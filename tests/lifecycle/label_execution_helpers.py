"""Actual service chain with synthetic upstream inputs and explicit test grants."""
from dataclasses import asdict
from sqlalchemy import update
from returnops_api.private_label_execution import compose_private_label_execution
from returnops_domain import customer_tables as old, lifecycle_tables as life, founder_codec as finite
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.label_execution_tables import controls, permissions, ledger, artifact_work
from returnops_domain.label_execution_sources import COMPONENT, CONFIG, config_hash
from returnops_domain.core_label_mock import Ticket
from return_label_bridge_helpers import ready as bridge_ready, service as bridge_service, accept as bridge_accept
from manual_helpers import rows, snapshot, evidence


def provision(engine, identities):
    store = identities.people['founder']['store_id']
    with CustomerUnitOfWork(engine,write=True) as uow:
        for purpose in ('EXECUTION','EFFECT'):
            uow.execute(life.authorities.insert().values(store_id=store,component_id=COMPONENT,
                purpose=purpose,revision=1,enabled=True))
        uow.execute(permissions.insert().values(store_id=store,component_id=COMPONENT,
            provider_id=CONFIG['provider_id'],config_id=CONFIG['config_id'],command_type='GENERATE_LABEL',
            config_hash=config_hash(),revision=1,create_enabled=True,query_enabled=True))
        uow.commit()


def ready(engine,identities,*,grants=True):
    bridge_arguments,setup = bridge_ready(engine,identities)
    accepted = bridge_accept(bridge_service(engine,identities),bridge_arguments)
    assert accepted.status == 'ACCEPTED',asdict(accepted)
    head, = rows(engine,old.case_heads)
    if grants:provision(engine,identities)
    args = {**bridge_arguments,'expected_case_version':head['case_version'],'correlation_id':'label-execution-correlation'}
    return args,{**setup,'bridge_arguments':bridge_arguments,'bridge':accepted}


def service(engine,identities,name='founder',**options):
    return compose_private_label_execution(engine,identities.auth_config,
        None if name is None else 'Bearer '+identities.tokens[name],**options)


def execute(caller,args):
    return caller.execute_accepted_label(**args)


def reconcile(caller,args):
    return caller.reconcile_label(**{name:args[name] for name in
        ('case_id','execution_work_id','original_approval_key','correlation_id')})


def reserve(caller,args):
    result = caller._reserve(*(args[name] for name in ('case_id','expected_case_version','execution_work_id','original_approval_key','correlation_id')))
    assert type(result) is Ticket,asdict(result)
    return result


def control(engine):
    value, = rows(engine,controls)
    return value


def assert_complete(engine,args,result,before):
    assert result.status in {'COMMITTED','REPLAYED'} and result.operation_state == 'EXECUTING',asdict(result)
    row = control(engine);fact, = rows(engine,ledger);work, = rows(engine,artifact_work)
    assert row['confirmed_effect_status'] == fact['status'] == 'SUCCEEDED'
    assert result.provider_fact_status == 'SUCCEEDED' and work['state'] == 'PENDING'
    assert work['work_id'] == result.artifact_work_id and work['epoch'] == 0
    assert all(work[name] is None for name in ('claim_id','lease_expires_at','claimed_case_version','authority_revision'))
    assert row['query_claim_id'] is None and row['query_lease_until'] is None
    histories = sorted((r for r in rows(engine,old.history) if r['object_id'] == row['operation_id']),key=lambda r:r['object_version'])
    assert [r['object_version'] for r in histories] == [1,2,3]
    bodies = {r['record_id']:finite.decode_document(r['body']) for r in rows(engine,old.history_contents) if r['record_id'] in {h['record_id'] for h in histories}}
    assert [bodies[h['record_id']]['status'] for h in histories] == ['PENDING','EXECUTING','EXECUTING']
    assert [bodies[h['record_id']]['case_version'] for h in histories] == [args['expected_case_version'],args['expected_case_version']+1,args['expected_case_version']+1]
    assert all(bodies[h['record_id']]['attempt_count'] == 1 and 'result' not in bodies[h['record_id']] for h in histories)
    assert 'label_evidence_id' not in repr(bodies)
    after = snapshot(engine)
    changed = {name for name in before if before[name] != after[name]}
    assert changed == {old.case_heads.name,old.history.name,old.history_contents.name,old.audit.name,
        'founder_history_encodings',controls.name,ledger.name,artifact_work.name}
    prior, = before[old.case_heads.name];head, = after[old.case_heads.name]
    assert head['case_version'] == prior['case_version'] + 1 and head['history_sequence'] == prior['history_sequence'] + 3
    assert head['audit_sequence'] == prior['audit_sequence'] + 3 and head['status'] == prior['status'] == 'ACTION_IN_PROGRESS'
    for name in (life.work.name,life.state.name,life.sources.name,life.events.name,life.effects.name,'core_mock_return_ledger'):
        assert before[name] == after[name]
    assert len(after[life.effects.name]) == 1
    return after
