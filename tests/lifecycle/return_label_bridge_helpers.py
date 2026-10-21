"""Actual production N1/N2 setup with explicitly synthetic upstream inputs."""
from dataclasses import asdict
from sqlalchemy import select, text
from returnops_api.private_return_label_bridge import compose_private_return_label_bridge
from returnops_domain import customer_tables as old, lifecycle_tables as life
from returnops_domain.core_return_mock import CoreReturnMock
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.return_label_sources import KIND
from returnops_domain.return_execution_tables import ledger
from create_return_execution_helpers import (ready as return_ready, service as return_service,
    execute as return_execute, control, rows, snapshot, evidence)


def ready(engine, identities):
    upstream, setup = return_ready(engine, identities)
    result = return_execute(return_service(engine, identities), upstream)
    assert result.status == 'COMMITTED' and result.operation_state == 'SUCCEEDED', asdict(result)
    head, = rows(engine, old.case_heads)
    arguments = {name:upstream[name] for name in ('case_id','execution_work_id','original_approval_key')}
    arguments.update(expected_case_version=head['case_version'], correlation_id='return-source-correlation')
    return arguments, {**setup, 'upstream':upstream, 'return_result':result}


def service(engine, identities, name='founder', **options):
    return compose_private_return_label_bridge(engine, identities.auth_config,
        None if name is None else 'Bearer ' + identities.tokens[name], **options)


def accept(caller, arguments):
    return caller.accept_return_source(**arguments)


def recover(caller, arguments):
    return caller.recover_return_source(**{name:arguments[name] for name in
        ('case_id','execution_work_id','original_approval_key','correlation_id')})


def accepted_rows(engine):
    return [row for row in rows(engine, life.events) if row['event_kind'] == KIND]


def no_provider(monkeypatch):
    calls = []
    def forbidden(*args, **kwargs):
        calls.append('unexpected create/query')
        raise AssertionError('Bridge must not call any provider adapter')
    monkeypatch.setattr(CoreReturnMock, 'perform', forbidden)
    return calls


def assert_accepted(engine, arguments, result, before):
    assert result.status == 'ACCEPTED' and result.label_context, asdict(result)
    after = snapshot(engine)
    assert {name for name in before if before[name] != after[name]} == {
        old.case_heads.name, old.audit.name, life.work.name, life.sources.name, life.events.name}
    head_before, = before[old.case_heads.name]; head_after, = after[old.case_heads.name]
    assert head_after['case_version'] == head_before['case_version'] + 1
    assert head_after['status'] == head_before['status'] == 'ACTION_IN_PROGRESS'
    assert head_after['history_sequence'] == head_before['history_sequence']
    assert head_after['audit_sequence'] == head_before['audit_sequence'] + 1
    assert after[life.state.name] == before[life.state.name]
    assert after[old.history.name] == before[old.history.name]
    assert after[old.history_contents.name] == before[old.history_contents.name]
    original_work = next(row for row in before[life.work.name] if row['work_id'] == arguments['execution_work_id'])
    assert next(row for row in after[life.work.name] if row['work_id'] == arguments['execution_work_id']) == original_work
    receipt, = accepted_rows(engine)
    assert receipt['event_id'] == result.event_id and receipt['source_id'] == result.source_record_id
    assert receipt['pre_case_version'] == arguments['expected_case_version']
    work = next(row for row in rows(engine, life.work) if row['work_id'] == receipt['work_id'])
    binding = next(row for row in rows(engine, life.sources) if row['record_id'] == receipt['record_id'])
    assert work['state'] == 'DONE' and work['purpose'] == 'EFFECT' and work['epoch'] == 1
    assert work['claim_id'] and work['lease_expires_at'] is None and work['authority_revision'] >= 1
    assert binding['case_version'] == work['claimed_case_version'] == receipt['pre_case_version']
    assert binding['dispatch_source_record_id'] == control(engine)['dispatch_record_id']
    assert all(binding[name] is None for name in ('artifact_evidence_id','artifact_sha256','order_projection_id'))
    assert result.label_context['label_command']['provider_id'] == 'provider-mock-label'
    assert 'provider_return_id' not in result.label_context['label_command']['parameters']
    assert result.label_context['provider_return_id'] == rows(engine, ledger)[0]['provider_return_id']
    return after

