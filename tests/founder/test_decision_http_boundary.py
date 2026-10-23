"""Offline HTTP preparation evidence; no PG persistence or concurrency claims."""
import asyncio
from dataclasses import replace
import json
from types import SimpleNamespace

from fastapi import FastAPI
import jwt
import pytest

from returnops_api.founder_decision_http import PATH, OPERATION, register_founder_decision_candidate
from returnops_api.security.authorization import CaseResource
from returnops_api.security.errors import SecurityStoreUnavailable
from returnops_api.security.types import Role
from returnops_domain.approve_decision import ApproveResult, FounderApproveService
from returnops_domain.reject_decision import RejectResult, FounderRejectService
from returnops_domain.revision_decision import RevisionResult, FounderRevisionService
from returnops_domain.manual_decision import ManualResult, FounderDecisionService
from returnops_domain.errors import FlowError, ReceiptUnavailable

from decision_boundary_helpers import (BoundaryHarness, CASE, KEY, SENTINEL, DECISIONS,
    accepted_receipt, assert_error, forbidden, install_guards, request_body)


@pytest.fixture
def boundary(monkeypatch):
    loop = asyncio.new_event_loop()
    try:
        with monkeypatch.context() as guarded:
            guard_calls = install_guards(guarded)
            harness = BoundaryHarness(guarded, loop)
            yield harness
            assert guard_calls == [], 'Blocked real I/O/Domain/private-config call occurred'
            assert harness.unexpected_calls == [], 'Recovery, engine connection or preflight commit occurred'
    finally:
        loop.close()


def headers(h, key=KEY, content_type=b'application/json'):
    result = [(b'authorization', h.bearer().encode())]
    if key is not None:
        result.append((b'idempotency-key', key.encode()))
    if content_type is not None:
        result.append((b'content-type', content_type))
    return result


def test_default_app_has_no_decision_route_or_startup_side_effects(boundary):
    from returnops_api.main import create_app
    app = create_app(engine=boundary.engine, auth_config=boundary.config,
                     enable_processor=False, enable_fixed_proposal=False)
    assert not any(getattr(r, 'path', '') == PATH for r in app.routes)
    assert boundary.calls == [] and boundary.open_contexts == boundary.closed_contexts == 0


def test_only_explicit_post_is_registered(boundary):
    assert len(boundary.app.routes) == 1
    route = boundary.app.routes[0]
    assert route.path == PATH and route.methods == {'POST'} and route.operation_id == OPERATION


@pytest.mark.parametrize('collision', ['path', 'operation', 'generated-operation', 'already'])
def test_duplicate_registration_fails_without_partial_route_change(boundary, collision):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None,
                  generate_unique_id_function=lambda route: OPERATION)
    if collision == 'already':
        register_founder_decision_candidate(app, boundary.factory)
    else:
        app.add_api_route(PATH if collision == 'path' else '/other', lambda: None,
                         methods=['POST'], operation_id=OPERATION if collision == 'operation' else
                         None if collision == 'generated-operation' else 'other')
    before = tuple(app.routes)
    with pytest.raises(ValueError):
        register_founder_decision_candidate(app, boundary.factory)
    assert tuple(app.routes) == before


@pytest.mark.parametrize('factory', [None, 0, 'client-controlled', {}])
def test_invalid_trusted_factory_adds_no_route(factory):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    with pytest.raises(ValueError):
        register_founder_decision_candidate(app, factory)
    assert app.routes == []


def test_production_composition_builds_real_services_without_io(boundary):
    authorization = boundary.bearer()
    ports = boundary.production_factory(authorization)
    assert isinstance(ports.approve, FounderApproveService)
    assert isinstance(ports.reject, FounderRejectService)
    assert isinstance(ports.revision, FounderRevisionService)
    assert isinstance(ports.manual, FounderDecisionService)
    for service in (ports.approve, ports.reject, ports.revision, ports.manual):
        assert service.engine is boundary.engine and service.authority.authorization == authorization
        assert service.authority.config is boundary.config
    assert boundary.registry.reads == [] and boundary.open_contexts == 0
    assert ports.preflight(CASE) is None
    assert len(boundary.registry.reads) == 2 and boundary.resources.reads == [CASE]
    assert boundary.open_contexts == 0 and boundary.closed_contexts == 1


