"""Cloud-only actual approved/prepared source; grants are explicit test setup."""
from dataclasses import asdict
from sqlalchemy import select
from returnops_api.private_return_execution import compose_private_return_execution
from returnops_domain import customer_tables as old, founder_codec as finite, lifecycle_tables as life
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.return_execution_tables import controls, permissions, ledger
from returnops_domain.return_execution_sources import COMPONENT, CONFIG, config_hash
from preparation_helpers import ready as preparation_ready, service as preparation_service
from manual_helpers import rows, snapshot, evidence


def provision(engine, identities):
    store = identities.people['founder']['store_id']
    with CustomerUnitOfWork(engine, write=True) as uow:
        for purpose in ('EXECUTION', 'EFFECT'):
            uow.execute(life.authorities.insert().values(store_id=store, component_id=COMPONENT,
                purpose=purpose, revision=1, enabled=True))
        uow.execute(permissions.insert().values(store_id=store, component_id=COMPONENT,
            provider_id=CONFIG['provider_id'], config_id=CONFIG['config_id'], command_type='CREATE_RETURN',
            config_hash=config_hash(), revision=1, create_enabled=True, query_enabled=True))
        uow.commit()


def ready(engine, identities, *, grants=True):
    arguments, setup = preparation_ready(engine, identities)
    prepared = preparation_service(engine, identities).prepare(**arguments)
    assert prepared.status == 'PREPARED', asdict(prepared)
    if grants:
        provision(engine, identities)
    return {**arguments, 'correlation_id': 'return-execution-correlation'}, {**setup, 'preparation': prepared}


def service(engine, identities, name='founder', **options):
    return compose_private_return_execution(engine, identities.auth_config,
        None if name is None else 'Bearer ' + identities.tokens[name], **options)


def execute(caller, arguments):
    return caller.execute_prepared_create_return(**arguments)


def reconcile(caller, arguments):
    return caller.reconcile_create_return(**{key: arguments[key] for key in
        ('case_id', 'execution_work_id', 'original_approval_key', 'correlation_id')})


def control(engine):
    value, = rows(engine, controls)
    return value


def successes(engine):
    return [row for row in rows(engine, ledger) if row['status'] == 'SUCCEEDED']


def assert_complete(engine, arguments, result, before):
    assert result.status in {'COMMITTED', 'REPLAYED'}, asdict(result)
    current = control(engine); saved, = rows(engine, ledger)
    assert current['status'] == saved['status'] == result.operation_state == 'SUCCEEDED'
    assert current['query_epoch'] == 0 and saved['effect_key'] == current['effect_key']
    assert result.provider_operation_id == saved['provider_operation_id'] == current['confirmed_provider_operation_id']
    records = sorted((row for row in rows(engine, old.history) if row['kind'] == 'OPERATION'), key=lambda row: row['object_version'])
    assert [row['object_version'] for row in records] == [1, 2, 3]
    assert len({row['object_id'] for row in records}) == 1
    raw, = [row for row in rows(engine, old.history_contents) if row['record_id'] == current['result_record_id']]
    body = finite.decode_document(raw['body'])
    assert body['attempt_count'] == 1 and body['status'] == 'SUCCEEDED'
    assert body['result'] == dict(type='CREATE_RETURN', provider_return_id=saved['provider_return_id'], parcel_id=saved['parcel_id'])
    assert body['idempotency_key'] == current['effect_key'] and body['operation_fingerprint'] == current['operation_fingerprint']
    after = snapshot(engine)
    changed = {name for name in before if before[name] != after[name]}
    assert changed == {old.case_heads.name, old.history.name, old.history_contents.name, old.audit.name,
                       'founder_history_encodings', controls.name, ledger.name, life.effects.name}
    assert after[life.work.name] == before[life.work.name]
    head, = [row for row in rows(engine, old.case_heads) if row['case_id'] == arguments['case_id']]
    assert head['status'] == 'ACTION_IN_PROGRESS' and head['case_version'] == arguments['expected_case_version'] + 1
    state, = rows(engine, life.state)
    assert all(state[name] is None for name in ('outcome', 'outcome_record_id', 'notification_id', 'return_record_id', 'label_record_id'))
    return after
