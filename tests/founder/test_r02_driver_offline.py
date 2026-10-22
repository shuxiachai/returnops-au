"""R.02 driver offline checks; no database is used and DATABASE_URL stays unset.

Covers the deterministic cups catalogue, grant rows equal to the tests/lifecycle
provision() rows field-for-field and inserted just before use, the real
provision policies, every Domain call the driver makes bound to the real
signatures, the copied controlled PASS receiver + risk stub inputs, APPROVE
request assembly from a Founder CaseView, the audit chain against the
package's own append/verify functions, primary versus recovery acceptance,
receipt and API-log screening, error frames, and the tools/r02 boundary.
docs/08 R.02 / Gate 1; FR-009..FR-012; NFR-002/NFR-004/NFR-006/NFR-007.
"""
import ast
from copy import deepcopy
from datetime import datetime, timezone
import inspect
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy.sql.dml import Insert, Update

import returnops_api
import returnops_domain
from returnops_api.main import create_app
from returnops_domain import investigation_policy, proposal_policy
from returnops_domain.approval_admission import ApprovalAdmissionService
from returnops_domain.audit import append_event, verify_chain
from returnops_domain.canonical import decode_document, encode_document
from returnops_domain.execution_preparation import ExecutionPreparationService
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.label_artifact import LabelArtifactService
from returnops_domain.label_execution import LabelExecutionService
from returnops_domain.mock_orders import SyntheticCatalogue
from returnops_domain.notification_service import NotificationService
from returnops_domain.pass_review import PassReviewReceiver
from returnops_domain.pass_scenario import SCENARIO
from returnops_domain.preview_service import PreviewService
from returnops_domain.proposal_processor import FixedProposalProcessor
from returnops_domain.registry import TrustedRegistry
from returnops_domain.return_execution import ReturnExecutionService
from returnops_domain.return_label_bridge import ReturnLabelBridge
from returnops_domain.wire import validate

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools' / 'r02'
# The test-only lifecycle helpers are the oracle here; tools/r02 never imports them.
sys.path.insert(0, str(ROOT / 'tests' / 'lifecycle'))
sys.path.insert(0, str(TOOLS))
import api_child  # noqa: E402
import catalogue  # noqa: E402
import driver  # noqa: E402
import grants  # noqa: E402
import scenario  # noqa: E402
import approval_admission_helpers  # noqa: E402
import approve_helpers  # noqa: E402
import create_return_execution_helpers  # noqa: E402
import label_artifact_helpers  # noqa: E402
import label_execution_helpers  # noqa: E402
import notification_helpers  # noqa: E402
import pass_review_helpers  # noqa: E402

STORE, OWNER = driver.STORE, driver.CUSTOMER_ONE
# Pinned on purpose: update it only together with a deliberate change to
# catalogue.py (identities, timestamps, line items, provider or dataset version)
# or to the driver's fixed STORE/CUSTOMER_ONE, and say so in the change record.
EXPECTED_DATASET_SHA256 = '18333dd06fef6fd411d1ac9f71e16f32957fad168b610950c9996488437244bd'
PAIRS = [('review', pass_review_helpers.provision_review),
         ('preview_and_approval', approve_helpers.provision),
         ('execution', approval_admission_helpers.provision_execution),
         ('create_return', create_return_execution_helpers.provision),
         ('generate_label', label_execution_helpers.provision),
         ('label_artifact', label_artifact_helpers.provision),
         ('notification', notification_helpers.provision)]