@pytest.mark.parametrize('failure', ['missing', 'duplicate', 'malformed', 'bad-signature', 'issuer', 'audience',
    'expired', 'revoked', 'disabled', 'unregistered', 'customer', 'cross-store', 'missing-case', 'unavailable-case'])
def test_real_f03_rejects_before_any_body_read(boundary, failure):
    h = boundary
    authorization = True
    wire = None
    expected = (401, 'UNAUTHENTICATED')
    if failure == 'missing':
        authorization = False
    elif failure == 'duplicate':
        wire = headers(h) + [(b'authorization', h.bearer().encode())]
    elif failure == 'malformed':
        authorization = 'Bearer ' + SENTINEL
    elif failure == 'bad-signature':
        authorization = 'Bearer ' + jwt.encode(h.claims, b'x' * 48, algorithm='HS256')
    elif failure in {'issuer', 'audience'}:
        authorization = h.bearer(**({'iss': 'wrong'} if failure == 'issuer' else {'aud': 'wrong'}))
    elif failure == 'expired':
        authorization = h.bearer(iat=h.now - 400, nbf=h.now - 400, exp=h.now - 1)
    elif failure == 'revoked':
        h.registry.snapshot = replace(h.registry.snapshot, session=replace(h.registry.snapshot.session, revoked=True))
    elif failure == 'disabled':
        h.registry.snapshot = replace(h.registry.snapshot, principal=replace(h.registry.snapshot.principal, enabled=False))
    elif failure == 'unregistered':
        h.registry.snapshot = None
    elif failure == 'customer':
        h.registry.snapshot = replace(h.registry.snapshot, principal=replace(h.registry.snapshot.principal, role=Role.CUSTOMER))
        authorization = h.bearer(role='FOUNDER', store_id='store_boundary')
        expected = (403, 'FORBIDDEN')
    else:
        if failure == 'cross-store':
            h.resources.cases[CASE] = CaseResource(CASE, 'foreign_store', 'customer_boundary')
        elif failure == 'missing-case':
            h.resources.cases.clear()
        else:
            h.resources.cases[CASE] = replace(h.resources.cases[CASE], available=False)
        expected = (404, 'NOT_FOUND')
    response = h.send(raw=SENTINEL.encode(), authorization=authorization, headers=wire)
    assert_error(response, *expected)
    assert h.body_reads == 0 and h.calls == [] and h.open_contexts == 0


def test_current_registry_change_is_not_cached_between_authorizations(boundary):
    h = boundary
    def change(registry):
        registry.snapshot = replace(registry.snapshot, principal=replace(registry.snapshot.principal, store_id='store_changed'))
        h.resources.cases[CASE] = replace(h.resources.cases[CASE], store_id='store_changed')
        registry.after_read = None
    h.registry.after_read = change
    assert_error(h.send(), 401, 'UNAUTHENTICATED')
    assert h.body_reads == 0 and h.calls == []


@pytest.mark.parametrize('where', ['enter', 'close', 'registry'])
def test_dependency_or_close_failure_prevents_body_and_dispatch(boundary, where):
    if where == 'enter':
        boundary.preflight_error = RuntimeError(SENTINEL)
    elif where == 'close':
        boundary.close_error = RuntimeError(SENTINEL)
    else:
        def fail(*args):
            raise SecurityStoreUnavailable(SENTINEL)
        boundary.registry.read_identity = fail
    assert_error(boundary.send(), 503, 'INTERNAL_ERROR')
    assert boundary.body_reads == 0 and boundary.calls == []


