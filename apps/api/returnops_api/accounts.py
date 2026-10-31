"""Customer self-registration and password sign-in (31 October 2026; FR-001, FR-012; NFR-002, NFR-009).

Off unless `demo.py serve --accounts`, which names the private credentials file written by
`demo.py provision` next to auth.json. Registration creates only a CUSTOMER of that file's
store (TrustedRegistry.register_customer); Founders exist only through `demo.py provision`.
Password hashes (scrypt) stay in that private file, so the frozen schema is unchanged; a
deployment that resets its database resets the file with it (tools/railway/start.py,
demo.ps1 fresh). A sign-in issues a new 899 s session the way provision does; the token is
then verified like any other (security/authentication.py). Neither route is in contract v1.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
import jwt
from fastapi import Request
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from returnops_domain import customer_tables as t
from returnops_domain.audit import identifier
from returnops_domain.errors import FlowError
from returnops_domain.registry import TrustedRegistry
from returnops_domain.wire import blank, validate
from .customer_http import _json_body, safe_json

SESSION_SECONDS = 899
PASSWORD_MIN, PASSWORD_MAX = 8, 128
_SCRYPT = {'n': 2**14, 'r': 8, 'p': 1}


class AccountError(FlowError):
    """A FlowError with a sentence for this one case, as ReceiptUnavailable does."""
    def __init__(self, code, message, *, status=None):
        super().__init__(code, status=status)
        self.message = message
        self.args = (message,)


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, dklen=32, **_SCRYPT)
    return 'scrypt$%d$%d$%d$%s$%s' % (_SCRYPT['n'], _SCRYPT['r'], _SCRYPT['p'],
        base64.b64encode(salt).decode('ascii'), base64.b64encode(digest).decode('ascii'))


def verify_password(password, stored):
    try:
        name, n, r, p, salt, digest = stored.split('$')
        if name != 'scrypt' or (int(n), int(r), int(p)) != (_SCRYPT['n'], _SCRYPT['r'], _SCRYPT['p']):
            return False
        expected = base64.b64decode(digest, validate=True)
        actual = hashlib.scrypt(password.encode('utf-8'), salt=base64.b64decode(salt, validate=True),
                                dklen=len(expected), **_SCRYPT)
    except (AttributeError, ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Compared against when the username is unknown, so a miss costs the same time as a hit.
_UNKNOWN = hash_password(secrets.token_urlsafe(24))


def _private_replace(path, value):
    """Write a sibling with mode 0600 and swap it in, so a reader never sees half a file."""
    temporary = path.with_name(path.name + '.' + secrets.token_hex(6) + '.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as output:
            json.dump(value, output, ensure_ascii=True, sort_keys=True)
            output.write('\n')
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


class CredentialStore:
    """The private credentials file: {"version": 1, "store_id": ..., "accounts": {id: hash}}."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        if not self.path.is_absolute():
            raise ValueError('Use an absolute private credentials file.')
        self.store_id = self._read()['store_id']

    def _read(self):
        value = json.loads(self.path.read_text(encoding='utf-8'))
        if (not isinstance(value, dict) or set(value) != {'version', 'store_id', 'accounts'} or value['version'] != 1
                or not isinstance(value['accounts'], dict)):
            raise ValueError('Use the credentials file written by demo.py provision.')
        validate('Id', value['store_id'])
        return value

    def hash_for(self, principal_id):
        with self._lock:
            stored = self._read()['accounts'].get(principal_id)
        return stored if isinstance(stored, str) else None

    def add(self, principal_id, password_hash):
        with self._lock:
            value = self._read()
            # Taken in any letter case: `Synthetic_Founder` must not sit beside `synthetic_founder`.
            if principal_id.lower() in {name.lower() for name in value['accounts']}:
                raise FlowError('INVALID_STATE')
            value['accounts'][principal_id] = password_hash
            _private_replace(self.path, value)

    def remove(self, principal_id):
        with self._lock:
            value = self._read()
            if value['accounts'].pop(principal_id, None) is not None:
                _private_replace(self.path, value)


def new_credentials_file(path, store_id, passwords):
    """For demo.py provision: hashes of the generated passwords of the provisioned people."""
    value = {'version': 1, 'store_id': store_id,
             'accounts': {principal: hash_password(password) for principal, password in passwords.items()}}
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as output:
        json.dump(value, output, ensure_ascii=True, sort_keys=True)
        output.write('\n')


