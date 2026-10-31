"""Customer self-registration and password sign-in against real PG17 (31 October 2026).

FR-001, FR-012; NFR-002, NFR-009. Registration creates only CUSTOMER principals of the
credentials file's store; a sign-in issues a session the existing verifier accepts.
"""
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from returnops_api.accounts import new_credentials_file
from returnops_api.main import create_app
from returnops_domain import customer_tables as t
from returnops_domain import scope_audit
from returnops_domain.canonical import decode_document
from returnops_domain.registry import TrustedRegistry
from returnops_domain.wire import validate

PASSWORDS = {'customer_a': 'customer-pass-1234', 'founder': 'founder-pass-1234'}


def _app(flow_engine, identities, path):
    return create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False,
                      accounts_file=str(path.resolve()))


@pytest.fixture
def accounts(flow_engine, identities, tmp_path):
    path = tmp_path / 'credentials.json'
    new_credentials_file(path, identities.people['founder']['store_id'],
                         {identities.people[name]['principal_id']: value for name, value in PASSWORDS.items()})
    with TestClient(_app(flow_engine, identities, path)) as client:
        yield client, path


def post(client, route, username, password):
    return client.post('/v1/auth/' + route, content=json.dumps({'username': username, 'password': password}).encode(),
                       headers={'Content-Type': 'application/json'})


def session(client, body):
    return client.get('/v1/session', headers={'Authorization': 'Bearer ' + body['access_token']})


def refused(response, status, code, message=None):
    assert response.status_code == status, response.text
    validate('ErrorEnvelope', response.json())
    assert response.json()['error']['code'] == code
    assert response.headers['Cache-Control'] == 'no-store'
    if message is not None:
        assert response.json()['error']['message'] == message


def test_registration_creates_a_customer_of_the_store_who_can_sign_in_and_lodge(accounts, flow_engine, identities):
    client, path = accounts
    username = 'new_customer_' + uuid4().hex[:8]
    created = post(client, 'register', username, 'a-long-password')
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body['principal_id'], body['role'], body['token_type'], body['expires_in']) == (username, 'CUSTOMER', 'Bearer', 899)
    assert created.headers['Cache-Control'] == 'no-store'
    current = session(client, body)
    assert current.status_code == 200 and current.json()['principal_id'] == username and current.json()['role'] == 'CUSTOMER'
    with flow_engine.connect() as connection:
        row = connection.execute(select(t.principals).where(t.principals.c.principal_id == username)).mappings().one()
        audited = connection.execute(select(scope_audit.events.c.body).where(scope_audit.events.c.scope_id == username)).scalars().all()
    assert (row['role'], row['store_id'], row['enabled']) == ('CUSTOMER', identities.people['founder']['store_id'], True)
    assert any(decode_document(value)['action'] == 'PRINCIPAL_SELF_REGISTERED' for value in audited)
    # The password itself is never stored, only its hash.
    assert 'a-long-password' not in path.read_text(encoding='utf-8')

    again = post(client, 'login', username, 'a-long-password')
    assert again.status_code == 200 and session(client, again.json()).status_code == 200
    lodged = client.post('/v1/cases', content=json.dumps({'original_message': 'The kettle stopped heating.'}).encode(),
                         headers={'Content-Type': 'application/json', 'Idempotency-Key': 'register-lodge-1',
                                  'Authorization': 'Bearer ' + again.json()['access_token']})
    assert lodged.status_code == 201, lodged.text


def test_registration_refuses_taken_names_founders_and_weak_input(accounts, identities):
    client, path = accounts
    before = path.read_bytes()
    taken = 'That username is already taken. Choose another one.'
    refused(post(client, 'register', identities.people['founder']['principal_id'], 'another-password'), 409, 'INVALID_STATE', taken)
    refused(post(client, 'register', identities.people['customer_b']['principal_id'], 'another-password'), 409, 'INVALID_STATE', taken)
    # The same IDs in another letter case: in the file (the Founder) and only in the database (customer_b).
    refused(post(client, 'register', identities.people['founder']['principal_id'].upper(), 'another-password'), 409, 'INVALID_STATE', taken)
    refused(post(client, 'register', identities.people['customer_b']['principal_id'].upper(), 'another-password'), 409, 'INVALID_STATE', taken)
    refused(post(client, 'register', 'short_pw_' + uuid4().hex[:6], 'short'), 422, 'VALIDATION_ERROR',
            'Choose a password of 8 to 128 characters.')
    refused(post(client, 'register', 'blank_pw_' + uuid4().hex[:6], '​' * 10), 422, 'VALIDATION_ERROR')
    refused(post(client, 'register', 'x', 'a-long-password'), 422, 'VALIDATION_ERROR')
    refused(client.post('/v1/auth/register', content=b'{"username":"someone_new","password":"a-long-password","role":"FOUNDER"}',
                        headers={'Content-Type': 'application/json'}), 422, 'VALIDATION_ERROR')
    # customer_b exists in the database but not in the file: refused and the file left as it was.
    assert path.read_bytes() == before