@pytest.mark.parametrize('decision,target', [(d, 'proposal') for d in DECISIONS] +
    [('MANUAL_HANDLING', 'processing_failure'), ('MANUAL_HANDLING', 'order_lookup_block')])
def test_legal_requests_dispatch_once_and_preserve_original_inputs(boundary, decision, target):
    value = request_body(decision, target)
    value['reason'] = '  preserved reason  '
    response = boundary.send(value)
    assert response.status == 202 and response.body == accepted_receipt(decision)
    assert response.headers[b'cache-control'] == b'no-store'
    assert len(boundary.calls) == 1
    choice, case_id, actual, key, correlation = boundary.calls[0]
    assert (choice, case_id, actual, key) == (decision, CASE, value, KEY)
    assert correlation == response.headers[b'x-correlation-id'].decode()
    assert boundary.body_reads == 1 and boundary.closed_contexts == 1


@pytest.mark.parametrize('field', ['actor', 'principal_id', 'store_id', 'role', 'grant', 'approval_id', 'command',
    'provider', 'authorization', 'correlation_id', 'request_ports_factory', 'preflight', 'unexpected'])
def test_client_authority_and_unknown_fields_are_rejected_not_stripped(boundary, field):
    value = request_body()
    value[field] = SENTINEL
    assert_error(boundary.send(value), 422, 'VALIDATION_ERROR')
    assert boundary.calls == []


@pytest.mark.parametrize('invalid', [
    {'expected_case_version': 0}, {'expected_case_version': -1}, {'expected_case_version': True},
    {'expected_case_version': 1.5}, {'expected_case_version': 9007199254740992}, {'expected_case_version': '7'},
    {'proposal_version': False}, {'proposal_version': 0}, {'proposal_version': 2.2},
    {'proposal_id': 'bad/id'}, {'reason': ''}, {'reason': None}, {'reason': 3}, {'reason': 'x' * 2001},
    {'decision': 'EXECUTE'}, {'decision': False}, {'preview_id': None}, {'scope_fingerprint': 'bad'},
    {'processing_failure_id': 'failure_boundary'}, {'order_lookup_block_id': 'block_boundary'},
])
def test_invalid_fields_and_mixed_targets_do_not_dispatch(boundary, invalid):
    assert_error(boundary.send({**request_body(), **invalid}), 422, 'VALIDATION_ERROR')
    assert boundary.calls == []


@pytest.mark.parametrize('missing', ['expected_case_version', 'proposal_id', 'proposal_version', 'decision', 'reason',
    'preview_id', 'scope_fingerprint'])
def test_required_proposal_and_approve_fields(boundary, missing):
    value = request_body()
    del value[missing]
    assert_error(boundary.send(value), 422, 'VALIDATION_ERROR')
    assert boundary.calls == []


@pytest.mark.parametrize('decision', ['REJECT', 'REQUEST_REVISION', 'MANUAL_HANDLING'])
@pytest.mark.parametrize('extra', ['preview_id', 'scope_fingerprint'])
def test_other_decisions_forbid_preview_fields(boundary, decision, extra):
    value = request_body(decision)
    value[extra] = 'preview_boundary' if extra == 'preview_id' else 'a' * 64
    assert_error(boundary.send(value), 422, 'VALIDATION_ERROR')
    assert boundary.calls == []


@pytest.mark.parametrize('target', ['processing_failure', 'order_lookup_block'])
@pytest.mark.parametrize('decision', ['APPROVE', 'REJECT', 'REQUEST_REVISION'])
def test_nonproposal_targets_forbid_other_decisions(boundary, target, decision):
    assert_error(boundary.send(request_body(decision, target)), 422, 'VALIDATION_ERROR')
    assert boundary.calls == []


