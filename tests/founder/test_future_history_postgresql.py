"""Neutral reads of synthetic frozen records; no future business producer exists."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from returnops_api.main import create_app
from returnops_domain import customer_tables as t, founder_codec as finite
from returnops_domain.audit import append_event, identifier
from returnops_domain.canonical import decode_document, digest, encode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from founder_helpers import accepted, founder, business_fingerprints
from future_history_fixtures import KINDS, EVENTS, EXAMPLES, material, persist, tombstone


def source(engine, case_id, version=1):
    value = material('PROPOSAL',case_id,version=version)
    return persist(engine,case_id,value)


def test_fractional_image_observations_survive_persisted_public_history(flow_engine,identities):
    case_id=accepted(identities)['case_id']
    value=material('PROPOSAL',case_id)
    observations=deepcopy(EXAMPLES['image-observation-result'])
    observations.update(case_id=case_id,input_version=value['content']['packet']['input_version'])
    observations['observations'][0]['confidence']=.75
    observations['observations'][0]['evidence_id']=value['content']['attachments'][0]['evidence_id']
    value['content']['image_observations']=observations
    persist(flow_engine,case_id,value)
    before=business_fingerprints(flow_engine)
    with TestClient(create_app(engine=flow_engine,auth_config=identities.auth_config,enable_processor=False)) as client:
        response=client.get('/v1/founder/cases/'+case_id+'/history',params={'kind':'PROPOSAL'},
            headers={'Authorization':'Bearer '+identities.tokens['founder']})
        assert response.status_code == 200
        content=response.json()['items'][0]['content']
        assert content['packet']['confidence'] == .8 and content['image_observations']['observations'][0]['confidence'] == .75
        assert content == value['content']
    assert business_fingerprints(flow_engine) == before


@pytest.mark.parametrize('kind', KINDS)
def test_all_frozen_nonempty_kinds_use_real_http_filtered_stable_pages(flow_engine, identities, kind):
    case_id=accepted(identities)['case_id']
    refs=[]
    values=[]
    for version in (1,2):
        proposal=source(flow_engine,case_id,version) if kind == 'REVIEW' else None
        value=material(kind,case_id,version=version,proposal_record_id=None if proposal is None else proposal['record_id'])
        refs.append(persist(flow_engine,case_id,value))
        values.append(value)
    before=business_fingerprints(flow_engine)
    with TestClient(create_app(engine=flow_engine,auth_config=identities.auth_config,enable_processor=False)) as client:
        headers={'Authorization':'Bearer '+identities.tokens['founder']}
        path='/v1/founder/cases/'+case_id+'/history'
        query={'kind':kind,'object_id':refs[0]['object_id'],'limit':1}
        first=client.get(path,params=query,headers=headers)
        assert first.status_code == 200
        one=first.json()
        assert one['items'][0]['content'] == values[0]['content']
        assert one['items'][0]['actor'] == values[0]['actor']
        second=client.get(path,params={**query,'cursor':one['next_cursor']},headers=headers)
        assert second.status_code == 200
        two=second.json()
        assert two['snapshot_id'] == one['snapshot_id'] and two['items'][0]['record_id'] == refs[1]['record_id']
        assert two['items'][0]['content_sha256'] == finite.digest(values[1]['content'])
        exact=client.get(path,params={'kind':kind,'object_id':refs[1]['object_id'],'object_version':2},headers=headers)
        assert exact.status_code == 200 and [item['record_id'] for item in exact.json()['items']] == [refs[1]['record_id']]
        assert client.get(path,params={**query,'cursor':one['next_cursor'],'kind':'STATEMENT'},headers=headers).status_code == 409
    assert business_fingerprints(flow_engine) == before


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('damage', ['identity','case','dto','origin','hash'])
def test_future_corruption_is_safe_503_without_source_text(flow_engine, identities, kind, damage):
    case_id=accepted(identities)['case_id']
    proposal=source(flow_engine,case_id) if kind == 'REVIEW' else None
    value=material(kind,case_id,proposal_record_id=None if proposal is None else proposal['record_id'])
    def mutate(item):
        if damage == 'identity': item['object_id']='wrong_object_identity'
        if damage == 'dto': item['content']['unexpected_private_field']='DO_NOT_LEAK_PRIVATE_VALUE'
        if damage == 'case':
            body=item['content'].get('packet',item['content'].get('review',item['content']))
            (body['scope'] if kind == 'APPROVAL' else body)['case_id']='wrong_case_identity'
    ref=persist(flow_engine,case_id,value,mutation=mutate,event_type='RETENTION_REMOVED' if damage == 'origin' else None)
    if damage == 'hash':
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            uow.execute(update(t.history).where(t.history.c.record_id == ref['record_id']).values(content_sha256='0'*64))
            uow.commit()
    before=business_fingerprints(flow_engine)
    with TestClient(create_app(engine=flow_engine,auth_config=identities.auth_config,enable_processor=False)) as client:
        response=client.get('/v1/founder/cases/'+case_id+'/history',params={'kind':kind},headers={'Authorization':'Bearer '+identities.tokens['founder']})
        assert response.status_code == 503 and response.json()['error']['code'] == 'INTERNAL_ERROR'
        assert 'DO_NOT_LEAK_PRIVATE_VALUE' not in response.text and 'fixture-no-live-model' not in response.text
    assert business_fingerprints(flow_engine) == before


@pytest.mark.parametrize('kind', ['PROPOSAL','REVIEW','DECISION','APPROVAL'])
def test_actor_must_match_saved_model_or_founder(flow_engine,identities,kind):
    case_id=accepted(identities)['case_id']
    proposal=source(flow_engine,case_id) if kind == 'REVIEW' else None
    value=material(kind,case_id,proposal_record_id=None if proposal is None else proposal['record_id'])
    actor=deepcopy(value['actor'])
    if actor['kind'] == 'MODEL': actor['model_run']['run_id']='wrong_model_run'
    else: actor['principal_id']='wrong_founder'
    persist(flow_engine,case_id,value,actor=actor)
    with pytest.raises(FlowError): founder(flow_engine,identities).read('listFounderCaseHistory',case_id,{'kind':kind})


@pytest.mark.parametrize('damage', ['record','foreign_record','kind','version','input','corpus','proposal_version','bundle_input','bundle_corpus','citation_coverage','duplicate_origin'])
def test_review_reference_and_proposal_saved_bindings(flow_engine,identities,damage):
    case_id=accepted(identities)['case_id']
    proposal_value=material('PROPOSAL',case_id)
    if damage == 'proposal_version': proposal_value['content']['packet']['proposal_version']=2
    if damage == 'bundle_input': proposal_value['content']['order_lookup']['input_version']=2
    if damage == 'bundle_corpus': proposal_value['content']['retrieval_result']['corpus_version']='wrong-corpus'
    if damage == 'citation_coverage': proposal_value['content']['citation_verification']['checks']=[]
    proposal=persist(flow_engine,case_id,proposal_value)
    review=material('REVIEW',case_id,proposal_record_id=proposal['record_id'])
    if damage == 'record': review['content']['proposal_record_id']='hist_missing'
    if damage == 'foreign_record':
        other=accepted(identities,key='foreign-proposal-fixture')['case_id']
        review['content']['proposal_record_id']=source(flow_engine,other)['record_id']
    if damage == 'kind':
        with flow_engine.connect() as connection:
            review['content']['proposal_record_id']=connection.execute(select(t.history.c.record_id).where(t.history.c.kind == 'STATEMENT')).scalar_one()
    if damage == 'version': review['content']['review']['proposal_version']=2
    if damage == 'input': review['content']['review']['input_version']=2
    if damage == 'corpus': review['content']['review']['corpus_version']='wrong-corpus'
    ref=persist(flow_engine,case_id,review)
    if damage == 'duplicate_origin':
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            row=uow.execute(select(t.history).where(t.history.c.record_id == ref['record_id'])).mappings().one()
            append_event(uow,case_id,actor=review['actor'],event_type=EVENTS['REVIEW'],correlation_id=identifier('corr'),
                payload={'duplicate_fixture':True},object_ids=[ref['object_id']],history_refs=[ref],now=row['recorded_at'])
            uow.commit()
    with pytest.raises(FlowError): founder(flow_engine,identities).read('listFounderCaseHistory',case_id,{'kind':'REVIEW'})


def test_review_retains_reference_to_proposal_tombstone_without_rebuilding(flow_engine,identities):
    case_id=accepted(identities)['case_id']
    proposal=source(flow_engine,case_id)
    review=material('REVIEW',case_id,proposal_record_id=proposal['record_id'])
    persist(flow_engine,case_id,review)
    tombstone(flow_engine,proposal['record_id'])
    before=business_fingerprints(flow_engine)
    page=founder(flow_engine,identities).read('listFounderCaseHistory',case_id,{'kind':'REVIEW'}).body
    assert page['items'][0]['content'] == review['content']
    removed=founder(flow_engine,identities).read('listFounderCaseHistory',case_id,{'kind':'PROPOSAL'}).body['items'][0]
    assert removed['retention_state'] == 'DELETED' and 'content' not in removed
    assert business_fingerprints(flow_engine) == before


@pytest.mark.parametrize('kind', ['OPERATION','NOTIFICATION'])
def test_future_revision_appends_do_not_enter_existing_snapshot(flow_engine,identities,kind):
    case_id=accepted(identities)['case_id']
    refs=[persist(flow_engine,case_id,material(kind,case_id,version=v)) for v in (1,2)]
    flow=founder(flow_engine,identities)
    first=flow.read('listFounderCaseHistory',case_id,{'kind':kind,'limit':1}).body
    persist(flow_engine,case_id,material(kind,case_id,version=3))
    before=business_fingerprints(flow_engine)
    second=flow.read('listFounderCaseHistory',case_id,{'kind':kind,'limit':1,'cursor':first['next_cursor']}).body
    assert second['snapshot_id'] == first['snapshot_id'] and 'next_cursor' not in second
    assert second['items'][0]['record_id'] == refs[1]['record_id']
    fresh=flow.read('listFounderCaseHistory',case_id,{'kind':kind}).body
    assert len(fresh['items']) == 3
    assert business_fingerprints(flow_engine) == before


@pytest.mark.parametrize('kind,field', [('DECISION','decisions'),('APPROVAL','approvals'),('OPERATION','operations'),('NOTIFICATION','notifications')])
def test_future_windows_and_latest_tombstone_never_revert(flow_engine,identities,kind,field):
    case_id=accepted(identities)['case_id']
    first=persist(flow_engine,case_id,material(kind,case_id))
    second=persist(flow_engine,case_id,material(kind,case_id,version=2))
    flow=founder(flow_engine,identities)
    detail=flow.read('getFounderCase',case_id).body
    assert len(detail[field]) == 1
    window=detail['collection_windows'][field]
    assert window['total_records'] == 2 and window['preview_count'] == 1
    tombstone(flow_engine,second['record_id'])
    before=business_fingerprints(flow_engine)
    later=flow.read('getFounderCase',case_id).body
    assert later[field] == [] and later['collection_windows'][field]['unavailable_count'] == 1
    page=flow.read('listFounderCaseHistory',case_id,{'kind':kind,'cursor':window['start_cursor']}).body
    assert [item['record_id'] for item in page['items']] == [first['record_id'],second['record_id']]
    assert page['items'][1]['retention_state'] == 'DELETED' and 'content' not in page['items'][1]
    assert business_fingerprints(flow_engine) == before
