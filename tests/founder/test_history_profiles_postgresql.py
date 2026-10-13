"""Persistent numeric profile bindings, legacy projection and retention safety."""
import pytest
from sqlalchemy import select,update,inspect,text
from returnops_domain import customer_tables as t, founder_tables as f, founder_codec as finite
from returnops_domain import lifecycle_tables as lifecycle
from returnops_domain import preview_tables as preview
from returnops_domain.canonical import digest as old_digest, encode_document as old_encode
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from founder_helpers import accepted,founder,business_fingerprints,rows
from future_history_fixtures import material,persist,tombstone
from conftest import migrate


def legacy_material(case_id):
    value=material('PROPOSAL',case_id)
    # Separate legacy integer compatibility fixture; the primary .8 tests remain.
    value['content']['packet']['confidence']=1
    return value


def test_legacy_body_is_projected_without_rewriting_original_bytes(flow_engine,identities):
    case_id=accepted(identities)['case_id']
    value=legacy_material(case_id)
    ref=persist(flow_engine,case_id,value,legacy=True)
    before=business_fingerprints(flow_engine)
    page=founder(flow_engine,identities).read('listFounderCaseHistory',case_id,{'kind':'PROPOSAL'}).body
    assert page['items'][0]['content_sha256'] == finite.digest(value['content'])
    encoding=rows(flow_engine,f.encodings)[0]
    assert encoding['profile'] == finite.LEGACY_PROFILE
    assert encoding['source_content_sha256'] == old_digest(value['content'],'history/v1')
    assert encoding['projected_content_sha256'] == finite.digest(value['content'])
    assert business_fingerprints(flow_engine) == before
    tombstone(flow_engine,ref['record_id'])
    before=business_fingerprints(flow_engine)
    removed=founder(flow_engine,identities).read('listFounderCaseHistory',case_id,{'kind':'PROPOSAL'}).body['items'][0]
    assert 'content' not in removed and removed['content_sha256'] == finite.digest(value['content'])
    assert business_fingerprints(flow_engine) == before


@pytest.mark.parametrize('damage',['missing','wrong_profile','wrong_header','source_hash','projected_hash','old_kind'])
def test_metadata_cannot_authorize_an_unbound_codec_or_hash(flow_engine,identities,damage):
    case_id=accepted(identities)['case_id']
    value=material('PROPOSAL',case_id)
    ref=persist(flow_engine,case_id,value)
    kind='PROPOSAL'
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        if damage == 'missing': uow.execute(f.encodings.delete().where(f.encodings.c.record_id == ref['record_id']))
        elif damage == 'wrong_profile': uow.execute(update(f.encodings).where(f.encodings.c.record_id == ref['record_id']).values(profile=finite.LEGACY_PROFILE))
        elif damage == 'wrong_header': uow.execute(update(t.history_contents).where(t.history_contents.c.record_id == ref['record_id']).values(body=old_encode({'private':'do-not-return'})))
        elif damage == 'source_hash': uow.execute(update(f.encodings).where(f.encodings.c.record_id == ref['record_id']).values(source_content_sha256='0'*64))
        elif damage == 'projected_hash': uow.execute(update(f.encodings).where(f.encodings.c.record_id == ref['record_id']).values(projected_content_sha256='0'*64))
        else:
            kind='STATEMENT'
            statement=uow.execute(select(t.history).where(t.history.c.case_id == case_id,t.history.c.kind == kind)).mappings().one()
            uow.execute(f.encodings.insert().values(record_id=statement['record_id'],profile=finite.PROFILE,
                source_content_sha256=statement['content_sha256'],projected_content_sha256=statement['content_sha256'],receipt_id=None))
        uow.commit()
    before=business_fingerprints(flow_engine)
    with pytest.raises(FlowError) as error: founder(flow_engine,identities).read('listFounderCaseHistory',case_id,{'kind':kind})
    assert error.value.code == 'INTERNAL_ERROR'
    assert business_fingerprints(flow_engine) == before


def test_legacy_tombstone_without_encoding_does_not_guess_public_hash(flow_engine,identities):
    case_id=accepted(identities)['case_id']
    ref=persist(flow_engine,case_id,legacy_material(case_id),legacy=True)
    tombstone(flow_engine,ref['record_id'])
    with pytest.raises(FlowError): founder(flow_engine,identities).read('listFounderCaseHistory',case_id,{'kind':'PROPOSAL'})
    assert rows(flow_engine,f.encodings) == []


@pytest.mark.parametrize('flow_engine',['0005_order_investigation'],indirect=True)
def test_0006_backfills_legacy_future_metadata_without_business_rewrites(flow_engine,identities):
    case_id=accepted(identities)['case_id']
    value=legacy_material(case_id)
    persist(flow_engine,case_id,value,legacy=True)
    before=business_fingerprints(flow_engine)
    migrate(flow_engine)
    migrate(flow_engine)
    after=business_fingerprints(flow_engine)
    from returnops_domain import execution_preparation_tables
    added = {**lifecycle.metadata.tables, **preview.metadata.tables, **execution_preparation_tables.metadata.tables}
    assert {name:value for name,value in after.items() if name not in added} == before
    assert set(after)-set(before) == set(added)
    assert all(rows(flow_engine,table)==[] for table in added.values())
    assert rows(flow_engine,f.encodings)[0]['profile'] == finite.LEGACY_PROFILE
    result=founder(flow_engine,identities).read('listFounderCaseHistory',case_id,{'kind':'PROPOSAL'}).body
    assert result['items'][0]['content_sha256'] == finite.digest(value['content'])


@pytest.mark.parametrize('flow_engine',['0005_order_investigation'],indirect=True)
def test_0006_missing_legacy_tombstone_source_rolls_back_for_separate_data_plan(flow_engine,identities):
    case_id=accepted(identities)['case_id']
    ref=persist(flow_engine,case_id,legacy_material(case_id),legacy=True)
    tombstone(flow_engine,ref['record_id'])
    before=business_fingerprints(flow_engine)
    with pytest.raises(FlowError): migrate(flow_engine)
    assert not set(f.metadata.tables) & set(inspect(flow_engine).get_table_names())
    assert business_fingerprints(flow_engine) == before
    with flow_engine.connect() as connection:
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0005_order_investigation'