# The 21 Domain service calls of steps 4-7, by the driver's receiver variable.
SERVICE_CALLS = {
    ('processor', 'prepare'): FixedProposalProcessor, ('processor', 'process'): FixedProposalProcessor,
    ('processor', 'resolve'): FixedProposalProcessor,
    ('receiver', 'accept'): PassReviewReceiver, ('receiver', 'recover'): PassReviewReceiver,
    ('preview', 'accept'): PreviewService, ('preview', 'recover'): PreviewService,
    ('compose_private_approval_admission', 'check'): ApprovalAdmissionService,
    ('preparation', 'prepare'): ExecutionPreparationService,
    ('preparation', 'recover_preparation'): ExecutionPreparationService,
    ('returns', 'execute_prepared_create_return'): ReturnExecutionService,
    ('returns', 'reconcile_create_return'): ReturnExecutionService,
    ('bridge', 'accept_return_source'): ReturnLabelBridge, ('bridge', 'recover_return_source'): ReturnLabelBridge,
    ('labels', 'execute_accepted_label'): LabelExecutionService, ('labels', 'reconcile_label'): LabelExecutionService,
    ('artifacts', 'complete_label_artifact'): LabelArtifactService,
    ('artifacts', 'recover_label_artifact'): LabelArtifactService,
    ('notifications', 'produce_return'): NotificationService, ('notifications', 'send'): NotificationService,
    ('notifications', 'reconcile'): NotificationService,
}
OTHER_CALLS = {('TrustedRegistry', 'provision'): TrustedRegistry, ('IntakeProcessor', 'run_once'): IntakeProcessor,
               ('InvestigationProcessor', 'run_once'): InvestigationProcessor}
CONSTRUCTORS = {'AuthConfig', 'TrustedRegistry', 'IntakeProcessor', 'InvestigationProcessor', 'FixedProposalProcessor'}


def _example(name):
    examples = json.loads((ROOT / 'contracts/v1/examples.json').read_text(encoding='utf-8'))['positive']
    return next(item['value'] for item in examples if item['name'] == name)


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def one(self):
        row, = self.rows
        return row

    def one_or_none(self):
        return self.first()

    def all(self):
        return self.rows


def _capture(monkeypatch, *modules, stateful=False):
    """Record inserts (table, bound values) and commits. Selects find nothing, or
    with stateful=True the last row inserted into the selected table."""
    rows = []

    class CapturingUnitOfWork:
        def __init__(self, engine, *, write, **options):
            assert write is True

        def __enter__(self):
            return self

        def __exit__(self, *failure):
            return False

        def execute(self, statement):
            if isinstance(statement, Insert):
                rows.append((statement.table.name, dict(statement.compile().params)))
                return None
            name = statement.get_final_froms()[0].name
            found = [values for entry in rows if entry != 'COMMIT' for table, values in [entry] if table == name]
            return _Rows(found[-1:] if stateful else [])

        def commit(self):
            rows.append('COMMIT')

    for module in modules:
        monkeypatch.setattr(module, 'CustomerUnitOfWork', CapturingUnitOfWork)
    return rows


class _AuditUnitOfWork:
    """Just enough storage for audit.append_event and audit.verify_chain."""

    def __init__(self, case_id):
        self.head = dict(case_id=case_id, case_version=3, audit_sequence=0, audit_head=None)
        self.records = []

    def execute(self, statement):
        if isinstance(statement, Insert):
            self.records.append(dict(statement.compile().params))
            return None
        if isinstance(statement, Update):
            values = statement.compile().params
            self.head.update(audit_sequence=values['audit_sequence'], audit_head=values['audit_head'])
            return None
        if statement.get_final_froms()[0].name == 'case_heads':
            return _Rows([dict(self.head)])
        return _Rows(sorted(self.records, key=lambda row: row['sequence']))


class _Response:
    headers = {'x-correlation-id': 'corr_r02'}

    def __init__(self, status_code, body=None):
        self.status_code, self.body = status_code, body

    def json(self):
        if self.body is None:
            raise ValueError('not JSON')
        return deepcopy(self.body)


def _envelope(code):
    return {'error': {'code': code, 'message': 'x', 'correlation_id': 'corr_r02', 'retryable': False, 'details': []}}


def _run(tmp_path):
    run = driver.Run(tmp_path / 'r02-output')
    run.tokens, run.case = {'founder': 'founder-token-r02'}, 'case_r02'
    return run


def _imports(path):
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            names.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split('.')[0])
    return names


