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
