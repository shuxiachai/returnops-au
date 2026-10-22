"""R.02 demo mode: read the identities that demo.py provision wrote; not installed.

`python -m returnops_api.demo provision --private-dir D ...` writes two files:
D/auth.json {issuer, audience, signing_key_base64} and D/sessions.json
{principals, sessions, tokens}, with principals in the order customer-one,
customer-two, founder. load() reads both (their 0600/0700 modes are not
required for reading), checks them against exactly those shapes, and verifies
every token with the file's key, issuer and audience the way the API's
Authenticator does (HS256, required claims, no leeway). It never writes, never
registers anything and never prints. Errors carry a safe code only: no value,
path, token or key. Whether the rows are actually registered in the database is
checked by the driver (step 0), not here.

docs/08 R.02 (live-demo support only, not CI evidence); FR-009, NFR-002/NFR-003;
docs/16 private demo identities.
"""
import base64
import binascii
from dataclasses import dataclass, field
import json
from pathlib import Path

import jwt

from returnops_domain.wire import validate

AUTH_FILE, SESSIONS_FILE = 'auth.json', 'sessions.json'
MAX_BYTES = {AUTH_FILE: 8192, SESSIONS_FILE: 65536}  # 8192 is load_private_auth_config's own limit
AUTH_KEYS = frozenset({'issuer', 'audience', 'signing_key_base64'})
DOCUMENT_KEYS = frozenset({'principals', 'sessions', 'tokens'})
PRINCIPAL_KEYS = frozenset({'principal_id', 'role', 'store_id', 'enabled'})
SESSION_KEYS = frozenset({'session_id', 'principal_id', 'issued_at', 'not_before', 'expires_at', 'revoked'})
NAMES = ('customer_one', 'customer_two', 'founder')
MAX_SESSION_SECONDS = 900  # customer_sessions check constraint and AuthConfig.max_ttl_seconds
CLAIMS = ('iss', 'aud', 'sub', 'jti', 'iat', 'nbf', 'exp')


class IdentitiesError(Exception):
    """A safe code only (str(error) and .code)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Identities:
    auth_file: Path = field(repr=False)
    issuer: str
    audience: str
    signing_key: bytes = field(repr=False)
    signing_key_base64: str = field(repr=False)
    store_id: str
    people: dict  # customer_one / customer_two / founder -> principal_id
    principals: dict = field(repr=False)  # name -> principal row as written by demo.py
    sessions: dict = field(repr=False)  # name -> session row as written by demo.py
    tokens: dict = field(repr=False)  # name -> JWT

    @property
    def issued_at(self):
        return max(row['issued_at'] for row in self.sessions.values())

    @property
    def expires_at(self):
        """The earliest expiry of the three sessions: the driver's session window."""
        return min(row['expires_at'] for row in self.sessions.values())

    def secret_values(self):
        """Every value a receipt or a kept log must never contain."""
        key = self.signing_key
        return [*self.tokens.values(), self.signing_key_base64, base64.b64encode(key).decode('ascii'), key.hex()]


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate member')
        result[key] = value
    return result


def _read(directory, name):
    path = directory / name
    if not path.is_file():
        raise IdentitiesError('IDENTITIES_FILE_MISSING')
    try:
        raw = path.read_bytes()
    except OSError:
        raise IdentitiesError('IDENTITIES_FILE_UNREADABLE') from None
    if len(raw) > MAX_BYTES[name]:
        raise IdentitiesError('IDENTITIES_FILE_TOO_LARGE')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique)
    except (UnicodeDecodeError, ValueError):
        raise IdentitiesError('IDENTITIES_MALFORMED') from None


def _valid(name, value):
    try:
        validate(name, value)
    except Exception:
        return False
    return True


def _text(value):
    return type(value) is str and 1 <= len(value) <= 200 and value.isascii()


def _auth(value):
    if type(value) is not dict or set(value) != AUTH_KEYS or not all(_text(value[k]) for k in ('issuer', 'audience')):
        raise IdentitiesError('IDENTITIES_MALFORMED')
    encoded = value['signing_key_base64']
    try:
        key = base64.b64decode(encoded, validate=True) if type(encoded) is str else None
    except (binascii.Error, ValueError):
        key = None
    if key is None:
        raise IdentitiesError('IDENTITIES_MALFORMED')
    if not 32 <= len(key) <= 128:  # AuthConfig's accepted key length
        raise IdentitiesError('IDENTITIES_KEY_INVALID')
    return value['issuer'], value['audience'], key, encoded