def test_catalogue_bytes_and_dataset_hash_are_identical_on_every_run():
    first, second = catalogue.document_bytes(STORE, OWNER), catalogue.document_bytes(STORE, OWNER)
    assert first == second and b'\r' not in first and first.endswith(b'\n')
    assert json.loads(first) == catalogue.document(STORE, OWNER)
    metadata = [catalogue.load(STORE, OWNER).metadata for _ in range(2)]
    assert metadata[0] == metadata[1] == SyntheticCatalogue.from_document(json.loads(first)).metadata
    assert metadata[0].dataset_sha256 == EXPECTED_DATASET_SHA256
    assert (metadata[0].dataset_version, metadata[0].provider_id, metadata[0].provider_version) == (
        SCENARIO, 'synthetic_commerce', 'mock-orders-v1')


def test_catalogue_is_schema_valid_and_keeps_the_lifecycle_cups_family():
    snapshot = catalogue.document(STORE, OWNER)['orders'][0]['snapshot']
    assert validate('OrderSnapshot', snapshot, internal=True) == snapshot
    helper = pass_review_helpers.catalogue(SimpleNamespace(
        people={'customer_a': {'store_id': STORE, 'principal_id': OWNER}}))
    record, = helper._records
    original = decode_document(record.snapshot_bytes)
    varying = {'snapshot_id', 'order_id', 'purchased_at', 'retrieved_at'}
    assert {k: v for k, v in snapshot.items() if k not in varying} == {
        k: v for k, v in original.items() if k not in varying}
    assert (record.store_id, record.owner_principal_id, record.order_reference) == (STORE, OWNER, catalogue.ORDER_REFERENCE)
    ours = catalogue.load(STORE, OWNER).metadata
    assert (ours.dataset_version, ours.provider_id, ours.provider_version) == (
        helper.metadata.dataset_version, helper.metadata.provider_id, helper.metadata.provider_version)


@pytest.mark.parametrize('step,helper', PAIRS, ids=[step for step, _ in PAIRS])
def test_grant_rows_equal_the_lifecycle_provision_rows(monkeypatch, step, helper):
    expected = _capture(monkeypatch, sys.modules[helper.__module__])
    helper(object(), SimpleNamespace(people={'founder': {'store_id': STORE}}))
    actual = _capture(monkeypatch, grants)
    summary = getattr(grants, step)(object(), STORE)
    inserted = [row for row in actual if row != 'COMMIT']
    assert actual == expected and inserted and actual[-1] == 'COMMIT' and actual.count('COMMIT') == 1
    assert [row['table'] for row in summary] == [table for table, _ in inserted]
    assert all(values['store_id'] == STORE for _, values in inserted)


def test_driver_inserts_each_grant_just_before_first_use_in_test_order():
    tree = ast.parse((TOOLS / 'driver.py').read_text(encoding='utf-8'))
    used = sorted((node.lineno, node.col_offset, node.attr) for node in ast.walk(tree)
                  if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'grants')
    assert [name for *_, name in used] == list(grants.PROVISION + grants.STEPS)
    first = {}
    for node in ast.walk(tree):
        name = node.attr if isinstance(node, ast.Attribute) else node.id if isinstance(node, ast.Name) else None
        if name is not None:
            first[name] = min(first.get(name, node.lineno), node.lineno)
    grant_line = {name: line for line, _, name in used}
    for before, grant, use in (
            ('build_positive', 'review', 'compose_private_pass_review'),
            ('compose_private_pass_review', 'preview_and_approval', 'compose_private_preview'),
            ('compose_private_preview', 'execution', 'compose_private_approval_admission'),
            ('recover_preparation', 'create_return', 'execute_prepared_create_return'),
            ('recover_return_source', 'generate_label', 'execute_accepted_label'),
            ('execute_accepted_label', 'label_artifact', 'complete_label_artifact'),
            ('recover_label_artifact', 'notification', 'produce_return')):
        assert first[before] < grant_line[grant] < first[use], grant