def test_two_nonproposal_targets_are_not_a_single_target(boundary):
    value = request_body('MANUAL_HANDLING', 'processing_failure')
    value['order_lookup_block_id'] = 'block_boundary'
    assert_error(boundary.send(value), 422, 'VALIDATION_ERROR')
    assert boundary.calls == []


@pytest.mark.parametrize('raw', [b'', b'null', b'[]', b'"body"', b'42', b'\xff', b'{"x":NaN}',
    b'{"x":Infinity}', b'{"x":1,"x":2}', b'{"x":{"nested":1,"nested":2}}', b'{', b'[' * 1100])
def test_strict_json_decoder_rejects_bad_documents(boundary, raw):
    assert_error(boundary.send(raw=raw), 422, 'VALIDATION_ERROR')
    assert boundary.calls == []


@pytest.mark.parametrize('version', ['7.0', '7e0'])
def test_exact_json_integer_normalization_is_preserved(boundary, version):
    raw = json.dumps(request_body()).replace('"expected_case_version": 7', '"expected_case_version": ' + version).encode()
    assert boundary.send(raw=raw).status == 202
    assert type(boundary.calls[0][2]['expected_case_version']) is int


@pytest.mark.parametrize('key', [None, '', 'short', 'has space key', 'x' * 129, 'bad/key/value'])
def test_invalid_or_missing_key_rejected_before_body(boundary, key):
    assert_error(boundary.send(headers=headers(boundary, key)), 422, 'VALIDATION_ERROR')
    assert boundary.body_reads == 0 and boundary.calls == []


@pytest.mark.parametrize('key', ['k' * 8, 'K.9_:-' + 'a' * 122, 'abc.def:ghi-jkl_01'])
def test_key_length_boundaries_are_accepted_and_forwarded_unchanged(boundary, key):
    assert 8 <= len(key) <= 128
    response = boundary.send(headers=headers(boundary, key))
    assert response.status == 202 and len(boundary.calls) == 1 and boundary.calls[0][3] == key
    assert boundary.body_reads == 1


@pytest.mark.parametrize('raw_key', [b'k\xc3\xa9y-00000000', b'key\x00padding00', b'key\x7fpadding00',
                                     b'\xe2\x80\x8bzero-width-key', b'key-with-tab\t0000'])
def test_non_ascii_or_control_bytes_in_key_rejected_before_body(boundary, raw_key):
    wire = [(b'authorization', boundary.bearer().encode()), (b'idempotency-key', raw_key),
            (b'content-type', b'application/json')]
    assert_error(boundary.send(headers=wire), 422, 'VALIDATION_ERROR')
    assert boundary.body_reads == 0 and boundary.calls == []


@pytest.mark.parametrize('duplicate', [b'idempotency-key', b'content-type'])
def test_duplicate_non_auth_headers_rejected(boundary, duplicate):
    wire = headers(boundary)
    wire.append((duplicate, KEY.encode() if duplicate == b'idempotency-key' else b'application/json'))
    assert_error(boundary.send(headers=wire), 422, 'VALIDATION_ERROR')
    assert boundary.body_reads == 0 and boundary.calls == []


@pytest.mark.parametrize('query', [b'actor=founder', b'x=1&x=2', b'key=' + KEY.encode()])
def test_query_parameters_are_never_authority_or_command_inputs(boundary, query):
    assert_error(boundary.send(query=query), 422, 'VALIDATION_ERROR')
    assert boundary.body_reads == 0 and boundary.calls == []


@pytest.mark.parametrize('content_type', [None, b'text/plain', b'application/octet-stream'])
def test_content_type_is_checked_before_stream(boundary, content_type):
    assert_error(boundary.send(headers=headers(boundary, content_type=content_type)), 422, 'VALIDATION_ERROR')
    assert boundary.body_reads == 0 and boundary.calls == []


def test_streaming_size_limit_stops_without_dispatch(boundary):
    assert_error(boundary.send(chunks=[b' ' * (4 * 1024 * 1024), b'x']), 422, 'VALIDATION_ERROR')
    assert boundary.body_reads == 2 and boundary.calls == []


