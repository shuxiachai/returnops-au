"""No-DB checks for the installed, explicitly synthetic fixed builder."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import subprocess
import sys
from pathlib import Path
import pytest
from returnops_domain.fixed_proposal import build_fixed_proposal, ProposalCapacityError
from returnops_domain.founder_codec import validate
from returnops_domain.proposal_sources import RetainedMaterial
from returnops_domain.proposal_policy import intent_key, stable_id
from returnops_domain.proposal_processor import FixedProposalProcessor, Intent, _ProposalUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.audit import timestamp


def material():
    samples = json.loads((Path(__file__).parents[2]/'contracts/v1/examples.json').read_text())
    body = deepcopy(next(item['value']['content'] for item in samples['positive'] if item['name']=='history-proposal'))
    return RetainedMaterial(body['packet']['original_statement_id'],body['statements'],[],{},body['order_lookup'],'projection-fixed-test')


def build(source):
    return build_fixed_proposal(source,{'work_id':'work-fixed-test','case_id':'case-demo-001','input_version':1},1,
                                datetime(2026,10,5,tzinfo=timezone.utc))


def test_fixed_builder_preserves_complete_sources_without_inventing_assessment():
    source = material();before=deepcopy(source)
    body = build(source)
    validate('HistoricalProposalBundle',body)
    assert source==before and body['statements']==source.statements and body['order_lookup']==source.order_lookup
    assert body['packet']['recommended_action']=='REFER_FOR_MANUAL_HANDLING'
    assert body['packet']['facts']['assessment_status']=='UNCERTAIN'
    assert body['packet']['model_run']['model_id']=='fixture-no-live-model'
    assert body['packet']['model_run']['input_tokens']==body['packet']['model_run']['output_tokens']==0
    assert body['retrieval_result']['passages'][0]['is_synthetic'] is True
    body['statements'][0]['raw_text']='changed'
    assert source==before


def test_complete_input_at_exact_capacity_and_overflow_is_not_truncated():
    source = material()
    original=source.statements[0]
    for number in range(99):
        source.statements.append(dict(statement_id='clarification-'+str(number),kind='CLARIFICATION',
            raw_text='retained complete clarification',submitted_at=original['submitted_at']))
    assert len(build(source)['statements'])==100
    source.statements.append(dict(statement_id='clarification-overflow',kind='CLARIFICATION',
        raw_text='retained overflow',submitted_at=original['submitted_at']))
    with pytest.raises(ProposalCapacityError) as caught:build(source)
    assert len(source.statements)==101 and caught.value.__context__ is None


def test_work_identity_binds_every_original_target_field():
    head=dict(store_id='store-fixed',owner_principal_id='owner-fixed',case_id='case-fixed',input_version=2)
    key=intent_key(head,{'generation':3},'a'*64)
    original=stable_id('work',key)
    assert len(original)<=80 and original==stable_id('work',deepcopy(key))
    for name,value in key.items():
        changed=dict(key);changed[name]=value+1 if type(value) is int else value+'x'
        assert stable_id('work',changed)!=original


def test_production_import_has_no_test_or_offline_fixture_dependency():
    result=subprocess.run([sys.executable,'-B','-c',
        "import sys; import returnops_domain.proposal_processor; import returnops_api.main; "
        "assert not any(name.startswith(('tests.', 'tools.')) or name in "
        "{'synthetic_sources','controlled_denial_caller','offline_fixed_proposal'} for name in sys.modules); "
        "print('PASS installed-package runtime imports without test/offline producer')"],capture_output=True,timeout=15)
    assert result.returncode==0,result.stderr.decode('utf-8',errors='replace')
    assert b'PASS installed-package' in result.stdout


def test_transient_retry_keeps_intent_and_backs_off_without_database_polling():
    clock=[datetime(2026,10,5,tzinfo=timezone.utc)]
    key=intent_key(dict(store_id='store-fixed',owner_principal_id='owner-fixed',case_id='case-fixed',input_version=2),
                   {'generation':3},'a'*64)
    intent=Intent(stable_id('work',key),key,timestamp(clock[0]),1)
    # An invalid engine makes any unintended early DB poll fail this test.
    worker=FixedProposalProcessor(object(),clock=lambda:clock[0])
    for expected in [1,2,4,8,16,32,60,60]:
        result=worker._retryable(intent)
        assert result.status=='RETRYABLE' and result.work_id==intent.work_id and result.audit=='NOT_ATTEMPTED'
        assert worker._retry_intent==intent and worker._retry_after-clock[0]==timedelta(seconds=expected)
        assert worker.run_once() is False


@pytest.mark.parametrize('code,retryable',[('INTERNAL_ERROR',True),('INVALID_STATE',False),('FORBIDDEN',False)])
def test_private_uow_keeps_commit_check_classification_without_payload(code,retryable):
    uow=_ProposalUnitOfWork(object(),write=True);uow.transaction=object()
    def check():raise FlowError(code)
    uow.before_commit(check)
    with pytest.raises(FlowError):uow._commit_checks[0]()
    assert uow.retryable_rollback is retryable