def test_every_domain_call_of_the_driver_binds_to_the_real_signature():
    """Argument shapes are taken from driver.py itself; extra or missing calls fail."""
    found, constructed = {}, []
    for node in ast.walk(ast.parse((TOOLS / 'driver.py').read_text(encoding='utf-8'))):
        if not isinstance(node, ast.Call):
            continue
        shape = (len(node.args), tuple(kw.arg for kw in node.keywords))
        plain = not any(isinstance(arg, ast.Starred) for arg in node.args) and all(kw.arg for kw in node.keywords)
        function = node.func
        if isinstance(function, ast.Name) and (function.id in CONSTRUCTORS or function.id.startswith('compose_private_')):
            assert plain, function.id
            constructed.append((function.id, shape))
        elif isinstance(function, ast.Attribute):
            owner = function.value
            if isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name):
                owner = owner.func
            if isinstance(owner, ast.Name) and (owner.id, function.attr) in SERVICE_CALLS.keys() | OTHER_CALLS.keys():
                assert plain, function.attr
                found.setdefault((owner.id, function.attr), []).append(shape)
    assert len(SERVICE_CALLS) == 21 and set(found) == SERVICE_CALLS.keys() | OTHER_CALLS.keys()
    for (owner, method), shapes in found.items():
        cls = {**SERVICE_CALLS, **OTHER_CALLS}[(owner, method)]
        for count, keywords in shapes:
            inspect.signature(getattr(cls, method)).bind(object(), *[object()] * count, **dict.fromkeys(keywords))
    assert {name for name, _ in constructed} >= CONSTRUCTORS | {
        'compose_private_pass_review', 'compose_private_preview', 'compose_private_approval_admission',
        'compose_private_execution_preparation', 'compose_private_return_execution',
        'compose_private_return_label_bridge', 'compose_private_label_execution', 'compose_private_label_artifact',
        'compose_private_notification'}
    for name, (count, keywords) in constructed:
        inspect.signature(getattr(driver, name)).bind(*[object()] * count, **dict.fromkeys(keywords))
    inspect.signature(create_app).bind(engine=None, auth_config=None, **api_child.COMPOSITION)


def test_provision_uses_the_real_policies_with_the_demo_arguments(monkeypatch):
    rows = _capture(monkeypatch, investigation_policy, proposal_policy, stateful=True)
    summary = (grants.order_investigation(object(), STORE, catalogue.load(STORE, OWNER))
               + grants.fixed_proposal(object(), STORE))
    assert [row if row == 'COMMIT' else row[0] for row in rows] == [
        'investigation_services', 'investigation_policy_events', 'COMMIT',
        'investigation_provider_grants', 'investigation_policy_events', 'COMMIT', 'lifecycle_authorities', 'COMMIT']
    service, configured, _, grant, granted, _, authority, _ = rows
    assert service[1] == dict(store_id=STORE, service_id=investigation_policy.SERVICE_ID, provider_id='synthetic_commerce',
                              dataset_version=SCENARIO, provider_version='mock-orders-v1',
                              dataset_sha256=EXPECTED_DATASET_SHA256, enabled=True, revision=1)
    assert grant[1] == dict(store_id=STORE, service_id=investigation_policy.SERVICE_ID, provider_id='synthetic_commerce',
                            can_read=True, revision=1)
    assert [decode_document(row[1]['body'])['action'] for row in (configured, granted)] == [
        'SERVICE_CONFIGURED', 'PROVIDER_GRANT_CHANGED']
    assert authority[1] == dict(store_id=STORE, component_id=proposal_policy.COMPONENT, purpose='PROPOSAL',
                                enabled=True, revision=1)
    assert [row['table'] for row in summary] == ['investigation_services', 'investigation_provider_grants',
                                                 'lifecycle_authorities']


