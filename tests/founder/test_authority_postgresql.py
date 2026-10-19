"""Authority remains current on every page and before metadata commit."""
from datetime import datetime, timezone
import time
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_api.main import create_app
from returnops_domain import customer_tables as t, founder_tables as f
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.founder_service import FounderQueries
from returnops_domain.registry import TrustedRegistry
from founder_helpers import accepted, founder, rows


@pytest.mark.parametrize('change,expected', [('revoked', 401), ('disabled', 401), ('role', 403), ('store', 404), ('unavailable', 404)])
def test_existing_cursor_does_not_preserve_authority(flow_engine, identities, change, expected):
    case_id = accepted(identities)['case_id']
    token = founder(flow_engine, identities).read('getFounderCase', case_id).body['collection_windows']['statements']['start_cursor']
    registry = TrustedRegistry(flow_engine)
    principal = identities.people['founder']['principal_id']
    if change == 'revoked':
        registry.revoke_session(identities.sessions['founder']['session_id'])
    elif change == 'disabled':
        registry.change_principal(principal, enabled=False)
    elif change == 'role':
        registry.change_principal(principal, role='CUSTOMER')
    elif change == 'store':
        registry.change_principal(principal, store_id='store_elsewhere')
    else:
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            uow.execute(update(t.case_heads).where(t.case_heads.c.case_id == case_id).values(available=False))
            uow.commit()
    with TestClient(create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False)) as client:
        response = client.get('/v1/founder/cases/' + case_id + '/history', params={'kind': 'STATEMENT', 'cursor': token},
                              headers={'Authorization': 'Bearer ' + identities.tokens['founder']})
        assert response.status_code == expected
        if change == 'store':
            assert client.get('/v1/founder/cases', headers={'Authorization': 'Bearer ' + identities.tokens['founder']}).json()['items'] == []


def test_absent_customer_expired_and_forged_bearers_fail_before_query_data(flow_engine, identities):
    case_id = accepted(identities)['case_id']
    config = identities.auth_config
    now = int(time.time())
    session = identities.sessions['founder']
    expired = jwt.encode({'iss': config.issuer, 'aud': config.audience, 'sub': session['principal_id'], 'jti': session['session_id'],
        'iat': now - 60, 'nbf': now - 60, 'exp': now - 1}, config.signing_key, algorithm='HS256')
    forged = jwt.encode({'iss': config.issuer, 'aud': config.audience, 'sub': session['principal_id'], 'jti': session['session_id'],
        'iat': now - 1, 'nbf': now - 1, 'exp': now + 600}, b'not-the-private-key-for-this-app-00000', algorithm='HS256')
    cases = [({}, 401), ({'Authorization': 'Bearer ' + identities.tokens['customer_a']}, 403),
             ({'Authorization': 'Bearer ' + expired}, 401), ({'Authorization': 'Bearer ' + forged}, 401)]
    with TestClient(create_app(engine=flow_engine, auth_config=config, enable_processor=False)) as client:
        for headers, expected in cases:
            for suffix in ['', '/' + case_id, '/' + case_id + '/history?kind=STATEMENT', '/' + case_id + '/audit']:
                response = client.get('/v1/founder/cases' + suffix, headers=headers)
                assert response.status_code == expected
        assert client.get('/v1/founder/cases?role=FOUNDER&store_id=synthetic_au_store', headers=cases[1][0]).status_code == 403
        assert client.get('/v1/founder/cases', headers=[('Authorization', 'Bearer ' + identities.tokens['founder']), ('Authorization', 'Bearer other')]).status_code == 401
    assert rows(flow_engine, f.snapshots) == []


def test_current_authority_rechecked_after_read_rolls_back_metadata(flow_engine, identities):
    case_id = accepted(identities)['case_id']
    actual = CurrentRequestAuthority(identities.auth_config, 'Bearer ' + identities.tokens['founder'])
    calls = []
    def expire(connection, operation, resource_id=None):
        calls.append(operation)
        if len(calls) == 3:
            # A controlled same-connection dependency models expiry at recheck,
            # not an HTTP-supplied actor or a second-connection race bypass.
            connection.execute(update(t.sessions).where(t.sessions.c.session_id == identities.sessions['founder']['session_id']).values(revoked=True))
        return actual(connection, operation, resource_id)
    with pytest.raises(FlowError) as error:
        FounderQueries(flow_engine, expire).read('getFounderCase', case_id)
    assert error.value.code == 'UNAUTHENTICATED'
    assert rows(flow_engine, f.snapshots) == []
    assert not next(row for row in rows(flow_engine, t.sessions) if row['session_id'] == identities.sessions['founder']['session_id'])['revoked']


def test_global_fence_linearizes_read_before_revocation_without_lock_upgrade(flow_engine, identities):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    case_id = accepted(identities)['case_id']
    entered, release, revoking = Event(), Event(), Event()
    actual = CurrentRequestAuthority(identities.auth_config, 'Bearer ' + identities.tokens['founder'])
    count = 0
    def paused(connection, operation, resource_id=None):
        nonlocal count
        result = actual(connection, operation, resource_id)
        count += 1
        if count == 2:
            entered.set()
            assert release.wait(5)
        return result
    def revoke():
        revoking.set()
        TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
    with ThreadPoolExecutor(max_workers=2) as executor:
        read = executor.submit(FounderQueries(flow_engine, paused).read, 'getFounderCase', case_id)
        assert entered.wait(5)
        revocation = executor.submit(revoke)
        assert revoking.wait(5)
        assert not revocation.done()
        release.set()
        assert read.result(timeout=10).status == 200
        revocation.result(timeout=10)
    with pytest.raises(FlowError) as error:
        founder(flow_engine, identities).read('getFounderCase', case_id)
    assert error.value.code == 'UNAUTHENTICATED'
