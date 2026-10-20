"""AC11/12 subset: actual authorized HTTP reads and controlled retention.

Cloud-only. Read snapshots/cursors may be registered by existing GET services;
business records, delivery facts and all provider/render calls must stay fixed.
"""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from inspect import unwrap
import sys
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from starlette.concurrency import run_in_threadpool

from notification_helpers import ready, service, rows, snapshot, evidence
from returnops_api.main import create_app
from returnops_domain import customer_tables as old, founder_tables, lifecycle_tables as life
from returnops_domain.label_artifact_tables import artifacts, contents
from returnops_domain.label_execution_tables import ledger as label_facts
from returnops_domain.notification_mock import CoreMockNotification
from returnops_domain.notification_tables import controls, facts
from returnops_domain.retention import RetentionService
from returnops_domain.return_execution_tables import ledger as return_facts
from returnops_domain.wire import validate


KINDS = ('return', 'reject', 'manual_pass', 'manual_escalated',
         'manual_failure', 'manual_block', 'manual_intake', 'manual_assessment')
TERMINAL = {'RETURN_CREATED': 'COMPLETED', 'REJECTED': 'REJECTED',
            'MANUAL_HANDLED': 'MANUAL_HANDLED'}


def _headers(identities, role):
    return {} if role is None else {'Authorization': 'Bearer ' + identities.tokens[role]}


def _main_probe():
    """Safe calibration only: no provider, renderer, app or database call."""
    return threading.get_ident()


def _asgi_probe():
    return threading.get_ident()


def _worker_probe():
    return threading.get_ident()


class _CodeEntryProbe:
    """Observe actual code in every thread without replacing any profiler.

    Python 3.12 monitoring instruments code, so existing pools, future threads
    and aliases of the same function are covered. Only our claimed tool ID is
    modified. A callback exception can be swallowed by application code; the
    persistent counters are therefore independently asserted on context exit.
    """

    def __init__(self, functions, forbidden):
        self.codes = {function.__code__: name for name, function in functions.items()}
        assert len(self.codes) == len(functions), 'Ambiguous code-entry labels'
        self.forbidden = set(forbidden)
        self.counts = {name: 0 for name in functions}
        self.threads = {name: set() for name in functions}
        self.lock = threading.Lock()
        self.tool = None
        self.installed = []

    def _observe(self, code, offset):
        name = self.codes[code]
        with self.lock:
            self.counts[name] += 1
            self.threads[name].add(threading.get_ident())
        if name in self.forbidden:
            raise AssertionError('Forbidden actual code entry: ' + name)

    def __enter__(self):
        monitoring = sys.monitoring
        for tool in range(5, -1, -1):
            if monitoring.get_tool(tool) is None:
                try:
                    monitoring.use_tool_id(tool, 'notification-read-test')
                except ValueError:  # Another tool may have claimed this free ID.
                    continue
                self.tool = tool
                break
        assert self.tool is not None, 'No free Python monitoring tool ID'
        try:
            assert monitoring.get_events(self.tool) == 0
            monitoring.register_callback(self.tool, monitoring.events.PY_START, self._observe)
            for code in self.codes:
                assert monitoring.get_local_events(self.tool, code) == 0
                monitoring.set_local_events(self.tool, code, monitoring.events.PY_START)
                self.installed.append(code)
                assert monitoring.get_local_events(self.tool, code) == monitoring.events.PY_START
            _main_probe()
            assert self.counts['probe:main'] == 1
            assert self.threads['probe:main'] == {threading.get_ident()}
            return self
        except BaseException:
            self._close()
            raise

    def _close(self):
        if self.tool is None:
            return
        monitoring, tool = sys.monitoring, self.tool
        try:
            for code in self.installed:
                monitoring.set_local_events(tool, code, 0)
                assert monitoring.get_local_events(tool, code) == 0
            monitoring.set_events(tool, 0)
            assert monitoring.get_events(tool) == 0
            monitoring.register_callback(tool, monitoring.events.PY_START, None)
        finally:
            monitoring.free_tool_id(tool)
            assert monitoring.get_tool(tool) is None
            self.tool = None

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self._close()
        finally:
            assert not {name: self.counts[name] for name in self.forbidden
                        if self.counts[name]}, self.counts

    @property
    def pdf(self):
        return {name.removeprefix('pdf:'): count for name, count in self.counts.items()
                if name.startswith('pdf:')}

    @property
    def notification(self):
        return {name.removeprefix('notification:'): count for name, count in self.counts.items()
                if name.startswith('notification:')}

    def assert_http_threads(self):
        main = self.threads['probe:main']
        asgi = self.threads['probe:asgi']
        worker = self.threads['probe:worker']
        assert asgi and worker, self.threads
        assert main.isdisjoint(asgi | worker) and asgi.isdisjoint(worker), self.threads


