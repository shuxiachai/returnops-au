"""Synthetic offline ports with real F.03 signature and registry validation."""
import asyncio
import builtins
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import time
from types import SimpleNamespace

from fastapi import FastAPI
import jwt
import psycopg
from sqlalchemy.engine import Engine

from returnops_api import customer_authority as authority_module
from returnops_api import private_founder_decision_http as composition
from returnops_api.founder_decision_http import register_founder_decision_candidate
from returnops_api.security.authentication import AuthConfig
from returnops_api.security.authorization import CaseResource
from returnops_api.security.types import IdentitySnapshot, PrincipalRecord, Role, SessionRecord
from returnops_domain.approve_decision import FounderApproveService, ApproveResult
from returnops_domain.reject_decision import FounderRejectService
from returnops_domain.revision_decision import FounderRevisionService
from returnops_domain.manual_decision import FounderDecisionService


CASE = 'case_boundary'
KEY = 'original.boundary-key:01'
SENTINEL = 'PRIVATE_SENTINEL_JWT_SQL_BODY_AUDIT'
DECISIONS = ('APPROVE', 'REJECT', 'REQUEST_REVISION', 'MANUAL_HANDLING')


def request_body(decision='APPROVE', target='proposal'):
    value = {'expected_case_version': 7, 'decision': decision, 'reason': 'synthetic reason'}
    if target == 'proposal':
        value.update(proposal_id='proposal_boundary', proposal_version=3)
        if decision == 'APPROVE':
            value.update(preview_id='preview_boundary', scope_fingerprint='a' * 64)
    else:
        value[target + '_id'] = target + '_boundary'
    return value


def accepted_receipt(decision='APPROVE', case_id=CASE):
    value = {'case_id': case_id, 'case_version': 19, 'decision_id': 'decision_boundary',
             'decision': decision, 'accepted_at': '2026-10-14T00:00:00Z', 'processing_status': 'ACCEPTED'}
    if decision == 'APPROVE':
        value['approval_id'] = 'approval_boundary'
    return value


def forbidden(*args, **kwargs):
    raise AssertionError('Forbidden actual I/O or Domain effect: ' + SENTINEL)