def test_exact_size_limit_remains_valid_json(boundary):
    body = json.dumps(request_body()).encode()
    assert boundary.send(raw=body + b' ' * (4 * 1024 * 1024 - len(body))).status == 202
    assert len(boundary.calls) == 1


@pytest.mark.parametrize('code,status', [('UNAUTHENTICATED', 401), ('FORBIDDEN', 403), ('NOT_FOUND', 404),
    ('STALE_CASE_VERSION', 409), ('IDEMPOTENCY_CONFLICT', 409), ('INVALID_STATE', 409),
    ('VALIDATION_ERROR', 422), ('INTERNAL_ERROR', 503)])
def test_supported_denial_codes_have_static_mapping(boundary, code, status):
    boundary.result = RejectResult('DENIED', safe_code=code, audit='UNKNOWN')
    assert_error(boundary.send(), status, code)
    assert len(boundary.calls) == 1


@pytest.mark.parametrize('audit', ['RECORDED', 'NOT_RECORDED', 'UNKNOWN', 'NOT_ATTEMPTED'])
def test_supported_audit_vocabulary_preserves_denial_without_recovery(boundary, audit):
    boundary.result = RejectResult('DENIED', safe_code='INVALID_STATE', audit=audit)
    assert_error(boundary.send(), 409, 'INVALID_STATE')
    assert len(boundary.calls) == 1


@pytest.mark.parametrize('status', ['ACCEPTED', 'DENIED'])
@pytest.mark.parametrize('audit', ['made-up', None, {}, False, 1])
def test_unknown_or_nonstring_audit_values_fail_safely(boundary, status, audit):
    boundary.result = ApproveResult(status, accepted_receipt() if status == 'ACCEPTED' else None,
        safe_code=None if status == 'ACCEPTED' else 'INVALID_STATE', audit=audit)
    assert_error(boundary.send(), 503, 'INTERNAL_ERROR')
    assert len(boundary.calls) == 1


@pytest.mark.parametrize('status', ['ACCEPTED', 'DENIED'])
def test_audit_object_cannot_impersonate_a_supported_string(boundary, status):
    class AuditLookalike:
        def __eq__(self, other):
            return True
    boundary.result = ApproveResult(status, accepted_receipt() if status == 'ACCEPTED' else None,
        safe_code=None if status == 'ACCEPTED' else 'INVALID_STATE', audit=AuditLookalike())
    assert_error(boundary.send(), 503, 'INTERNAL_ERROR')


@pytest.mark.parametrize('result_type', [ApproveResult, RejectResult, RevisionResult, ManualResult])
def test_all_actual_result_shapes_are_supported(boundary, result_type):
    boundary.result = result_type('ACCEPTED', accepted_receipt())
    assert boundary.send().status == 202
    assert len(boundary.calls) == 1


@pytest.mark.parametrize('result', [
    SimpleNamespace(status='made-up'), SimpleNamespace(status=None), {}, object(),
    ApproveResult('DENIED', safe_code='STALE_PROPOSAL'), ApproveResult('DENIED', safe_code='APPROVAL_EXPIRED'),
    ApproveResult('DENIED', safe_code=SENTINEL), ApproveResult('DENIED', safe_code=None),
    ApproveResult('DENIED', safe_code=['INVALID_STATE']), ApproveResult('DENIED', receipt=accepted_receipt(), safe_code='INVALID_STATE'),
    ApproveResult('DENIED', safe_code='INVALID_STATE', audit={}),
    ApproveResult('ACCEPTED', accepted_receipt(), safe_code='INVALID_STATE'),
    ApproveResult('ACCEPTED', accepted_receipt(), audit='UNKNOWN'),
    SimpleNamespace(status='ACCEPTED', receipt=accepted_receipt()),
])
def test_unknown_codes_and_malformed_wrappers_fail_safely(boundary, result):
    boundary.result = result
    assert_error(boundary.send(), 503, 'INTERNAL_ERROR')
    assert len(boundary.calls) == 1


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'wrong-case', 'wrong-decision', 'missing-approval',
    'bad-version', 'bool-version', 'bad-time', 'bad-status', 'not-object', 'null'])