def _io_probe(*, allow_notification_query=False):
    from returnops_domain import label_pdf as pdf, label_pdf_validation as validation
    from returnops_domain import label_artifact_sources as sources, label_artifact_history as history
    from returnops_domain.core_return_mock import CoreReturnMock
    from returnops_domain.core_label_mock import CoreLabelMock
    from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock

    functions = {
        'pdf:render': pdf.render_label_pdf, 'pdf:text_line': pdf._text_line,
        'pdf:assembly': pdf._assemble_pdf, 'pdf:expected_pdf': sources.expected_pdf,
        'pdf:validation': unwrap(validation.verify_label_pdf),
        'pdf:return_provider': CoreReturnMock.perform,
        'pdf:label_provider': CoreLabelMock.perform,
        'pdf:artifact_retrieval': CoreLabelArtifactMock.retrieve_original_label,
        'pdf:evidence_dto': history.evidence_body, 'pdf:result_dto': history.result_body,
        **{'notification:' + name: getattr(CoreMockNotification, name)
           for name in ('deliver', 'query', '_insert')},
        'probe:main': _main_probe, 'probe:asgi': _asgi_probe, 'probe:worker': _worker_probe,
    }
    forbidden = {'pdf:' + name for name in (
        'render', 'text_line', 'assembly', 'expected_pdf',
        'return_provider', 'label_provider', 'artifact_retrieval')}
    forbidden |= {'notification:deliver', 'notification:_insert'}
    if not allow_notification_query:
        forbidden.add('notification:query')
    return _CodeEntryProbe(functions, forbidden)


@contextmanager
def _client(engine, identities):
    # Install before app creation/startup; calibration never invokes business
    # functions and remains harmless if instrumentation is broken or absent.
    with _io_probe() as probe:
        app = create_app(engine=engine, auth_config=identities.auth_config, enable_processor=False)

        async def observed_app(scope, receive, send):
            if scope['type'] == 'http':
                _asgi_probe()
                await run_in_threadpool(_worker_probe)
            await app(scope, receive, send)

        with TestClient(observed_app) as client:
            try:
                yield client, probe
            finally:
                probe.assert_http_threads()


def _business(engine):
    names = {table.name for table in (
        old.case_heads, old.history, old.history_contents, life.state, life.effects,
        life.work, life.sources, life.events,
        controls, facts, return_facts, label_facts, artifacts, contents,
    )}
    value = {name: data for name, data in snapshot(engine).items() if name in names}
    # Existing denial auditing is permitted. It must not alter business state.
    for head in value[old.case_heads.name]:
        head.pop('audit_head')
        head.pop('audit_sequence')
    return value