def test_controlled_pass_inputs_are_the_unchanged_lifecycle_copies(monkeypatch):
    for name in ('build_positive', 'ControlledPassReviewer'):
        assert inspect.getsource(getattr(scenario, name)) == inspect.getsource(getattr(pass_review_helpers, name))

    def base(material, work, proposal_version, at):
        return {'packet': {'case_id': 'case_r02', 'input_version': 1, 'proposal_id': 'proposal_r02',
                           'model_run': {'prompt_version': 'fixed'}}}

    monkeypatch.setattr(scenario, 'build_fixed_proposal', base)
    monkeypatch.setattr(pass_review_helpers, 'build_fixed_proposal', base)
    material = SimpleNamespace(statements=[{'statement_id': 'statement_r02'}], attachments=[{'evidence_id': 'evidence_r02'}])
    at = datetime(2026, 10, 22, tzinfo=timezone.utc)
    assert scenario.build_positive(material, {}, 2, at) == pass_review_helpers.build_positive(material, {}, 2, at)
    request = {'packet': {'case_id': 'case_r02', 'input_version': 1, 'proposal_id': 'proposal_r02', 'proposal_version': 2,
                          'corpus_version': SCENARIO, 'citations': [{'citation_id': 'synthetic-cups-citation'}]},
               'attachments': [{'evidence_id': 'evidence_r02'}]}
    context = {'run_id': 'run_r02', 'finished_at': '2026-10-22T00:00:00.000000Z'}
    for outcome in ('PASS', 'PASS_WITH_WARNING'):
        ours, theirs = scenario.ControlledPassReviewer(outcome), pass_review_helpers.ControlledPassReviewer(outcome)
        assert ours(request, context, 'review_r02') == theirs(request, context, 'review_r02')
        assert ours.calls == theirs.calls == [request]
    assert scenario.evidence_pdf().startswith(b'%PDF-')


def test_approve_request_is_assembled_only_from_the_founder_case_view():
    view = _example('founder-review-ready-view')
    body = driver.approve_request(view)
    assert body == dict(expected_case_version=view['case_version'], proposal_id=view['current_proposal']['proposal_id'],
                        proposal_version=view['current_proposal']['proposal_version'], decision='APPROVE',
                        reason=driver.REASON, preview_id=view['action_preview']['preview_id'],
                        scope_fingerprint=view['action_preview']['scope_fingerprint'])
    wrong = driver.wrong_fingerprint(body)
    assert validate('FounderDecisionRequest', wrong) == wrong and wrong['scope_fingerprint'] != body['scope_fingerprint']
    assert {k: v for k, v in wrong.items() if k != 'scope_fingerprint'} == {
        k: v for k, v in body.items() if k != 'scope_fingerprint'}
    command = driver.candidate_command(view)
    assert command == view['action_preview']['scope']['commands'][0] and command['type'] == 'CREATE_RETURN'
    command['parameters']['parcel_id'] = 'changed'
    assert view['action_preview']['scope']['commands'][0]['parameters']['parcel_id'] != 'changed'
    for missing in ('action_preview', 'current_proposal'):
        with pytest.raises(driver.Stop):
            driver.approve_request({k: v for k, v in view.items() if k != missing})
    with pytest.raises(driver.Stop):
        driver.approve_request({**view, 'status': 'APPROVED'})
    assert driver.preview_checks(view['action_preview']) and all(driver.preview_checks(view['action_preview']).values())


def test_audit_checks_agree_with_the_package_audit_chain():
    uow, now = _AuditUnitOfWork('case_r02'), datetime(2026, 10, 22, tzinfo=timezone.utc)
    for event_type in ('CASE_CREATED_R02', 'FOUNDER_APPROVE_DENIED', 'FOUNDER_DECISION_ACCEPTED'):
        append_event(uow, 'case_r02', actor={'kind': 'SERVICE', 'component_id': 'r02-test'}, event_type=event_type,
                     correlation_id='corr_r02', payload={'event': event_type}, object_ids=[], history_refs=[], now=now)
    assert verify_chain(uow, 'case_r02')
    items = [decode_document(row['body']) for row in uow.records]  # what the Founder audit pages carry
    assert driver.audit_links(items) and driver.audit_hashes(items)
    tampered = [items[0], {**items[1], 'event_type': 'R02_CHANGED'}, items[2]]
    uow.records[1]['body'] = encode_document(tampered[1])
    assert not verify_chain(uow, 'case_r02')
    assert driver.audit_links(tampered) and not driver.audit_hashes(tampered)
    assert not driver.audit_links(items[1:]) and not driver.audit_links([]) and not driver.audit_hashes([])


