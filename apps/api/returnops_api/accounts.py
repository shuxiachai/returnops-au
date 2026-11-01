"""Customer self-registration and password sign-in (31 October 2026; FR-001, FR-012; NFR-002, NFR-009).

Off unless `demo.py serve --accounts`, which names the private credentials file written by
`demo.py provision` next to auth.json. Registration creates only a CUSTOMER of that file's
store (TrustedRegistry.register_customer); Founders exist only through `demo.py provision`.
Password hashes (scrypt) stay in that private file, so the frozen schema is unchanged; a
deployment that resets its database resets the file with it (tools/railway/start.py,
demo.ps1 fresh). A sign-in issues a new 899 s session the way provision does; the token is
then verified like any other (security/authentication.py). Neither route is in contract v1.

Hardened the same day after an independent review: a name that exists, or looks like one
that exists, is refused before any password is written; a name being registered cannot sign
in; a sign-in must belong to the file's store; inputs are bounded before any work; scrypt
runs at most two at a time; the limiters hold a bounded number of keys and check and count
in one step; a registration whose outcome is unknown keeps its password if the account exists.

Runtime review of the same evening: a body over 4 KiB or slower than 10 s is refused before
it is decoded; at most four sign-in or registration requests use worker threads at once
(more are refused at once as busy), so a flood cannot hold the threads the other routes
need; a name signs in as the account's own spelling, as registration treats `Alice`,
`alice` and `a-lice` as one name.

1 November 2026 (the lead: fifteen minutes is too short): a password sign-in stays signed in
for an hour. Every key still lasts at most 899 s, the most the verifier and the frozen schema
accept (docs/18), so `POST /v1/auth/renew` hands out the next key: only for a key that a
password sign-in or a renewal of one issued in this process, only in the last five minutes of
that key, and never past one hour after the sign-in. An access key from `demo.py provision` is
not renewed. Not in contract v1.
"""
from __future__ import annotations
import asyncio
import base64
import functools
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
import anyio
import jwt
from fastapi import Request
from returnops_domain.audit import identifier
from returnops_domain.errors import FlowError
from returnops_domain.registry import TrustedRegistry, canonical_id
from returnops_domain.wire import blank, decode_json_document, validate
from .customer_authority import SameConnectionIdentities
from .customer_http import one_header, safe_json
from .security.authentication import Authenticator
from .security.errors import SecurityError

SESSION_SECONDS = 899
# A password sign-in is renewed for this long, in the last RENEW_BEFORE_SECONDS of each key.
RENEW_WINDOW_SECONDS = 3600
RENEW_BEFORE_SECONDS = 300
RENEWABLE_MAX_KEYS = 10000
PASSWORD_MIN, PASSWORD_MAX = 8, 128
_SCRYPT = {'n': 2**14, 'r': 8, 'p': 1}
# About 16 MiB and 40 ms of CPU each, so no more than this many run at once.
HASH_SLOTS = 2
HASH_WAIT_SECONDS = 0.5
# A name, a password and JSON escapes fit in well under 4 KiB; anything larger is refused unread.
MAX_AUTH_BODY_BYTES = 4096
AUTH_BODY_SECONDS = 10
# Worker threads the auth routes may use at once; the shared pool keeps the rest.
AUTH_THREADS = 4
BUSY = 'Sign-in is busy right now. Try again in a moment.'


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

    def entry_for(self, principal_id):
        """(the account's own spelling, its hash) for this name in any letter case, '-' or '_'."""
        wanted = canonical_id(principal_id)
        with self._lock:
            accounts = self._read()['accounts']
        for name, stored in accounts.items():
            if canonical_id(name) == wanted and isinstance(stored, str):
                return name, stored
        return None, None

    def taken(self, principal_id):
        """Whether this name, or one that differs only in letter case, '-' or '_', has a password."""
        with self._lock:
            names = self._read()['accounts']
        return canonical_id(principal_id) in {canonical_id(name) for name in names}

    def add(self, principal_id, password_hash):
        with self._lock:
            value = self._read()
            # `Synthetic_Founder` or `synthetic-founder` must not sit beside `synthetic_founder`.
            if canonical_id(principal_id) in {canonical_id(name) for name in value['accounts']}:
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
    """At most `limit` attempts per key in a sliding window, in this process only.

    take() checks and counts in one step, so parallel requests cannot all pass the check
    before any is counted. At most `max_keys` keys are held, so memory stays bounded; when
    that many are live, the oldest key gives way. Refusing the new key instead let a flood
    of made-up names lock every real user out (runtime review, 31 October 2026); giving way
    hands a flooded name back at most `limit` attempts per `max_keys` made-up names.
    """

    def __init__(self, limit, window_seconds, *, max_keys=10000, clock=time.monotonic):
        self.limit, self.window, self.max_keys, self.clock = limit, window_seconds, max_keys, clock
        self._events = {}
        self._lock = threading.Lock()

    def _prune(self, key, now):
        events = [moment for moment in self._events.get(key, ()) if moment > now - self.window]
        if events:
            self._events[key] = events
        else:
            self._events.pop(key, None)
        return events

    def take(self, key):
        with self._lock:
            now = self.clock()
            events = self._prune(key, now)
            if len(events) >= self.limit:
                return False
            if not events and len(self._events) >= self.max_keys:
                for other in list(self._events):
                    self._prune(other, now)
                while len(self._events) >= self.max_keys:
                    self._events.pop(next(iter(self._events)))
            self._events.setdefault(key, []).append(now)
            return True

    def clear(self, key):
        with self._lock:
            self._events.pop(key, None)

    def size(self):
        with self._lock:
            return len(self._events)