def test_malformed_or_mismatched_receipts_are_never_success(boundary, mutation):
    receipt = accepted_receipt()
    if mutation == 'missing':
        del receipt['decision_id']
    elif mutation == 'extra':
        receipt['private'] = SENTINEL
    elif mutation == 'wrong-case':
        receipt['case_id'] = 'case_foreign'
    elif mutation == 'wrong-decision':
        receipt['decision'] = 'REJECT'
        del receipt['approval_id']
    elif mutation == 'missing-approval':
        del receipt['approval_id']
    elif mutation in {'bad-version', 'bool-version'}:
        receipt['case_version'] = 0 if mutation == 'bad-version' else True
    elif mutation == 'bad-time':
        receipt['accepted_at'] = 'invalid'
    elif mutation == 'bad-status':
        receipt['processing_status'] = 'COMPLETED'
    elif mutation == 'not-object':
        receipt = []
    else:
        receipt = None
    boundary.result = ApproveResult('ACCEPTED', receipt)
    assert_error(boundary.send(), 503, 'INTERNAL_ERROR')
    assert len(boundary.calls) == 1


@pytest.mark.parametrize('decision', ['REJECT', 'REQUEST_REVISION', 'MANUAL_HANDLING'])
def test_nonapprove_receipt_cannot_smuggle_approval(boundary, decision):
    receipt = accepted_receipt(decision)
    receipt['approval_id'] = 'approval_smuggled'
    boundary.result = ManualResult('ACCEPTED', receipt)
    assert_error(boundary.send(request_body(decision)), 503, 'INTERNAL_ERROR')


@pytest.mark.parametrize('code', [None, 'FORBIDDEN', 'INVALID_STATE', SENTINEL])
@pytest.mark.parametrize('audit', ['NOT_ATTEMPTED', 'UNKNOWN', SENTINEL])
def test_unknown_never_uses_receipt_or_retries(boundary, code, audit):
    class Unknown:
        status = 'UNKNOWN'
        safe_code = code
        @property
        def receipt(self):
            raise AssertionError('UNKNOWN receipt must not be consumed')
    value = Unknown()
    value.audit = audit
    boundary.result = value
    assert_error(boundary.send(), 503, 'INTERNAL_ERROR')
    assert len(boundary.calls) == 1


@pytest.mark.parametrize('error_kind', ['exception', 'flow-custom', 'unsupported-flow', 'receipt-unavailable'])
def test_exceptions_are_normalized_without_private_message_or_status(boundary, error_kind):
    expected = (503, 'INTERNAL_ERROR')
    if error_kind == 'exception':
        error = RuntimeError(SENTINEL)
    elif error_kind == 'receipt-unavailable':
        error = ReceiptUnavailable()
        expected = (409, 'INVALID_STATE')
    else:
        error = FlowError('FORBIDDEN', status=200)
        error.message = SENTINEL
        if error_kind == 'unsupported-flow':
            error.code = 'STALE_PROPOSAL'
        else:
            expected = (403, 'FORBIDDEN')
    boundary.accept_error = error
    response = boundary.send()
    assert_error(response, *expected)
    assert b'previously accepted' not in response.raw and len(boundary.calls) == 1


def test_repeated_key_is_forwarded_twice_without_http_recovery_cache(boundary):
    first, second = boundary.send(), boundary.send()
    assert first.status == second.status == 202
    assert len(boundary.calls) == 2
    assert [call[3] for call in boundary.calls] == [KEY, KEY]
    assert boundary.calls[0][4] != boundary.calls[1][4]
    assert first.body == second.body