def test_history_order_check():
    records = {'DECISION': [{'recorded_sequence': 5}], 'APPROVAL': [{'recorded_sequence': 6}],
               'OPERATION': [{'recorded_sequence': 9}, {'recorded_sequence': 7}], 'NOTIFICATION': [{'recorded_sequence': 12}]}
    assert driver.history_firsts(records) == [5, 6, 7, 12] and driver.history_ordered([5, 6, 7, 12])
    assert not driver.history_ordered(driver.history_firsts({**records, 'NOTIFICATION': []}))
    assert not driver.history_ordered([5, 7, 6, 12])


def test_pages_follow_the_cursor_to_its_end_and_stop_otherwise(tmp_path):
    run, seen = _run(tmp_path), []
    bodies = [dict(items=[1, 2], next_cursor='c1'), dict(items=[3], next_cursor='c2'), dict(items=[])]

    class Http:
        def get(self, path, *, params, headers):
            assert headers == {'Authorization': 'Bearer founder-token-r02'}
            seen.append(dict(params))
            return _Response(200, bodies[len(seen) - 1])

    run.http = Http()
    assert run.pages('/v1/founder/cases/case_r02/history', {'kind': 'DECISION'}) == ([1, 2, 3], 3)
    assert seen == [{'kind': 'DECISION', 'limit': 100}, {'kind': 'DECISION', 'limit': 100, 'cursor': 'c1'},
                    {'kind': 'DECISION', 'limit': 100, 'cursor': 'c2'}]
    run.http = SimpleNamespace(get=lambda path, **options: _Response(200, dict(items=[], next_cursor='again')))
    with pytest.raises(driver.Stop) as stopped:
        run.pages('/v1/founder/cases/case_r02/audit', {})
    assert stopped.value.code == 'PAGINATION_UNBOUNDED'
    run.http = SimpleNamespace(get=lambda path, **options: _Response(409, _envelope('INVALID_STATE')))
    with pytest.raises(driver.Stop) as stopped:
        run.pages('/v1/founder/cases/case_r02/audit', {})
    assert (stopped.value.code, stopped.value.detail['http_status'], stopped.value.detail['error_code']) == (
        'HTTP_UNEXPECTED_STATUS', 409, 'INVALID_STATE')
    assert run.data['steps'][-1]['status'] == 'UNEXPECTED'


def test_expect_maps_status_error_code_and_label(tmp_path):
    run = _run(tmp_path)
    assert run.expect(6, 'negative', _Response(409, _envelope('INVALID_STATE')), 409, error='INVALID_STATE') == \
        _envelope('INVALID_STATE')
    step = run.data['steps'][-1]
    assert (step['status'], step['http_status'], step['error_code'], step['correlation_id']) == (
        'OK', 409, 'INVALID_STATE', 'corr_r02')
    run.expect(6, 'approve', _Response(503, _envelope('INTERNAL_ERROR')), 503, error='INTERNAL_ERROR', label='UNKNOWN')
    assert run.data['steps'][-1]['status'] == 'UNKNOWN'
    with pytest.raises(driver.Stop) as stopped:
        run.expect(6, 'mismatch', _Response(409, _envelope('STALE_CASE_VERSION')), 409, error='INVALID_STATE')
    assert stopped.value.detail == dict(name='mismatch', http_status=409, error_code='STALE_CASE_VERSION')
    with pytest.raises(driver.Stop) as stopped:
        run.expect(6, 'not_json', _Response(502), 202)
    assert stopped.value.detail['error_code'] is None and 'error_code' not in run.data['steps'][-1]


