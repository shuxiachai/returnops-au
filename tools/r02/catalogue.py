"""Deterministic synthetic-cups order catalogue for the R.02 driver; not installed.

Same document shape, provider, dataset version and line items as the test-only
tests/lifecycle/pass_review_helpers.catalogue(), but with fixed snapshot/order
identities and timestamps instead of identifier()/now(). For the same store and
owner the document bytes and dataset_sha256 (mock_orders._document) are
therefore identical on every run, so InvestigationPolicy.configure() and the
driver's InvestigationProcessor(catalogue=...) always bind the same metadata.
"""
import json

from returnops_domain.mock_orders import SyntheticCatalogue
from returnops_domain.pass_scenario import SCENARIO

ORDER_REFERENCE = 'SYN-CUPS-PASS'
PROVIDER_ID = 'synthetic_commerce'
PROVIDER_VERSION = 'mock-orders-v1'
SNAPSHOT_ID = 'r02_cups_snapshot_v1'
ORDER_ID = 'r02_cups_order_v1'
PURCHASED_AT = '2026-10-01T00:00:00Z'
RETRIEVED_AT = '2026-10-02T00:00:00Z'
# pass_scenario.verify_scenario accepts exactly these two lines.
LINE_ITEMS = (
    dict(line_item_id='line-mug-blue', sku='SYN-CUP-BLUE', description='Synthetic blue cup', quantity=1, unit_price_minor=1000),
    dict(line_item_id='line-mug-white', sku='SYN-CUP-WHITE', description='Synthetic white cup', quantity=1, unit_price_minor=1000),
)


def document(store_id, owner_principal_id):
    """The explicit synthetic catalogue document; a fresh copy on every call."""
    snapshot = dict(snapshot_id=SNAPSHOT_ID, order_id=ORDER_ID, provider_id=PROVIDER_ID, snapshot_version=1,
                    purchased_at=PURCHASED_AT, currency='AUD', retrieved_at=RETRIEVED_AT,
                    line_items=[dict(line) for line in LINE_ITEMS])
    return dict(is_synthetic=True, format_version=1, dataset_version=SCENARIO, provider_id=PROVIDER_ID,
                provider_version=PROVIDER_VERSION, orders=[dict(store_id=store_id, owner_principal_id=owner_principal_id,
                                                                order_reference=ORDER_REFERENCE, snapshot=snapshot)])


def document_bytes(store_id, owner_principal_id):
    """Stable ASCII/LF JSON written next to the run receipt; it holds no secret."""
    text = json.dumps(document(store_id, owner_principal_id), sort_keys=True, indent=2, ensure_ascii=True)
    return (text + '\n').encode('ascii')


def load(store_id, owner_principal_id):
    """Validated immutable catalogue; malformed input raises, never falls back."""
    return SyntheticCatalogue.from_document(document(store_id, owner_principal_id))
