"""demo.py renew-sessions: new access keys for a kept Railway deployment (31 October 2026).

The data, the signing key and the passwords stay; only sessions.json is new, and its keys
sign in. A person who no longer exists or is disabled stops the renewal and leaves the old
file in place, so the start begins a fresh demonstration. NFR-003, NFR-004.
"""
import base64
import json
import pytest
from returnops_api import demo
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_domain.customer_service import CustomerFlow
from returnops_domain.errors import FlowError
from returnops_domain.registry import TrustedRegistry


def private_dir(tmp_path, identities, names=('customer_a', 'founder')):
    folder = tmp_path / 'demo-shop'
    folder.mkdir()
    config = identities.auth_config
    (folder / 'auth.json').write_text(json.dumps({'issuer': config.issuer, 'audience': config.audience,
        'signing_key_base64': base64.b64encode(config.signing_key).decode('ascii')}), encoding='utf-8')
    principals = [{key: identities.people[name][key] for key in ('principal_id', 'role', 'store_id', 'enabled')} for name in names]
    (folder / 'sessions.json').write_text(json.dumps({'principals': principals, 'sessions': [], 'tokens': {}}), encoding='utf-8')
    return folder


def test_new_sessions_sign_in_and_keep_the_people(flow_engine, identities, tmp_path):
    folder = private_dir(tmp_path, identities)
    demo.renew_sessions(folder, engine=flow_engine)
    renewed = json.loads((folder / 'sessions.json').read_text(encoding='utf-8'))
    assert [p['principal_id'] for p in renewed['principals']] == [identities.people[n]['principal_id'] for n in ('customer_a', 'founder')]
    assert all(row['expires_at'] - row['issued_at'] == 900 for row in renewed['sessions'])
    for name in ('customer_a', 'founder'):
        principal_id = identities.people[name]['principal_id']
        flow = CustomerFlow(flow_engine, CurrentRequestAuthority(identities.auth_config, 'Bearer ' + renewed['tokens'][principal_id]))
        assert flow.session().body['principal_id'] == principal_id


def test_a_disabled_person_stops_the_renewal_and_leaves_the_file(flow_engine, identities, tmp_path):
    folder = private_dir(tmp_path, identities)
    before = (folder / 'sessions.json').read_bytes()
    TrustedRegistry(flow_engine).change_principal(identities.people['founder']['principal_id'], enabled=False)
    with pytest.raises(FlowError):
        demo.renew_sessions(folder, engine=flow_engine)
    assert (folder / 'sessions.json').read_bytes() == before
    with pytest.raises(ValueError):
        demo.renew_sessions('relative/demo-shop', engine=flow_engine)