def test_call_accepts_replayed_only_after_one_same_key_recovery(tmp_path):
    run = _run(tmp_path)

    def result(status):
        return SimpleNamespace(status=status, safe_code=None)

    with pytest.raises(driver.Stop) as stopped:
        run.call(7, 'prepare', lambda: result('REPLAYED'), lambda: result('REPLAYED'), ok={'PREPARED'}, replayed=True)
    assert (stopped.value.code, stopped.value.detail['path']) == ('UNEXPECTED_STATUS', 'primary')
    recoveries = []
    value = run.call(7, 'create_return', lambda: result('UNKNOWN'), lambda: recoveries.append(1) or result('REPLAYED'),
                     ok={'COMMITTED'}, replayed=True)
    assert value.status == 'REPLAYED' and recoveries == [1] and run.data['produced_by']['create_return'] == 'recover'
    assert [step['path'] for step in run.data['steps'][-2:]] == ['primary', 'recover']
    with pytest.raises(driver.Stop) as stopped:
        run.call(5, 'action_preview', lambda: result('UNKNOWN'), lambda: result('REPLAYED'), ok={'ACCEPTED'})
    assert stopped.value.code == 'UNEXPECTED_STATUS'
    assert run.call(7, 'notification_send', lambda: result('SENT'), ok={'SENT'}).status == 'SENT'
    assert run.data['produced_by']['notification_send'] == 'primary'
    with pytest.raises(driver.Stop) as stopped:
        run.call(7, 'prepare', lambda: result('DENIED'), lambda: pytest.fail('no recovery after DENIED'), ok={'PREPARED'})
    assert stopped.value.code == 'DENIED'
    run.rows = lambda table, *where: ([dict(notification_work_id='work_r02', state='READY', outcome='RETURN_CREATED',
                                            intent_core=b'private')] if table.name == 'notification_delivery_controls'
                                      else [dict(notification_work_id='work_r02')])
    with pytest.raises(driver.Stop) as stopped:
        run.call(7, 'notification_produce', lambda: result('UNKNOWN'), ok={'READY'}, unknown=run.notification_state)
    assert stopped.value.code == 'UNKNOWN' and stopped.value.detail == dict(
        name='notification_produce', path='primary', lifecycle_notification_work_id='work_r02',
        notification_controls=[dict(notification_work_id='work_r02', state='READY', outcome='RETURN_CREATED')])


def test_receipt_and_api_log_screen_credentials_and_local_directories(tmp_path):
    token, key = 'eyJhbGciOiJIUzI1NiJ9.r02-claims.r02-signature', 'c2lnbmluZy1rZXktZm9yLXIwMi1vbmx5'
    password = 'r02-distinct-password'
    dsn = 'postgresql+psycopg://r02user:' + password + '@localhost/returnops_f02_r02'
    home, private, output = str(Path.home()), str(tmp_path / 'r02-private-x'), str(tmp_path / 'r02-output')
    forbidden = [token, key, dsn, password, output, private, home]
    data = dict(result='PASSED', steps=[dict(step=6, name='approve', correlation_id='corr_r02',
                                             idempotency_key='r02-approve-0011223344556677')])
    path = tmp_path / driver.RECEIPT
    driver.write_receipt(path, data, forbidden)
    content = path.read_bytes()
    assert b'\r' not in content and json.loads(content) == data
    assert all(value.encode() not in content for value in ['Bearer', *forbidden])
    with pytest.raises(FileExistsError):
        driver.write_receipt(path, data, forbidden)
    for leaked in ({'header': 'Bearer x'}, {'token': token}, {'nested': [{'key': key}]}, {'dsn': dsn},
                   {'text': 'a ' + password + ' b'}, {'where': output}, {'below': private + '/x'}, {'home': home}):
        with pytest.raises(driver.ReceiptLeak):
            driver.render_receipt({**data, **leaked}, forbidden)
    windows = 'C:\\r02\\private'  # serialized as C:\\r02\\private
    with pytest.raises(driver.ReceiptLeak):
        driver.render_receipt({'where': windows}, [windows])
    locations = [('<private>', private), ('<home>', home)]
    raw = ('File "' + private + '/x.py", line 1\nhome ' + home + '\n').encode('utf-8')
    assert driver.screen_log(raw, [token, key, dsn, password], locations) == (
        b'File "<private>/x.py", line 1\nhome <home>\n', 2)
    for credential in ('Bearer abc', token, key, dsn, password):
        assert driver.screen_log(b'x ' + credential.encode() + b' y', [token, key, dsn, password], locations) == (None, 0)