def _credentials(value):
    if not isinstance(value, dict) or set(value) != {'username', 'password'}:
        raise FlowError('VALIDATION_ERROR')
    username, password = value['username'], value['password']
    if not isinstance(username, str) or not isinstance(password, str):
        raise FlowError('VALIDATION_ERROR')
    return username, password


def _valid_username(username):
    try:
        validate('Principal', {'principal_id': username, 'role': 'CUSTOMER'})
    except FlowError:
        return False
    return True


def _encodable(password):
    try:
        password.encode('utf-8')
    except UnicodeEncodeError:
        return False
    return True


def _session_times():
    now = int(time.time())
    # The same window as demo.py provision: 900 s from issue, the most the verifier accepts.
    return {'session_id': identifier('session'), 'issued_at': now - 1, 'not_before': now - 1,
            'expires_at': now + SESSION_SECONDS}


def _token(config, principal_id, session):
    claims = {'iss': config.issuer, 'aud': config.audience, 'sub': principal_id, 'jti': session['session_id'],
              'iat': session['issued_at'], 'nbf': session['not_before'], 'exp': session['expires_at']}
    return jwt.encode(claims, config.signing_key, algorithm='HS256')


def _signed_in(token, principal_id, role, expires_in=SESSION_SECONDS):
    return {'access_token': token, 'token_type': 'Bearer', 'expires_in': expires_in,
            'principal_id': principal_id, 'role': role}


WRONG_CREDENTIALS = 'The username or password is not correct.'


