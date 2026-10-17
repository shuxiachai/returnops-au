"""Explicit synthetic fixture producers; these do not represent future features."""
from datetime import datetime, timezone
from hashlib import sha256
from sqlalchemy import inspect, select, text
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_domain import customer_tables as t
from returnops_domain.audit import append_event, identifier, timestamp
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.founder_service import FounderQueries
from returnops_domain.history import append_revision
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor


def founder(engine, identities, name='founder', **kwargs):
    return FounderQueries(engine, CurrentRequestAuthority(identities.auth_config, 'Bearer ' + identities.tokens[name]), **kwargs)


def accepted(identities, reference=None, key='founder-create-key'):
    request = {'original_message': '  synthetic original\x00\ud800  '}
    if reference is not None:
        request['order_reference'] = reference
    return identities.flow().create(request, key, identifier('corr')).body


def investigate(engine, identities, reference='SYN-1001', key='founder-create-key', catalogue=None):
    body = accepted(identities, reference, key)
    assert IntakeProcessor(engine).run_once()
    worker = InvestigationProcessor(engine, catalogue=catalogue, retry_seconds=0)
    assert worker.run_once()
    if catalogue is not None:
        assert worker.run_once()
    return body


def business_fingerprints(engine):
    """Every persisted non-Founder table, including old cursor metadata, is covered."""
    result = {}
    with engine.connect() as connection:
        for name in sorted(inspect(connection).get_table_names()):
            if name.startswith('founder_') or name == 'alembic_version':
                continue
            assert name.replace('_', '').isalnum()
            rows = connection.execute(text('SELECT * FROM "' + name + '"')).all()
            result[name] = sha256(repr(sorted((tuple(row) for row in rows), key=repr)).encode('utf-8', 'surrogatepass')).hexdigest()
    return result


def append_statements(engine, identities, case_id, count, *, object_id=None, start_version=1):
    """Accepted synthetic history + exact originating audit, for pagination tests.

    No future proposal/approval operation or public mutation route is fabricated.
    """
    refs = []
    with CustomerUnitOfWork(engine, write=True) as uow:
        for index in range(count):
            now = datetime.now(timezone.utc)
            statement = object_id or identifier('statement')
            content = {'statement_id': statement, 'kind': 'CLARIFICATION', 'question_id': 'question_synthetic',
                       'raw_text': 'synthetic historical statement ' + str(index), 'submitted_at': timestamp(now)}
            ref = append_revision(uow, case_id, 'STATEMENT', statement, start_version + index if object_id else 1, content, now)
            append_event(uow, case_id, actor={'kind': 'HUMAN', 'role': 'CUSTOMER', 'principal_id': identities.people['customer_a']['principal_id']},
                event_type='CUSTOMER_CLARIFICATION_ACCEPTED', correlation_id=identifier('corr'), payload={'fixture': True},
                object_ids=[statement], history_refs=[ref], now=now)
            refs.append(ref)
        uow.commit()
    return refs


def rows(engine, table):
    with engine.connect() as connection:
        return list(connection.execute(select(table)).mappings())