def _get(client, path, identities, role='customer_a', params=None, schema=None):
    response = client.get(path, headers=_headers(identities, role), params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    if schema is not None:
        validate(schema, body)
    assert response.headers['Cache-Control'] == 'no-store'
    return body


@pytest.mark.parametrize('kind', KINDS)
def test_notification_actual_current_and_history_publish_only_sent(
        flow_engine, identities, enabled, request, kind):
    setup = ready(flow_engine, identities, kind)
    case = setup['case_id']
    path = '/v1/cases/' + case
    before = _business(flow_engine)
    with _client(flow_engine, identities) as (client, pending_probe):
        pending = _get(client, path, identities, schema='CustomerCaseView')
        pending_history = _get(client, path + '/history', identities,
                               params={'kind': 'OUTCOME_MESSAGE'}, schema='CustomerHistoryPage')
    assert 'outcome_message' not in pending and pending_history['items'] == []
    assert _business(flow_engine) == before
    sent = service(flow_engine, identities).send(setup['work_id'])
    assert sent.status == 'SENT', asdict(sent)
    before = _business(flow_engine)
    with _client(flow_engine, identities) as (client, probe):
        current = _get(client, path, identities, schema='CustomerCaseView')
        page = _get(client, path + '/history', identities,
                    params={'kind': 'OUTCOME_MESSAGE'}, schema='CustomerHistoryPage')
        founder = _get(client, '/v1/founder/cases/' + case, identities,
                       role='founder', schema='CaseView')
        audit = _get(client, '/v1/founder/cases/' + case + '/audit', identities,
                     role='founder', params={'limit':100}, schema='AuditPage')
    assert len(page['items']) == 1
    message = page['items'][0]['content']
    validate('CustomerOutcomeMessage', message)
    assert message['notification_id'] == setup['control']['notification_id']
    assert message['outcome'] == setup['control']['outcome']
    assert message['message'] in current['outcome_message']
    assert current['status'] == founder['status'] == TERMINAL[message['outcome']]
    customer_events=[event for event in audit['items']
                     if event['event_type']=='NOTIFICATION_CUSTOMER_MESSAGE_RECORDED']
    assert len(customer_events)==1
    assert customer_events[0]['history_refs'][0]['kind']=='NOTIFICATION'
    assert _business(flow_engine) == before
    assert len(rows(flow_engine, facts)) == 1 and rows(flow_engine, facts)[0]['status'] == 'SENT'
    evidence(request.node.nodeid, kind=kind, sent=asdict(sent),
             current_status=current['status'], actual_pdf_calls=probe.pdf,
             notification_read_calls=probe.notification,
             pending_pdf_calls=pending_probe.pdf,
             pending_notification_calls=pending_probe.notification)


@pytest.mark.parametrize('role,status,code', [
    ('customer_b', 404, 'NOT_FOUND'), ('founder', 403, 'FORBIDDEN'),
    (None, 401, 'UNAUTHENTICATED'),
])
def test_notification_customer_reads_remain_currently_authorized(
        flow_engine, identities, enabled, role, status, code):
    setup = ready(flow_engine, identities, 'reject')
    assert service(flow_engine, identities).send(setup['work_id']).status == 'SENT'
    before = _business(flow_engine)
    with _client(flow_engine, identities) as (client, probe):
        for suffix, params in (('', None), ('/history', {'kind': 'OUTCOME_MESSAGE'})):
            response = client.get('/v1/cases/' + setup['case_id'] + suffix,
                                  headers=_headers(identities, role), params=params)
            assert response.status_code == status
            validate('ErrorEnvelope', response.json())
            assert response.json()['error']['code'] == code
    assert _business(flow_engine) == before


def test_notification_founder_snapshot_does_not_mix_later_revisions(
        flow_engine, identities, enabled):
    setup = ready(flow_engine, identities, 'reject')
    path = '/v1/founder/cases/' + setup['case_id']
    before_initial = _business(flow_engine)
    with _client(flow_engine, identities) as (client, initial_probe):
        view = _get(client, path, identities, role='founder', schema='CaseView')
        window = view['collection_windows']['notifications']
        params = {'kind': 'NOTIFICATION', 'limit': 20, 'cursor': window['start_cursor']}
        initial = _get(client, path + '/history', identities, role='founder',
                       params=params, schema='FounderHistoryPage')
        assert initial['items'] and all(item['content']['status'] == 'PENDING'
                                        for item in initial['items'])
    assert _business(flow_engine) == before_initial
    assert service(flow_engine, identities).send(setup['work_id']).status == 'SENT'
    before = _business(flow_engine)
    with _client(flow_engine, identities) as (client, probe):
        old = _get(client, path + '/history', identities, role='founder',
                   params=params, schema='FounderHistoryPage')
        fresh = _get(client, path + '/history', identities, role='founder',
                     params={'kind': 'NOTIFICATION', 'limit': 20}, schema='FounderHistoryPage')
    assert old == initial
    assert any(item['content']['status'] == 'SENT' for item in fresh['items'])
    assert _business(flow_engine) == before


@pytest.mark.parametrize('fault', ['limit', 'filter', 'tampered', 'expired'])
def test_notification_history_cursor_uses_existing_context_errors(
        flow_engine, identities, enabled, fault):
    setup = ready(flow_engine, identities, 'reject')
    path = '/v1/founder/cases/' + setup['case_id']
    with _client(flow_engine, identities) as (client, probe):
        view = _get(client, path, identities, role='founder', schema='CaseView')
        window = view['collection_windows']['notifications']
        params = {'kind': 'NOTIFICATION', 'limit': 20, 'cursor': window['start_cursor']}
        if fault == 'limit':
            params['limit'] = 1
        elif fault == 'filter':
            params['kind'] = 'OPERATION'
        elif fault == 'tampered':
            token = params['cursor']
            params['cursor'] = token[:-1] + ('A' if token[-1] != 'A' else 'B')
        else:
            expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            with flow_engine.begin() as connection:
                changed = connection.execute(update(founder_tables.snapshots).where(
                    founder_tables.snapshots.c.snapshot_id == window['snapshot_id']).values(
                    as_of=expired_at - timedelta(seconds=1), expires_at=expired_at))
                assert changed.rowcount == 1
        before = _business(flow_engine)
        response = client.get(path + '/history', headers=_headers(identities, 'founder'),
                              params=params)
    assert response.status_code == 409
    validate('ErrorEnvelope', response.json())
    assert response.json()['error']['code'] == 'INVALID_STATE'
    assert _business(flow_engine) == before


@pytest.mark.parametrize('sent', [False, True])
@pytest.mark.parametrize('removed', ['pdf', 'statement'])
def test_notification_retention_keeps_safe_reads_and_never_restores_content(
        flow_engine, identities, enabled, request, sent, removed):
    setup = ready(flow_engine, identities, 'return')
    sender = service(flow_engine, identities)
    if sent:
        assert sender.send(setup['work_id']).status == 'SENT'
    original_facts = rows(flow_engine, facts)
    original_status = rows(flow_engine, old.case_heads)[0]['status']
    if removed == 'pdf':
        object_id = setup['artifact'].label_evidence_id
        kind = 'EVIDENCE'
    else:
        record = next(item for item in rows(flow_engine, old.history) if item['kind'] == 'STATEMENT')
        object_id, kind = record['object_id'], 'STATEMENT'
    assert RetentionService(flow_engine).remove(kind, object_id)
    assert rows(flow_engine, facts) == original_facts
    assert rows(flow_engine, old.case_heads)[0]['status'] == original_status
    control = rows(flow_engine, controls)[0]
    assert control['state'] == 'RETAINED' and control['available'] is False
    before = _business(flow_engine)
    path = '/v1/cases/' + setup['case_id']
    with _client(flow_engine, identities) as (client, probe):
        current = _get(client, path, identities, schema='CustomerCaseView')
        page = _get(client, path + '/history', identities,
                    params={'kind': 'OUTCOME_MESSAGE'}, schema='CustomerHistoryPage')
        _get(client, '/v1/founder/cases/' + setup['case_id'], identities,
             role='founder', schema='CaseView')
        history = _get(client, '/v1/founder/cases/' + setup['case_id'] + '/history', identities,
                       role='founder', params={'kind': 'NOTIFICATION'}, schema='FounderHistoryPage')
    assert 'outcome_message' not in current
    assert len(page['items']) == int(sent)
    assert all(item['retention_state'] != 'AVAILABLE' and 'content' not in item
               for item in page['items'])
    assert history['items'] and all(item['retention_state'] != 'AVAILABLE' and 'content' not in item
                                   for item in history['items'])
    assert _business(flow_engine) == before
    # Recovery may query original facts or remain HOLD/UNKNOWN, but cannot
    # accept a new completion or reconstruct removed derived content.
    with _io_probe(allow_notification_query=True) as recovery_probe:
        recovery = sender.reconcile(setup['work_id'])
    assert recovery.status in {'HOLD', 'UNKNOWN', 'RETAINED'}
    assert _business(flow_engine) == before
    assert rows(flow_engine, facts) == original_facts
    if removed == 'pdf':
        assert not rows(flow_engine, contents)
    evidence(request.node.nodeid, sent_before_retention=sent, removed=removed,
             recovery=asdict(recovery), actual_pdf_calls=probe.pdf,
             notification_read_calls=probe.notification,
             recovery_pdf_calls=recovery_probe.pdf)


def _reseal_customer_audit(uow,case_id,change):
    """Controlled corruption with a valid chain, so the origin check must reject."""
    from sqlalchemy import select
    from returnops_domain.canonical import decode_document,digest,encode_document
    previous=None
    for row in uow.execute(select(old.audit).where(old.audit.c.case_id==case_id)
                           .order_by(old.audit.c.sequence)).mappings().all():
        event=decode_document(row['body'])
        if event['event_type']=='NOTIFICATION_CUSTOMER_MESSAGE_RECORDED':
            change(event)
        if previous is None:
            event.pop('previous_event_hash',None)
        else:
            event['previous_event_hash']=previous
        unsigned={key:value for key,value in event.items() if key!='event_hash'}
        event['event_hash']=digest({'sequence':row['sequence'],'event':unsigned},'audit/v1')
        uow.execute(update(old.audit).where(old.audit.c.event_id==row['event_id']).values(
            event_hash=event['event_hash'],body=encode_document(event)))
        previous=event['event_hash']
    uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case_id).values(audit_head=previous))