def test_founder_signs_in_with_a_password_and_wrong_passwords_are_limited(accounts, identities):
    client, _ = accounts
    founder = identities.people['founder']['principal_id']
    signed = post(client, 'login', founder, PASSWORDS['founder'])
    assert signed.status_code == 200, signed.text
    assert signed.json()['role'] == 'FOUNDER' and session(client, signed.json()).json()['role'] == 'FOUNDER'
    wrong = 'The username or password is not correct.'
    refused(post(client, 'login', 'nobody_' + uuid4().hex[:6], PASSWORDS['founder']), 401, 'UNAUTHENTICATED', wrong)
    for _ in range(5):
        refused(post(client, 'login', founder, 'not-the-password'), 401, 'UNAUTHENTICATED', wrong)
    # The sixth try is refused even with the right password, for this username only.
    refused(post(client, 'login', founder, PASSWORDS['founder']), 429, 'INVALID_STATE')
    customer = identities.people['customer_a']['principal_id']
    assert post(client, 'login', customer, PASSWORDS['customer_a']).status_code == 200


def test_a_disabled_account_cannot_sign_in(accounts, flow_engine, identities):
    client, _ = accounts
    customer = identities.people['customer_a']['principal_id']
    TrustedRegistry(flow_engine).change_principal(customer, enabled=False)
    refused(post(client, 'login', customer, PASSWORDS['customer_a']), 401, 'UNAUTHENTICATED')


def test_no_registration_into_a_store_without_an_enabled_founder(flow_engine, identities, tmp_path):
    path = tmp_path / 'credentials.json'
    new_credentials_file(path, 'store_without_founder_' + uuid4().hex[:8], {})
    with TestClient(_app(flow_engine, identities, path)) as client:
        username = 'orphan_' + uuid4().hex[:8]
        refused(post(client, 'register', username, 'a-long-password'), 403, 'FORBIDDEN')
    assert json.loads(path.read_text(encoding='utf-8'))['accounts'] == {}
    with flow_engine.connect() as connection:
        assert connection.execute(select(t.principals).where(t.principals.c.principal_id == username)).first() is None


# Independent review of 31 October 2026 (findings 1 to 9), each as a regression test.

def test_a_database_only_name_never_gets_a_password_written(accounts, identities, monkeypatch):
    # Finding 1: the password used to be written before the database check, so a sign-in in
    # that window could take over the existing account.
    client, path = accounts
    from returnops_api import accounts as module
    written = []
    original = module.CredentialStore.add
    monkeypatch.setattr(module.CredentialStore, 'add', lambda self, name, value: (written.append(name), original(self, name, value)))
    target = identities.people['customer_b']['principal_id']
    for name in (target, target.upper(), target.replace('_', '-')):
        refused(post(client, 'register', name, 'attacker-password'), 409, 'INVALID_STATE')
    assert written == []
    refused(post(client, 'login', target, 'attacker-password'), 401, 'UNAUTHENTICATED')


def test_a_name_being_registered_cannot_sign_in(accounts, monkeypatch):
    # Finding 1: the window between writing the password and creating the account.
    client, _ = accounts
    import threading
    from returnops_domain.registry import TrustedRegistry as Registry
    username = 'racing_' + uuid4().hex[:8]
    answers = []
    original = Registry.register_customer

    def during(self, principal_id, store_id, session):
        worker = threading.Thread(target=lambda: answers.append(post(client, 'login', principal_id, 'a-long-password').status_code))
        worker.start()
        worker.join(timeout=20)
        return original(self, principal_id, store_id, session)

    monkeypatch.setattr(Registry, 'register_customer', during)
    assert post(client, 'register', username, 'a-long-password').status_code == 201
    assert answers == [401]
    assert post(client, 'login', username, 'a-long-password').status_code == 200


def test_a_password_for_another_store_does_not_sign_in(accounts, flow_engine, identities):
    # Finding 1: a sign-in must belong to the credentials file's store.
    client, path = accounts
    import time as clock
    other = 'other_store_' + uuid4().hex[:8]
    outsider = 'outsider_' + uuid4().hex[:8]
    now = int(clock.time())
    TrustedRegistry(flow_engine).provision(
        [{'principal_id': outsider, 'role': 'FOUNDER', 'store_id': other, 'enabled': True}],
        [{'session_id': 'session_' + uuid4().hex, 'principal_id': outsider, 'issued_at': now - 1, 'not_before': now - 1,
          'expires_at': now + 600, 'revoked': False}])
    from returnops_api.accounts import CredentialStore, hash_password
    CredentialStore(path).add(outsider, hash_password('outsider-password'))
    refused(post(client, 'login', outsider, 'outsider-password'), 401, 'UNAUTHENTICATED')


