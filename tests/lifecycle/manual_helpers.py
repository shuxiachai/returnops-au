"""Explicit synthetic setup; positive states come from real accepted entries."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from sqlalchemy import inspect, select, text
from returnops_api.private_manual import compose_private_manual
from returnops_domain import customer_tables as old, investigation_tables as inv, lifecycle_tables as t
from returnops_domain.audit import identifier
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.manual_denial import COMPONENT
from returnops_domain.mock_orders import load_builtin_catalogue
from returnops_domain.order_ports import OrderSourceUnavailable


def now():
    return datetime.now(timezone.utc)


def rows(engine, table):
    with engine.connect() as connection:
        return [dict(r) for r in connection.execute(select(table)).mappings()]


class BrokenSource:
    metadata = load_builtin_catalogue().metadata

    def read_matches(self, *args):
        raise OrderSourceUnavailable()


def ready(engine, identities, kind, *, grant=True):
    case = identities.flow().create({'original_message':'Synthetic manual source; retain exactly.',
        'order_reference':'SYN-CONFLICT' if kind == 'block' else 'SYN-1001'},
        identifier('create'), identifier('corr')).body['case_id']
    assert IntakeProcessor(engine).run_once()
    processor = InvestigationProcessor(engine, catalogue=BrokenSource() if kind == 'failure' else None,
                                       retry_seconds=0)
    assert processor.run_once()
    if kind == 'failure':
        assert processor.run_once()
    head = next(r for r in rows(engine, old.case_heads) if r['case_id'] == case)
    assert head['status'] == 'ESCALATED'
    states = [r for r in rows(engine, t.state) if r['case_id'] == case]
    assert not states or states[0]['proposal_record_id'] is None
    field = 'processing_failure_id' if kind == 'failure' else 'order_lookup_block_id'
    target = head['current_failure_id'] if kind == 'failure' else next(
        r['current_block_id'] for r in rows(engine, inv.state) if r['case_id'] == case)
    if grant:
        provision_outcome(engine, identities)
    return case, dict(expected_case_version=head['case_version'], decision='MANUAL_HANDLING',
                      reason='The Founder will handle this request manually.', **{field:target})


def provision_outcome(engine, identities):
    """Explicit test provisioning outside the business caller, never startup."""
    with CustomerUnitOfWork(engine, write=True) as uow:
        exists = uow.execute(select(t.authorities).where(t.authorities.c.component_id == COMPONENT,
            t.authorities.c.purpose == 'OUTCOME')).first()
        if exists is None:
            uow.execute(t.authorities.insert().values(store_id=identities.people['founder']['store_id'],
                component_id=COMPONENT, purpose='OUTCOME', revision=1, enabled=True))
        uow.commit()


def service(engine, identities, name='founder', **options):
    return compose_private_manual(engine, identities.auth_config,
                                  None if name is None else 'Bearer ' + identities.tokens[name], **options)


def snapshot(engine):
    """Every physical table, stable ordering; binary bodies are hashed exactly."""
    def safe(value):
        if isinstance(value, (bytes, memoryview)):
            return {'byte_length':len(value), 'sha256':sha256(bytes(value)).hexdigest()}
        if isinstance(value, datetime):
            return value.isoformat()
        return value
    with engine.connect() as connection:
        result = {}
        for name in inspect(connection).get_table_names():
            data = [{k:safe(v) for k,v in r.items()} for r in
                    connection.execute(text('SELECT * FROM "' + name + '"')).mappings()]
            result[name] = sorted(data, key=lambda r:json.dumps(r, sort_keys=True))
        return result


def business(value):
    value = {k:[dict(r) for r in v] for k,v in value.items()}
    value.pop('customer_audit_events')
    for row in value['case_heads']:
        row.pop('audit_head'); row.pop('audit_sequence')
    return value


def evidence(node, **values):
    destination = os.environ.get('MANUAL_EVIDENCE_DIR')
    if destination:
        path = Path(destination)
        path.mkdir(parents=True, exist_ok=True)
        name = sha256(node.encode()).hexdigest() + '.json'
        target = path / name
        assert not target.exists(), 'Do not overwrite earlier execution evidence.'
        target.write_text(json.dumps({'node':node, **values}, indent=2, ensure_ascii=True, default=str), encoding='utf-8')


def assert_pending(engine, case, request, result):
    assert result.status == 'ACCEPTED', (result.status, result.safe_code, result.audit)
    head = next(r for r in rows(engine, old.case_heads) if r['case_id'] == case)
    assert head['status'] == 'NOTIFICATION_PENDING'
    assert head['case_version'] == request['expected_case_version'] + 1
    state = next(r for r in rows(engine, t.state) if r['case_id'] == case)
    assert state['outcome'] == 'MANUAL_HANDLED' and state['approval_record_id'] is None
    from returnops_domain.lifecycle_schema import NOTIFICATION,version
    from returnops_domain.notification_profile import COMPONENT as delivery_component
    with engine.connect() as connection:
        modern=version(connection)==NOTIFICATION
    expected_notification_component=delivery_component if modern else COMPONENT
    works = [r for r in rows(engine,t.work) if r['case_id']==case
             and r['component_id'] in {COMPONENT,expected_notification_component}]
    assert len(works) == 2
    outcome = next(r for r in works if r['purpose'] == 'OUTCOME')
    notification = next(r for r in works if r['purpose'] == 'NOTIFICATION')
    assert outcome['component_id']==COMPONENT and notification['component_id']==expected_notification_component
    if modern:
        from returnops_domain.notification_tables import controls,facts
        saved,=[row for row in rows(engine,controls) if row['case_id']==case]
        assert saved['notification_work_id']==notification['work_id'] and saved['state']=='READY'
        assert saved['attempt_count']==0 and saved['producer_id']==COMPONENT
        assert not [row for row in rows(engine,facts) if row['case_id']==case]
    assert outcome['state'] == 'DONE' and outcome['epoch'] == 1 and outcome['claim_id']
    assert notification['state'] == 'PENDING' and notification['claim_id'] is None
    assert notification['epoch'] == 0 and notification['authority_revision'] is None
    assert notification['idempotency_key'] and notification['work_id'] == state['notification_work_id']
    assert not rows(engine, t.effects)
    assert not any(r['kind'] in {'APPROVAL','OPERATION'} for r in rows(engine, old.history))