@pytest.mark.parametrize('retained',[False,True])
def test_customer_origin_and_retained_identity_corruption_fail_closed(
        flow_engine,identities,enabled,request,retained):
    from sqlalchemy import delete
    from returnops_domain.customer_uow import CustomerUnitOfWork
    from returnops_domain.errors import FlowError
    from returnops_domain.history import read_revision
    from returnops_domain.manual_target import one
    setup=ready(flow_engine,identities,'reject')
    assert service(flow_engine,identities).send(setup['work_id']).status=='SENT'
    if retained:
        statement=next(row for row in rows(flow_engine,old.history) if row['kind']=='STATEMENT')
        assert RetentionService(flow_engine).remove('STATEMENT',statement['object_id'])
    message=next(row for row in rows(flow_engine,old.history) if row['kind']=='OUTCOME_MESSAGE')
    saved=rows(flow_engine,controls)[0]
    baseline=snapshot(flow_engine)
    faults=('metadata_hash','metadata_time','control_owner','control_missing','fact_hash',
            'work_purpose','accepted_ref','actor','correlation','payload','duplicate_origin')
    for fault in faults:
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            if fault=='metadata_hash':
                uow.execute(update(old.history).where(old.history.c.record_id==message['record_id'])
                            .values(content_sha256='d'*64))
            elif fault=='metadata_time':
                uow.execute(update(old.history).where(old.history.c.record_id==message['record_id'])
                            .values(recorded_at=message['recorded_at']+timedelta(seconds=1)))
            elif fault=='control_owner':
                uow.execute(update(controls).where(controls.c.notification_work_id==saved['notification_work_id'])
                            .values(owner_id=identities.people['customer_b']['principal_id']))
            elif fault=='control_missing':
                uow.execute(delete(controls).where(controls.c.notification_work_id==saved['notification_work_id']))
            elif fault=='fact_hash':
                uow.execute(update(facts).where(facts.c.fact_id==saved['accepted_fact_id']).values(fact_hash='d'*64))
            elif fault=='work_purpose':
                uow.execute(update(life.work).where(life.work.c.work_id==saved['notification_work_id'])
                            .values(purpose='OUTCOME'))
            elif fault=='duplicate_origin':
                from returnops_domain.audit import append_event
                from returnops_domain.notification_customer_origin import customer_payload,history_ref,EVENT
                accepted=one(uow,old.history,record_id=saved['accepted_record_id'])
                fact=one(uow,facts,fact_id=saved['accepted_fact_id'])
                append_event(uow,setup['case_id'],actor={'kind':'SERVICE','component_id':'notification-delivery-v2'},
                    event_type=EVENT,correlation_id=saved['accepted_event_id'],
                    payload=customer_payload(saved,fact,message),
                    object_ids=[message['object_id'],message['record_id']],history_refs=[history_ref(accepted)],
                    now=message['recorded_at'])
            else:
                def corrupt(event):
                    if fault=='accepted_ref':
                        event['history_refs'][0]['object_version']+=1
                    elif fault=='actor':
                        event['actor']={'kind':'SERVICE','component_id':'wrong_component'}
                    elif fault=='correlation':
                        event['correlation_id']='wrong_correlation'
                    else:
                        event['payload_hash']='d'*64
                _reseal_customer_audit(uow,setup['case_id'],corrupt)
            row=one(uow,old.history,record_id=message['record_id'])
            with pytest.raises(FlowError):
                read_revision(uow,row)
        assert snapshot(flow_engine)==baseline,fault
    evidence(request.node.nodeid,retained=retained,faults=list(faults),before=baseline,after=snapshot(flow_engine))