def register_account_routes(app, store):
    # Five sign-in attempts per name a minute: the demo passwords are random 16-character
    # strings, so this mainly slows guessing at customer passwords without locking a name long.
    sign_ins = AttemptLimiter(5, 60)
    registrations = AttemptLimiter(120, 600)
    hash_slots = threading.BoundedSemaphore(HASH_SLOTS)
    pending = set()
    pending_lock = threading.Lock()
    # Session ID -> when its password sign-in happened (Unix seconds), for the keys this
    # process issued by sign-in, registration or renewal; a restart forgets them, and the
    # next key then needs a new sign-in. Bounded like the limiters.
    renewable = {}
    renewable_lock = threading.Lock()
    # Exposed for tests and operators; nothing here is a secret.
    app.state.account_limits = {'sign_ins': sign_ins, 'registrations': registrations, 'hash_slots': hash_slots}
    app.state.account_renewals = {'keys': renewable, 'window': RENEW_WINDOW_SECONDS, 'before': RENEW_BEFORE_SECONDS}

    wrong = lambda: AccountError('UNAUTHENTICATED', WRONG_CREDENTIALS)
    taken = lambda: AccountError('INVALID_STATE', 'That username is already taken. Choose another one.')
    not_renewable = lambda: AccountError('INVALID_STATE', 'This sign-in cannot be renewed. Sign in again.')

    def remember(session_id, signed_in_at):
        with renewable_lock:
            renewable[session_id] = signed_in_at
            while len(renewable) > RENEWABLE_MAX_KEYS:
                renewable.pop(next(iter(renewable)))

    def with_hash_slot(work):
        if not hash_slots.acquire(timeout=HASH_WAIT_SECONDS):
            raise AccountError('INTERNAL_ERROR', BUSY, status=503)
        try:
            return work()
        finally:
            hash_slots.release()

    def register(config, engine, username, password):
        if not _valid_username(username):
            raise AccountError('VALIDATION_ERROR', 'Choose a username of 3 to 80 letters, digits, - or _, '
                               'starting with a letter or digit.')
        if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX or blank(password) or not _encodable(password):
            raise AccountError('VALIDATION_ERROR', 'Choose a password of 8 to 128 characters.')
        if not registrations.take('all'):
            raise AccountError('INVALID_STATE', 'Too many accounts were requested just now. Try again in a few minutes.',
                               status=429)
        name = canonical_id(username)
        with pending_lock:
            if name in pending:
                raise taken()
            pending.add(name)
        registry = TrustedRegistry(engine)
        try:
            # Refused before any password is written: an existing account, or a look-alike of
            # one, can never be given a password that signs it in.
            if store.taken(username) or registry.name_taken(username):
                raise taken()
            password_hash = with_hash_slot(lambda: hash_password(password))
            try:
                store.add(username, password_hash)
            except FlowError:
                raise taken() from None
            session = _session_times()
            try:
                registry.register_customer(username, store.store_id, session)
            except FlowError as error:
                # A refusal before commit: nothing was written to the database.
                store.remove(username)
                if error.code == 'INVALID_STATE':
                    raise taken() from None
                if error.code == 'FORBIDDEN':
                    raise AccountError('FORBIDDEN', 'New accounts cannot be created for this shop right now.') from None
                raise
            except BaseException:
                # The outcome is unknown (a lost commit acknowledgement): keep the password if
                # the account exists, so it can still sign in; otherwise take it back.
                try:
                    exists = registry.name_taken(username)
                except Exception:
                    exists = True
                if not exists:
                    store.remove(username)
                raise
        finally:
            with pending_lock:
                pending.discard(name)
        remember(session['session_id'], session['not_before'] + 1)
        return 201, _signed_in(_token(config, username, session), username, 'CUSTOMER')

    def sign_in(config, engine, username, password):
        # Bounded before any work: no hashing, no limiter entry for an impossible name.
        if not _valid_username(username) or not 1 <= len(password) <= PASSWORD_MAX:
            raise wrong()
        name = canonical_id(username)
        with pending_lock:
            if name in pending:
                raise wrong()
        if not sign_ins.take(name):
            raise AccountError('INVALID_STATE', 'Too many sign-in attempts for this username. Wait a minute.', status=429)
        # The account's own spelling: `Alice` registered also signs in as `alice`, never as a second name.
        own, stored = store.entry_for(username)
        matched = with_hash_slot(lambda: verify_password(password, stored or _UNKNOWN)) and stored is not None
        if not matched:
            raise wrong()
        username = own
        registry = TrustedRegistry(engine)
        scope = registry.principal_scope(username)
        # Only an enabled account of this file's store signs in here.
        if scope is None or scope[1] != store.store_id or scope[2] is not True:
            raise wrong()
        session = _session_times()
        try:
            registry.register_session(username, session['session_id'], session['issued_at'],
                                      session['not_before'], session['expires_at'])
        except FlowError as error:
            if error.code in {'INVALID_STATE', 'VALIDATION_ERROR'}:
                raise wrong() from None
            raise
        sign_ins.clear(name)
        remember(session['session_id'], session['not_before'] + 1)
        return 200, _signed_in(_token(config, username, session), username, scope[0])

    def renew(config, engine, authorization):
        """The next key of a password sign-in (1 November 2026); every check of a request first."""
        with engine.connect() as connection:
            try:
                verified = Authenticator(config, SameConnectionIdentities(connection)).authenticate(authorization)
            except SecurityError as error:
                raise FlowError(error.code, status=error.status_code) from None
        with renewable_lock:
            signed_in_at = renewable.get(verified.session_id)
        rules = app.state.account_renewals
        if signed_in_at is None or verified.store_id != store.store_id:
            raise not_renewable()
        now = int(time.time())
        ends = signed_in_at + rules['window']
        # Verified above, so the claims are this key's own.
        current_ends = int(jwt.decode(authorization.split()[1], options={'verify_signature': False})['exp'])
        if current_ends - now > rules['before']:
            raise AccountError('INVALID_STATE', 'This key is renewed in its last five minutes.')
        if ends - now < 2:
            raise AccountError('INVALID_STATE', 'The hour since sign-in has passed. Sign in again.')
        session = {'session_id': identifier('session'), 'issued_at': now - 1, 'not_before': now - 1,
                   'expires_at': min(now + SESSION_SECONDS, ends)}
        principal_id = verified.principal_id
        try:
            TrustedRegistry(engine).register_session(principal_id, session['session_id'], session['issued_at'],
                                                     session['not_before'], session['expires_at'])
        except FlowError as error:
            if error.code in {'INVALID_STATE', 'VALIDATION_ERROR'}:
                raise not_renewable() from None
            raise
        remember(session['session_id'], signed_in_at)
        return 200, _signed_in(_token(config, principal_id, session), principal_id, verified.role.value,
                               expires_in=session['expires_at'] - now)

    async def read_body(request):
        content_type = one_header(request, 'content-type', required=True)
        if content_type.split(';', 1)[0].strip().lower() != 'application/json':
            raise FlowError('VALIDATION_ERROR')
        length = request.headers.get('content-length')
        if length is not None and (not length.strip().isdigit() or int(length) > MAX_AUTH_BODY_BYTES):
            raise FlowError('VALIDATION_ERROR')
        body = bytearray()
        async with asyncio.timeout(AUTH_BODY_SECONDS):
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_AUTH_BODY_BYTES:
                    raise FlowError('VALIDATION_ERROR')
                body.extend(chunk)
        return decode_json_document(bytes(body))

    def threads(app):
        # Created on first use, inside the event loop that owns it.
        limiter = getattr(app.state, 'auth_threads', None)
        if limiter is None:
            limiter = app.state.auth_threads = anyio.CapacityLimiter(AUTH_THREADS)
        return limiter

    async def respond(request, operation):
        correlation = identifier('corr')
        try:
            config = request.app.state.auth_config
            if config is None:
                raise FlowError('INTERNAL_ERROR')
            username, password = _credentials(await read_body(request))
            limiter = threads(request.app)
            if limiter.borrowed_tokens >= limiter.total_tokens:
                raise AccountError('INTERNAL_ERROR', BUSY, status=503)
            status, body = await anyio.to_thread.run_sync(
                functools.partial(operation, config, request.app.state.engine, username, password), limiter=limiter)
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

    @app.post('/v1/auth/renew')
    async def renew_route(request: Request):
        correlation = identifier('corr')
        try:
            config = request.app.state.auth_config
            if config is None:
                raise FlowError('INTERNAL_ERROR')
            # No body: the bearer key is the whole request.
            authorization = one_header(request, 'authorization')
            limiter = threads(request.app)
            if limiter.borrowed_tokens >= limiter.total_tokens:
                raise AccountError('INTERNAL_ERROR', BUSY, status=503)
            status, body = await anyio.to_thread.run_sync(
                functools.partial(renew, config, request.app.state.engine, authorization), limiter=limiter)
            return safe_json(body, status, correlation=correlation)
        except FlowError as error:
            return safe_json(error.envelope(correlation), error.status, correlation=correlation)
        except Exception:
            return safe_json(FlowError().envelope(correlation), 503, correlation=correlation)