def test_impossible_names_and_passwords_are_refused_before_any_work(accounts):
    # Findings 2, 3 and 8: no limiter entry and no hashing for a name that cannot exist; a
    # password that cannot be encoded is a validation error, not a service failure.
    client, _ = accounts
    limits = client.app.state.account_limits
    before = limits['sign_ins'].size()
    for _ in range(20):
        refused(post(client, 'login', 'x' * 200, 'whatever-password'), 401, 'UNAUTHENTICATED')
    refused(post(client, 'login', 'someone_real', 'p' * 1000), 401, 'UNAUTHENTICATED')
    # Runtime review (31 October 2026): a body over 4 KiB is refused before it is decoded.
    refused(post(client, 'login', 'x' * 100000, 'whatever-password'), 422, 'VALIDATION_ERROR')
    refused(post(client, 'register', 'someone_new', 'p' * 100000), 422, 'VALIDATION_ERROR')
    assert limits['sign_ins'].size() == before
    surrogate = client.post('/v1/auth/register', content=b'{"username":"surrogate_user","password":"abcdefgh\ud800"}',
                            headers={'Content-Type': 'application/json'})
    refused(surrogate, 422, 'VALIDATION_ERROR', 'Choose a password of 8 to 128 characters.')


def test_hashing_waits_for_a_free_slot_and_otherwise_says_busy(accounts, identities):
    # Finding 3: at most two scrypt computations at a time.
    client, _ = accounts
    slots = client.app.state.account_limits['hash_slots']
    assert slots.acquire() and slots.acquire()
    try:
        busy = post(client, 'login', identities.people['founder']['principal_id'], PASSWORDS['founder'])
        refused(busy, 503, 'INTERNAL_ERROR', 'Sign-in is busy right now. Try again in a moment.')
    finally:
        slots.release()
        slots.release()
    assert post(client, 'login', identities.people['founder']['principal_id'], PASSWORDS['founder']).status_code == 200


def test_an_unknown_registration_outcome_keeps_the_password_of_a_created_account(accounts, monkeypatch):
    # Finding 5: a lost commit acknowledgement used to delete the password of a created account.
    client, path = accounts
    from returnops_domain.errors import AcceptanceOutcomeUnknown
    from returnops_domain.registry import TrustedRegistry as Registry
    original = Registry.register_customer

    def committed_but_unacknowledged(self, *args):
        original(self, *args)
        raise AcceptanceOutcomeUnknown()

    monkeypatch.setattr(Registry, 'register_customer', committed_but_unacknowledged)
    username = 'unacknowledged_' + uuid4().hex[:8]
    assert post(client, 'register', username, 'a-long-password').status_code == 503
    monkeypatch.setattr(Registry, 'register_customer', original)
    assert username in json.loads(path.read_text(encoding='utf-8'))['accounts']
    assert post(client, 'login', username, 'a-long-password').status_code == 200


def test_failed_registrations_count_towards_the_registration_limit(accounts, identities):
    # Finding 6: refused duplicates used to be free, so retries were unlimited.
    client, _ = accounts
    limits = client.app.state.account_limits['registrations']
    before = limits._events.get('all', [])[:]
    refused(post(client, 'register', identities.people['founder']['principal_id'], 'another-password'), 409, 'INVALID_STATE')
    assert len(limits._events.get('all', [])) == len(before) + 1


def test_a_name_signs_in_in_any_letter_case_as_the_account_itself(accounts):
    # Runtime review (31 October 2026): registration treats Alice and alice as one name,
    # so sign-in does too, and the session is the account's own spelling.
    client, _ = accounts
    username = 'Mixed_Case_' + uuid4().hex[:6]
    assert post(client, 'register', username, 'a-long-password').status_code == 201
    for typed in (username.lower(), username.upper().replace('_', '-')):
        signed_in = post(client, 'login', typed, 'a-long-password')
        assert signed_in.status_code == 200, signed_in.text
        assert signed_in.json()['principal_id'] == username
        assert session(client, signed_in.json()).json()['principal_id'] == username
    refused(post(client, 'login', username.lower(), 'wrong-password-1'), 401, 'UNAUTHENTICATED')


def test_busy_auth_threads_refuse_at_once_without_any_work(accounts, identities):
    # Runtime review (31 October 2026): at most four auth requests hold worker threads; a
    # flood is refused at once instead of taking the threads every other route needs.
    from types import SimpleNamespace
    client, _ = accounts
    limits = client.app.state.account_limits
    before = limits['sign_ins'].size()
    client.app.state.auth_threads = SimpleNamespace(borrowed_tokens=4, total_tokens=4)
    busy = post(client, 'login', identities.people['founder']['principal_id'], PASSWORDS['founder'])
    refused(busy, 503, 'INTERNAL_ERROR', 'Sign-in is busy right now. Try again in a moment.')
    assert limits['sign_ins'].size() == before
    client.app.state.auth_threads = None
    assert post(client, 'login', identities.people['founder']['principal_id'], PASSWORDS['founder']).status_code == 200