def test_current_get_rejects_orphan_sent_fact_and_origin_when_customer_kind_is_hidden(
        flow_engine,identities,enabled,request):
    from sqlalchemy import delete
    from returnops_domain.customer_uow import CustomerUnitOfWork
    from returnops_domain.founder_integrity import CaseProof
    from returnops_domain.manual_target import one
    setup=ready(flow_engine,identities,'reject')
    assert service(flow_engine,identities).send(setup['work_id']).status=='SENT'
    message=next(row for row in rows(flow_engine,old.history) if row['kind']=='OUTCOME_MESSAGE')
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert uow.execute(update(old.history).where(old.history.c.record_id==message['record_id'])
                           .values(kind='PROCESSING_FAILURE')).rowcount==1
        assert uow.execute(delete(controls).where(controls.c.notification_work_id==setup['work_id'])).rowcount==1
        # Preserve contiguous history and the legal audit chain/reference. The
        # new orphan check, not a broken sequence or FK, must prevent the read.
        CaseProof(uow,one(uow,old.case_heads,case_id=setup['case_id']))
        uow.commit()
    before=_business(flow_engine)
    with _client(flow_engine,identities) as (client,probe):
        response=client.get('/v1/cases/'+setup['case_id'],headers=_headers(identities,'customer_a'))
    assert response.status_code==409
    validate('ErrorEnvelope',response.json())
    assert response.json()['error']['code']=='INVALID_STATE'
    assert _business(flow_engine)==before
    assert len(rows(flow_engine,facts))==1
    evidence(request.node.nodeid,controlled_corruption=True,status=response.status_code,
             before=before,after=_business(flow_engine),notification_read_calls=probe.notification)
