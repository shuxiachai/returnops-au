"""The signed-in customer's own case list, GET /v1/cases, against real PG17 (31 October 2026).

Outside contract v1 and served only with password sign-in. FR-001; NFR-002, NFR-003, NFR-006; UC-01E:
a customer sees only their own available cases of the store, the Founder is refused.
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from returnops_api.accounts import new_credentials_file
from returnops_api.main import create_app
from returnops_domain import customer_tables as t
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.wire import validate


@pytest.fixture
def client(flow_engine, identities, tmp_path):
    path = tmp_path / 'credentials.json'
    new_credentials_file(path, identities.people['founder']['store_id'], {})
    app = create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False,
                     accounts_file=str(path.resolve()))
    with TestClient(app) as test_client:
        yield test_client


def bearer(identities, name):
    return {'Authorization': 'Bearer ' + identities.tokens[name]}


def lodge(client, identities, name, message, key, outcome=None):
    body = {'original_message': message}
    if outcome is not None:
        body['requested_outcome'] = outcome
    response = client.post('/v1/cases', content=json.dumps(body).encode(),
                           headers={**bearer(identities, name), 'Content-Type': 'application/json', 'Idempotency-Key': key})
    assert response.status_code == 201, response.text
    return response.json()['case_id']


def own(client, identities, name, **kwargs):
    return client.get('/v1/cases', headers=bearer(identities, name), **kwargs)


def refused(response, status, code):
    assert response.status_code == status, response.text
    validate('ErrorEnvelope', response.json())
    assert response.json()['error']['code'] == code
    assert response.headers['Cache-Control'] == 'no-store'


def test_a_customer_sees_only_their_own_cases_newest_first(client, identities):
    first = lodge(client, identities, 'customer_a', 'The kettle stopped heating after two days.', 'list-a-1', 'REFUND')
    other = lodge(client, identities, 'customer_b', 'Customer B private words.', 'list-b-1')
    second = lodge(client, identities, 'customer_a', 'The parcel   arrived\n crushed. ' + 'x' * 200, 'list-a-2')
    response = own(client, identities, 'customer_a')
    assert response.status_code == 200, response.text
    assert response.headers['Cache-Control'] == 'no-store' and response.headers['X-Correlation-ID']
    body = response.json()
    assert body['limit'] == 20 and [item['case_id'] for item in body['items']] == [second, first]
    newest, oldest = body['items']
    assert (oldest['excerpt'], oldest['requested_outcome'], oldest['status'], oldest['awaiting_answer']) == (
        'The kettle stopped heating after two days.', 'REFUND', 'SUBMITTED', False)
    # Spaces and line breaks fold; a long statement is cut at 120 characters and marked.
    assert newest['excerpt'].startswith('The parcel arrived crushed. xxx') and newest['excerpt'].endswith('...')
    assert len(newest['excerpt']) == 123 and newest.get('requested_outcome', 'UNSPECIFIED') == 'UNSPECIFIED'
    assert set(newest) <= {'case_id', 'status', 'created_at', 'updated_at', 'awaiting_answer', 'excerpt', 'requested_outcome'}
    assert other not in response.text and 'Customer B' not in response.text
    assert [item['case_id'] for item in own(client, identities, 'customer_b').json()['items']] == [other]


def test_a_case_waiting_for_the_customer_says_so_like_the_single_case_view(client, identities, flow_engine):
    case_id = lodge(client, identities, 'customer_a', 'It is not right.', 'list-a-wait')
    assert IntakeProcessor(flow_engine).run_once()
    item, = own(client, identities, 'customer_a').json()['items']
    single = client.get('/v1/cases/' + case_id, headers=bearer(identities, 'customer_a')).json()
    assert item['case_id'] == case_id and item['awaiting_answer'] is True and 'clarification' in single
    assert (item['status'], item['created_at'], item['updated_at']) == (single['status'], single['created_at'], single['updated_at'])


def test_a_new_customer_has_an_empty_list(client, identities):
    lodge(client, identities, 'customer_b', 'Not for customer A.', 'list-b-only')
    assert own(client, identities, 'customer_a').json() == {'items': [], 'limit': 20}


def test_the_founder_strangers_and_queries_are_refused(client, identities):
    lodge(client, identities, 'customer_a', 'Kept private.', 'list-a-refuse')
    refused(own(client, identities, 'founder'), 403, 'FORBIDDEN')
    refused(client.get('/v1/cases'), 401, 'UNAUTHENTICATED')
    refused(client.get('/v1/cases', headers={'Authorization': 'Bearer not-a-token'}), 401, 'UNAUTHENTICATED')
    refused(own(client, identities, 'customer_a', params={'limit': '5'}), 422, 'VALIDATION_ERROR')


def test_at_most_twenty_available_cases_are_listed(client, identities, flow_engine):
    lodged = [lodge(client, identities, 'customer_a', f'Request number {n}.', f'list-a-many-{n}') for n in range(21)]
    assert [item['case_id'] for item in own(client, identities, 'customer_a').json()['items']] == lodged[::-1][:20]
    # A case that is no longer available (removed under the retention rules) is not listed.
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        uow.execute(update(t.case_heads).where(t.case_heads.c.case_id == lodged[-1]).values(available=False))
        uow.commit()
    assert [item['case_id'] for item in own(client, identities, 'customer_a').json()['items']] == lodged[-2::-1][:20]