def test_unexpected_error_records_only_tools_r02_frames(tmp_path, monkeypatch):
    try:
        driver.candidate_command({})
    except KeyError as error:
        frames = driver.error_frames(error)
    assert frames == [dict(file='driver.py', line=frames[0]['line'], function='candidate_command')]
    monkeypatch.setattr(driver.Run, 'environment', lambda self: driver.candidate_command({}))
    output = tmp_path / 'r02-output'
    output.mkdir()
    assert driver.Run(output).execute() == 'FAILED'
    stop = json.loads((output / driver.RECEIPT).read_text(encoding='ascii'))['stop']
    assert (stop['code'], stop['error_type'], stop['step']) == ('UNEXPECTED_ERROR', 'KeyError', 0)
    assert [frame['function'] for frame in stop['error_frames']] == ['execute', 'candidate_command']
    assert all(set(frame) == {'file', 'line', 'function'} and frame['file'] == 'driver.py' for frame in stop['error_frames'])
    assert 'action_preview' not in json.dumps(stop)


def test_refused_run_without_database_url_writes_only_a_safe_receipt(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    output = tmp_path / 'r02-output'
    assert driver.main(['--output', str(output)]) == 2
    content = (output / driver.RECEIPT).read_text(encoding='ascii')
    receipt = json.loads(content)
    assert receipt['result'] == 'REFUSED' and receipt['stop'] == {'code': 'DATABASE_URL_REJECTED', 'step': 0}
    assert receipt['limitations'] and receipt['steps'] == [] and receipt['checks'] == {}
    assert [path.name for path in output.iterdir()] == [driver.RECEIPT]
    assert 'Bearer' not in content and str(tmp_path) not in content and json.dumps(str(tmp_path))[1:-1] not in content
    assert driver.main(['--output', str(output)]) == 2  # earlier evidence is never overwritten
    assert (output / driver.RECEIPT).read_text(encoding='ascii') == content
    defaults = driver.parser().parse_args(['--output', 'x'])
    assert (defaults.keep_api_log, defaults.allow_existing_data) == (False, False)


def test_api_child_composition_and_environment_come_from_one_place():
    assert api_child.COMPOSITION == dict(enable_processor=False, enable_fixed_proposal=False,
                                         enable_founder_decisions=True)
    assert api_child.CHILD.count('create_app(') == 1 and '**' + repr(api_child.COMPOSITION) in api_child.CHILD
    compile(api_child.CHILD, 'r02-api-child', 'exec')
    source = {'PATH': 'p', 'DATABASE_URL': 'd', 'PGSSLMODE': 'require', 'PYTHONUTF8': '1', 'LC_ALL': 'C',
              'GITHUB_TOKEN': 'drop', 'RETURNOPS_FIXED_PROPOSAL_DEMO': '1', 'RETURNOPS_FOUNDER_DECISIONS': '0',
              'UNRELATED_SECRET': 'drop'}
    env = api_child.child_environment(source, Path('auth.json'), 4242)
    assert set(env) == {'PATH', 'DATABASE_URL', 'PGSSLMODE', 'PYTHONUTF8', 'LC_ALL', 'RETURNOPS_AUTH_FILE',
                        'RETURNOPS_R02_PORT', 'PYTHONDONTWRITEBYTECODE', 'PYTHONIOENCODING', 'PYTHONPATH'}
    assert env['RETURNOPS_R02_PORT'] == '4242' and env['PYTHONPATH'].split(os.pathsep) == [
        str(Path(module.__file__).resolve().parent.parent) for module in (returnops_api, returnops_domain)]


def test_tools_r02_boundary_and_encoding():
    modules = {path.stem for path in TOOLS.glob('*.py')}
    assert modules == {'api_child', 'catalogue', 'demo_identities', 'driver', 'grants', 'scenario'}
    test_modules = {path.stem for folder in ('lifecycle', 'founder') for path in (ROOT / 'tests' / folder).glob('*.py')}
    for path in sorted(path for path in TOOLS.iterdir() if path.is_file()):
        raw = path.read_bytes()
        assert b'\r' not in raw and raw.decode('ascii'), path.name
        if path.suffix == '.py':
            assert not _imports(path) & (test_modules | {'tests'}), path.name
    for package in ('apps/api/returnops_api', 'packages/returnops_domain'):
        for path in (ROOT / package).rglob('*.py'):
            assert not _imports(path) & (modules | {'tools'}), path
            assert 'tools/r02' not in path.read_text(encoding='utf-8'), path
