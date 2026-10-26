"""docs/45 S3: demo.py's opt-in manual-handling grant over actual PostgreSQL.

A SYN-CONFLICT case escalates after order investigation with an order-lookup block
and no proposal. Without the grant the Founder's MANUAL_HANDLING is refused 403
FORBIDDEN with no business effect (pass 0, docs/47 section 5); after
demo.grant_founder_manual it is accepted once through the real decision route and
the case waits for its notification. The grant is one lifecycle authority row,
the same as tests/lifecycle/manual_helpers.provision_outcome.
FR-009/FR-012; NFR-002/NFR-006; docs/08 A2.07.
"""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from returnops_api import demo
from returnops_api.main import create_app
from returnops_domain import lifecycle_tables as life
from returnops_domain.manual_denial import COMPONENT
from returnops_domain.wire import validate

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lifecycle'))
import manual_helpers  # noqa: E402
from manual_helpers import rows, snapshot  # noqa: E402
from pass_revision_helpers import business_snapshot  # noqa: E402

STORE = 'synthetic_au_store'


def _client(flow_engine, identities):
    return TestClient(create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False,
                                 enable_fixed_proposal=False, enable_founder_decisions=True))


def _founder(identities, key=None):
    headers = {'Authorization': 'Bearer ' + identities.tokens['founder']}
    if key is not None:
        headers['Idempotency-Key'] = key
    return headers


def _grants(flow_engine):
    return sorted((r['store_id'], r['component_id'], r['purpose'], r['revision'], r['enabled'])
                  for r in rows(flow_engine, life.authorities))


def test_manual_handling_is_refused_without_the_demo_grant_and_accepted_with_it(flow_engine, identities, enabled):
    case, body = manual_helpers.ready(flow_engine, identities, 'block', grant=False)
    assert _grants(flow_engine) == []
    with _client(flow_engine, identities) as client:
        view = client.get('/v1/founder/cases/' + case, headers=_founder(identities))
        assert view.status_code == 200, view.text
        detail = view.json()
        assert detail['status'] == 'ESCALATED' and 'current_proposal' not in detail
        assert detail['order_lookup_block']['block_id'] == body['order_lookup_block_id']
        assert detail['order_lookup_block']['status'] == 'CONFLICT'

        # Taken after the read, which records its own Founder read snapshot rows.
        before = business_snapshot(snapshot(flow_engine))
        refused = client.post('/v1/founder/cases/' + case + '/decisions', json=body,
                              headers=_founder(identities, 'demo-manual-refused'))
        assert refused.status_code == 403, refused.text
        assert refused.json()['error']['code'] == 'FORBIDDEN'
        assert business_snapshot(snapshot(flow_engine)) == before

        demo.grant_founder_manual(flow_engine, STORE)
        assert _grants(flow_engine) == [(STORE, COMPONENT, 'OUTCOME', 1, True)]
        accepted = client.post('/v1/founder/cases/' + case + '/decisions', json=body,
                               headers=_founder(identities, 'demo-manual-accepted'))
        assert accepted.status_code == 202, accepted.text
        receipt = validate('DecisionReceipt', accepted.json(), internal=True)
        assert receipt['case_id'] == case and receipt['decision'] == 'MANUAL_HANDLING'
        assert receipt['processing_status'] == 'ACCEPTED' and 'approval_id' not in receipt
        manual_helpers.assert_pending(flow_engine, case, body,
            SimpleNamespace(status='ACCEPTED', safe_code=None, audit='NOT_ATTEMPTED', receipt=receipt))
        assert client.get('/v1/founder/cases/' + case, headers=_founder(identities)).json()['status'] == 'NOTIFICATION_PENDING'
    # The grant conferred nothing else: no approval or execution authority appeared.
    assert _grants(flow_engine) == [(STORE, COMPONENT, 'OUTCOME', 1, True)]


def test_the_demo_grant_is_idempotent_and_never_re_enables_a_disabled_authority(flow_engine):
    demo.grant_founder_manual(flow_engine, STORE)
    demo.grant_founder_manual(flow_engine, STORE)
    assert _grants(flow_engine) == [(STORE, COMPONENT, 'OUTCOME', 1, True)]
    with flow_engine.begin() as connection:
        connection.execute(life.authorities.update().values(enabled=False))
    with pytest.raises(ValueError, match='does not re-enable'):
        demo.grant_founder_manual(flow_engine, STORE)
    assert _grants(flow_engine) == [(STORE, COMPONENT, 'OUTCOME', 1, False)]