def _principals(rows):
    if type(rows) is not list or len(rows) != 3 or any(type(row) is not dict or set(row) != PRINCIPAL_KEYS
                                                       for row in rows):
        raise IdentitiesError('IDENTITIES_MALFORMED')
    if any(not _valid('Principal', {'principal_id': row['principal_id'], 'role': row['role']})
           or not _valid('Id', row['store_id']) for row in rows):
        raise IdentitiesError('IDENTITIES_MALFORMED')
    ids = [row['principal_id'] for row in rows]
    customers = [row for row in rows if row['role'] == 'CUSTOMER']
    founders = [row for row in rows if row['role'] == 'FOUNDER']
    if (len(set(ids)) != 3 or len(customers) != 2 or len(founders) != 1
            or len({row['store_id'] for row in rows}) != 1 or any(row['enabled'] is not True for row in rows)):
        raise IdentitiesError('IDENTITIES_ROLES_INVALID')
    # demo.py writes [customer_one, customer_two, founder]; the first customer is customer_one.
    return dict(zip(NAMES, (*customers, founders[0])))


def _sessions(rows, principals):
    by_principal = {row['principal_id']: name for name, row in principals.items()}
    if type(rows) is not list or len(rows) != 3 or any(type(row) is not dict or set(row) != SESSION_KEYS
                                                       for row in rows):
        raise IdentitiesError('IDENTITIES_MALFORMED')
    result = {}
    for row in rows:
        times = [row[k] for k in ('issued_at', 'not_before', 'expires_at')]
        if (row['principal_id'] not in by_principal or by_principal[row['principal_id']] in result
                or not _valid('Id', row['session_id']) or any(type(t) is not int for t in times)
                or not 0 <= times[0] <= times[1] < times[2] <= 9007199254740991
                or times[2] - times[0] > MAX_SESSION_SECONDS or row['revoked'] is not False):
            raise IdentitiesError('IDENTITIES_SESSIONS_INVALID')
        result[by_principal[row['principal_id']]] = row
    if len({row['session_id'] for row in result.values()}) != 3:
        raise IdentitiesError('IDENTITIES_SESSIONS_INVALID')
    return result


def _verify(token, key, issuer, audience, principal, session):
    try:
        decoded = jwt.decode_complete(token, key, algorithms=['HS256'], issuer=issuer, audience=audience, leeway=0,
                                      options={'require': list(CLAIMS), 'strict_aud': True})
    except jwt.ExpiredSignatureError:
        raise IdentitiesError('IDENTITIES_SESSION_EXPIRED') from None
    except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError):
        raise IdentitiesError('IDENTITIES_TOKEN_INVALID') from None
    header, claims = decoded['header'], decoded['payload']
    if (set(header) != {'alg', 'typ'} or header.get('typ') != 'JWT' or claims['sub'] != principal['principal_id']
            or claims['jti'] != session['session_id']
            or [claims[k] for k in ('iat', 'nbf', 'exp')] != [session[k] for k in ('issued_at', 'not_before', 'expires_at')]):
        raise IdentitiesError('IDENTITIES_TOKEN_INVALID')


def load(directory):
    """Validated Identities from a demo.py provision directory, or IdentitiesError."""
    directory = Path(directory)
    if not directory.is_dir():
        raise IdentitiesError('IDENTITIES_DIRECTORY_MISSING')
    issuer, audience, key, encoded = _auth(_read(directory, AUTH_FILE))
    document = _read(directory, SESSIONS_FILE)
    if type(document) is not dict or set(document) != DOCUMENT_KEYS:
        raise IdentitiesError('IDENTITIES_MALFORMED')
    principals = _principals(document['principals'])
    sessions = _sessions(document['sessions'], principals)
    tokens = document['tokens']
    if (type(tokens) is not dict or set(tokens) != {row['principal_id'] for row in principals.values()}
            or any(type(value) is not str or len(value) > 4096 for value in tokens.values())):
        raise IdentitiesError('IDENTITIES_MALFORMED')
    named = {name: tokens[row['principal_id']] for name, row in principals.items()}
    for name in NAMES:
        _verify(named[name], key, issuer, audience, principals[name], sessions[name])
    return Identities(auth_file=(directory / AUTH_FILE).resolve(), issuer=issuer, audience=audience, signing_key=key,
                      signing_key_base64=encoded, store_id=principals['founder']['store_id'],
                      people={name: row['principal_id'] for name, row in principals.items()},
                      principals=principals, sessions=sessions, tokens=named)