def install_guards(monkeypatch):
    # The loop is made before these guards: Windows may use a local socketpair
    # while constructing it. Every test request then runs with connect blocked.
    calls = []
    def blocked(label):
        def stop(*args, **kwargs):
            calls.append(label)
            forbidden()
        return stop
    for name in ('connect', 'raw_connection'):
        monkeypatch.setattr(Engine, name, blocked('database.' + name))
    monkeypatch.setattr(psycopg, 'connect', blocked('database.psycopg'))
    monkeypatch.setattr(socket, 'create_connection', blocked('network.create_connection'))
    monkeypatch.setattr(socket.socket, 'connect', blocked('network.connect'))
    monkeypatch.setattr(socket.socket, 'connect_ex', blocked('network.connect_ex'))
    for service in (FounderApproveService, FounderRejectService, FounderRevisionService, FounderDecisionService):
        monkeypatch.setattr(service, 'accept', blocked('domain.' + service.__name__ + '.accept'))
        monkeypatch.setattr(service, 'recover', blocked('domain.' + service.__name__ + '.recover'))
    from returnops_api import customer_config, settings
    monkeypatch.setattr(customer_config, 'load_private_auth_config', blocked('private.auth_config'))
    monkeypatch.setattr(settings.Settings, 'from_environment', blocked('private.settings'))
    if 'returnops_api.main' in sys.modules:
        monkeypatch.setattr(sys.modules['returnops_api.main'], 'load_private_auth_config', blocked('private.main.auth_config'))
    def guarded_open(original):
        def open_file(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                name = Path(os.fsdecode(file)).name.lower()
                if name == '.env' or name.startswith('.env.') and name != '.env.example':
                    blocked('private.environment_file')()
            return original(file, *args, **kwargs)
        return open_file
    monkeypatch.setattr(builtins, 'open', guarded_open(builtins.open))
    monkeypatch.setattr(io, 'open', guarded_open(io.open))
    return calls


class SyntheticRegistry:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.reads = []
        self.after_read = None

    def read_identity(self, principal_id, session_id):
        self.reads.append((principal_id, session_id))
        snapshot = self.snapshot
        if self.after_read is not None:
            self.after_read(self)
        if snapshot is None or (snapshot.principal.principal_id, snapshot.session.session_id) != (principal_id, session_id):
            return None
        return snapshot


class SyntheticResources:
    def __init__(self):
        self.cases = {CASE: CaseResource(CASE, 'store_boundary', 'customer_boundary')}
        self.reads = []

    def get_case(self, case_id):
        self.reads.append(case_id)
        return self.cases.get(case_id)

    get_evidence = get_operation = get_notification = forbidden


class ScriptedPort:
    def __init__(self, harness, decision):
        self.harness, self.decision = harness, decision

    def accept(self, case_id, request, original_key, correlation_id):
        h = self.harness
        assert h.open_contexts == 0 and h.closed_contexts > 0
        h.calls.append((self.decision, case_id, request, original_key, correlation_id))
        if h.accept_error is not None:
            raise h.accept_error
        return h.result if h.result is not None else ApproveResult('ACCEPTED', accepted_receipt(request['decision'], case_id))

    def recover(self, *args, **kwargs):
        self.harness.unexpected_calls.append('scripted.recover')
        forbidden()


class BoundaryHarness:
    def __init__(self, monkeypatch, loop):
        self.loop = loop
        self.config = AuthConfig('boundary-tests', 'boundary-api', secrets.token_bytes(48), leeway_seconds=0)
        self.now = int(time.time())
        self.claims = dict(iss=self.config.issuer, aud=self.config.audience, sub='founder_boundary',
            jti='session_boundary', iat=self.now - 1, nbf=self.now - 1, exp=self.now + 299)
        snapshot = IdentitySnapshot(PrincipalRecord('founder_boundary', Role.FOUNDER, 'store_boundary'),
            SessionRecord('session_boundary', 'founder_boundary', self.now - 1, self.now - 1, self.now + 299))
        self.registry, self.resources = SyntheticRegistry(snapshot), SyntheticResources()
        self.calls, self.factory_headers = [], []
        self.unexpected_calls = []
        self.open_contexts = self.closed_contexts = self.body_reads = 0
        self.result = self.accept_error = self.close_error = self.preflight_error = None
        def engine_connect(*args, **kwargs):
            self.unexpected_calls.append('synthetic_engine.connect')
            forbidden()
        self.engine = SimpleNamespace(connect=engine_connect)
        h = self
        class ReadOnlyUow:
            def __init__(self, engine, *, write):
                assert engine is h.engine and write is False
                self.connection = object()
            def __enter__(self):
                h.open_contexts += 1
                if h.preflight_error is not None:
                    h.open_contexts -= 1
                    raise h.preflight_error
                return self
            def __exit__(self, *exception):
                h.open_contexts -= 1
                h.closed_contexts += 1
                if h.close_error is not None:
                    raise h.close_error
            def commit(self):
                h.unexpected_calls.append('preflight.commit')
                forbidden()
        monkeypatch.setattr(composition, 'CustomerUnitOfWork', ReadOnlyUow)
        monkeypatch.setattr(authority_module, 'SameConnectionIdentities', lambda connection: self.registry)
        monkeypatch.setattr(authority_module, 'SameConnectionResources', lambda connection: self.resources)
        self.production_factory = composition.compose_private_founder_decision_http(self.engine, self.config)
        self.scripted = dict(zip(DECISIONS, (ScriptedPort(self, d) for d in DECISIONS)))
        def factory(authorization):
            self.factory_headers.append(authorization)
            ports = self.production_factory(authorization)
            return replace(ports, approve=self.scripted['APPROVE'], reject=self.scripted['REJECT'],
                           revision=self.scripted['REQUEST_REVISION'], manual=self.scripted['MANUAL_HANDLING'])
        self.factory = factory
        self.app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        register_founder_decision_candidate(self.app, factory)

    def bearer(self, **overrides):
        return 'Bearer ' + jwt.encode({**self.claims, **overrides}, self.config.signing_key, algorithm='HS256')

    def send(self, body=None, *, raw=None, authorization=True, headers=None, query=b'', case_id=CASE, chunks=None):
        value = request_body() if body is None else body
        content = json.dumps(value).encode() if raw is None else raw
        default = [(b'content-type', b'application/json'), (b'idempotency-key', KEY.encode())]
        if authorization is not False:
            default.append((b'authorization', (self.bearer() if authorization is True else authorization).encode()))
        wire_headers = default if headers is None else headers
        events = list(chunks if chunks is not None else [content])
        scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'POST',
            'scheme': 'http', 'path': '/v1/founder/cases/' + case_id + '/decisions',
            'raw_path': ('/v1/founder/cases/' + case_id + '/decisions').encode(), 'query_string': query,
            'root_path': '', 'headers': wire_headers, 'server': ('offline.test', 80), 'client': ('synthetic', 0)}
        messages = []
        async def receive():
            assert self.open_contexts == 0
            self.body_reads += 1
            return {'type': 'http.request', 'body': events.pop(0), 'more_body': bool(events)}
        async def send(message):
            messages.append(message)
        self.loop.run_until_complete(self.app(scope, receive, send))
        start = next(m for m in messages if m['type'] == 'http.response.start')
        payload = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
        return SimpleNamespace(status=start['status'], headers=dict(start['headers']), raw=payload, body=json.loads(payload))


def assert_error(response, status, code):
    assert response.status == status
    error = response.body['error']
    assert error['code'] == code and error['details'] == []
    assert response.headers[b'cache-control'] == b'no-store'
    assert response.headers[b'x-correlation-id'].decode() == error['correlation_id']
    assert SENTINEL.encode() not in response.raw
    if status == 503:
        assert 'original request key' in error['message']