class AttemptLimiter:
    """At most `limit` events per key in a sliding window; in this process only."""

    def __init__(self, limit, window_seconds, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window_seconds, clock
        self._events = {}
        self._lock = threading.Lock()

    def _recent(self, key):
        cutoff = self.clock() - self.window
        events = [moment for moment in self._events.get(key, []) if moment > cutoff]
        if events:
            self._events[key] = events
        else:
            self._events.pop(key, None)
        return events

    def blocked(self, key):
        with self._lock:
            return len(self._recent(key)) >= self.limit

    def record(self, key):
        with self._lock:
            self._recent(key)
            self._events.setdefault(key, []).append(self.clock())

    def clear(self, key):
        with self._lock:
            self._events.pop(key, None)


def _credentials(value):
    if not isinstance(value, dict) or set(value) != {'username', 'password'}:
        raise FlowError('VALIDATION_ERROR')
    username, password = value['username'], value['password']
    if not isinstance(username, str) or not isinstance(password, str):
        raise FlowError('VALIDATION_ERROR')
    return username, password


def _session_times():
    now = int(time.time())
    # The same window as demo.py provision: 900 s from issue, the most the verifier accepts.
    return {'session_id': identifier('session'), 'issued_at': now - 1, 'not_before': now - 1,
            'expires_at': now + SESSION_SECONDS}


def _token(config, principal_id, session):
    claims = {'iss': config.issuer, 'aud': config.audience, 'sub': principal_id, 'jti': session['session_id'],
              'iat': session['issued_at'], 'nbf': session['not_before'], 'exp': session['expires_at']}
    return jwt.encode(claims, config.signing_key, algorithm='HS256')


def _signed_in(token, principal_id, role):
    return {'access_token': token, 'token_type': 'Bearer', 'expires_in': SESSION_SECONDS,
            'principal_id': principal_id, 'role': role}


WRONG_CREDENTIALS = 'The username or password is not correct.'


def register_account_routes(app, store):
    sign_ins = AttemptLimiter(5, 300)
    registrations = AttemptLimiter(30, 600)

    def register(config, engine, username, password):
        if registrations.blocked('all'):
            raise AccountError('INVALID_STATE', 'Too many accounts were created just now. Try again in a few minutes.', status=429)
        try:
            validate('Principal', {'principal_id': username, 'role': 'CUSTOMER'})
        except FlowError:
            raise AccountError('VALIDATION_ERROR', 'Choose a username of 3 to 80 letters, digits, - or _, '
                               'starting with a letter or digit.') from None
        if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX or blank(password):
            raise AccountError('VALIDATION_ERROR', 'Choose a password of 8 to 128 characters.')
        taken = AccountError('INVALID_STATE', 'That username is already taken. Choose another one.')
        try:
            store.add(username, hash_password(password))
        except FlowError:
            raise taken from None
        session = _session_times()
        try:
            TrustedRegistry(engine).register_customer(username, store.store_id, session)
        except BaseException as error:
            store.remove(username)
            if isinstance(error, FlowError) and error.code == 'INVALID_STATE':
                raise taken from None
            if isinstance(error, FlowError) and error.code == 'FORBIDDEN':
                raise AccountError('FORBIDDEN', 'New accounts cannot be created for this shop right now.') from None
            raise
        registrations.record('all')
        return 201, _signed_in(_token(config, username, session), username, 'CUSTOMER')

    def sign_in(config, engine, username, password):
        key = username.casefold()
        if sign_ins.blocked(key):
            raise AccountError('INVALID_STATE', 'Too many sign-in attempts for this username. Wait a few minutes.', status=429)
        stored = store.hash_for(username) if len(username) <= 80 else None
        matched = verify_password(password, stored or _UNKNOWN) and stored is not None
        if not matched:
            sign_ins.record(key)
            raise AccountError('UNAUTHENTICATED', WRONG_CREDENTIALS)
        session = _session_times()
        try:
            TrustedRegistry(engine).register_session(username, session['session_id'], session['issued_at'],
                                                     session['not_before'], session['expires_at'])
        except FlowError as error:
            if error.code in {'INVALID_STATE', 'VALIDATION_ERROR'}:
                raise AccountError('UNAUTHENTICATED', WRONG_CREDENTIALS) from None
            raise
        sign_ins.clear(key)
        with engine.connect() as connection:
            role = connection.execute(select(t.principals.c.role).where(t.principals.c.principal_id == username)).scalar_one()
        return 200, _signed_in(_token(config, username, session), username, role)

    async def respond(request, operation):
        correlation = identifier('corr')
        try:
            config = request.app.state.auth_config
            if config is None:
                raise FlowError('INTERNAL_ERROR')
            username, password = _credentials(await _json_body(request))
            status, body = await run_in_threadpool(operation, config, request.app.state.engine, username, password)
            return safe_json(body, status, correlation=correlation)
        except FlowError as error:
            return safe_json(error.envelope(correlation), error.status, correlation=correlation)
        except Exception:
            return safe_json(FlowError().envelope(correlation), 503, correlation=correlation)

    @app.post('/v1/auth/register')
    async def register_route(request: Request):
        return await respond(request, register)

    @app.post('/v1/auth/login')
    async def login_route(request: Request):
        return await respond(request, sign_in)
