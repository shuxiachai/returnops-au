# A1.04 independent synthetic order provider

The callable component is tracked by [Issue25](https://github.com/shuxiachai/returnops-au/issues/25) on the technical baseline main6554132bf73fb6d8e5357f24ffeec738db1010e0 after PR24. KAN-29 is the recorded14September Jira mapping, not a current Jira status check. A1.04 remains OwnerA/ReviewerC, S=F.01 and F=A1.01; no WBS or personal/joint acceptance is changed. Use the actual source PR and CI for publication/review status.

## Traceability

The bounded delivery is [A1.04 in the work-package table](08-delivery-work-packages.md), with recorded Jira KAN-29. The exact requirement definitions are in [FR-003, NFR-004 and NFR-007](00-project-definition-v1.md):

| Requirement | This component's evidence |
|---|---|
| FR-003: typed read-only order snapshot | All five frozen outcomes, snapshot/line-item validation and scoped lookup contract tests |
| NFR-004: reliability without duplicate effects or illegal mutation | Stable repeated/parallel reads, explicit source failures, immutable generations and no lookup writes; mutation/retry workflows remain outside A1.04 |
| NFR-007: replaceable typed/versioned dependencies | Neutral resolver/source ports, immutable dataset/provider versions, packaged resource and isolated wheel/image lookup |

The concrete DTO authority is the [frozen OrderLookupRequest/OrderLookupResult/OrderSnapshot/LineItem schemas](../contracts/v1/schemas.json), explained by the [v1 interface contract](09-interface-contract-v1.md). `OrderLookupPort.lookup` implements the read-only role modeled as `OrderProviderPort.lookup_read_only` and `MockOrderAdapter` in the [shared class diagram](diagrams/01-domain-class-diagram.md). The [shared investigation sequence](diagrams/03-sequence-diagram.md) shows the five-result branch; [CS-02 connectors A14/A18](13-shared-composite-structure.md) distinguish order lookup from later Domain receipt acceptance, and [package P10](15-package-deployment-models.md) keeps the read-only adapter separate from effects. These links document alignment; no diagram or existing model text is changed.

## Scope and usage

`returnops_domain.mock_orders.MockOrderProvider` implements the neutral `OrderLookupPort`. It reads a packaged synthetic catalogue and returns the existing frozen `OrderLookupResult`. It does not register HTTP routes, call a model/network/provider, touch PostgreSQL, change orders/payment/inventory or increment case/input versions. Current customer-worker behavior is unchanged. Later A1.05 supplies real Domain/worker integration.

The resolver and source are constructor-injected trusted composition. The request may contain only `case_id`, `input_version` and optional `order_reference`; it cannot choose an owner, store, service, provider, dataset or permission. A resolver runs on every lookup, checks current case access/input and returns an immutable `OrderReadContext`. Provider-read permission is bound to the actual composed provider and service. The following example grants only one explicit synthetic case/version; it is not a DB or F.03 integration:

```python
from returnops_domain.mock_orders import MockOrderProvider, load_builtin_catalogue
from returnops_domain.order_ports import OrderLookupError, OrderReadContext

catalogue = load_builtin_catalogue()  # explicit resource read, never import-time seeding

class SyntheticExampleContext:
    def resolve(self, case_id, input_version):
        if case_id != "synthetic_example_case":
            raise OrderLookupError("CASE_ACCESS_DENIED")
        if input_version != 1:
            raise OrderLookupError("STALE_INPUT")
        return OrderReadContext(
            case_id, input_version, "synthetic_au_store", "synthetic_customer_a",
            "synthetic_example_service", catalogue.metadata.provider_id, True,
        )

provider = MockOrderProvider(
    SyntheticExampleContext(), catalogue, service_id="synthetic_example_service"
)
result = provider.lookup({
    "case_id": "synthetic_example_case", "input_version": 1,
    "order_reference": "SYN-1001",
})
assert result["status"] == "MATCHED"
assert result["input_version"] == 1
```

Malformed requests, denied case access, stale input or unavailable/mismatched trusted context raise allowlisted `OrderLookupError` codes. They do not fabricate a provider business result. Resolver failure never reads the order source. Integral JSON numbers normalize using the existing private codec rules; booleans and fractional versions remain invalid.

| Outcome | Condition |
|---|---|
| MATCHED | One valid exact reference in the authorized store/owner scope; includes snapshot |
| NOT_FOUND | No supplied reference or no scoped match; foreign and nonexistent references have the same generic result |
| CONFLICT | Multiple valid distinct orders match in that scope; contains no candidate snapshots |
| AUTHORITY_DENIED | Case access is established but the composed provider read permission is absent; no source read |
| PROVIDER_FAILURE | The explicitly injected trusted source fails or returns invalid observations; no raw exception detail |

Only MATCHED includes a snapshot. Messages are fixed allowlisted strings, with no order reference, owner, path or exception text. `PROVIDER_FAILURE` is a normal reference string if submitted by a caller; technical faults are injected through a trusted test source, never magic customer input. References are compared exactly without trimming or case folding.

## Immutable synthetic provenance

`order_data/synthetic_orders_v1.json` is a versioned package resource loaded with `importlib.resources`. Its `is_synthetic` marker, format/dataset/provider versions, scope IDs and every snapshot are validated on explicit load; corrupt initialization fails closed. The six records contain only invented data. The other-owner/store entries are authorization isolation negatives, not a new multi-store product feature. They are separate from Gold/pilot data and C's corpus; the MVP remains one Australian store.

Each snapshot has stable ID/order/provider/version, AUD currency, unique line IDs, quantity1–999 and nonnegative integral minor-unit prices. `retrieved_at` is the fixed synthetic capture time, not the current lookup clock. Internal records retain immutable typed bytes; results are independent dict/list copies. `provider.metadata` is immutable and exposes the dataset/provider versions and SHA256 of the versioned typed canonical catalogue document (`synthetic-orders/v1`), including scopes. This is a semantic-content hash, not a hash of JSON whitespace or file bytes.

`catalogue.replacement(document)` validates and constructs a **new immutable synthetic dataset/instance**. It does not modify an existing order, mutate the old instance, accept Domain facts or execute an A1.05 version migration. A replacement requires a new dataset version. Known snapshot identity/version cannot gain different content; changed snapshot content requires a greater snapshot version, while order/scope identity remains bound. A provider captures one source generation; swapping it behind an existing provider fails safely. Create a new trusted composition to use a new dataset. No global cross-process catalogue-history registry is introduced.

## Later Domain acceptance boundary

This component echoes the current request case/input and returns an observation. It does not authorize later persistence. A1.05 must provide authoritative current case access, owner/store/service/provider entitlement and recheck the source/work/claim/input binding in its result-acceptance transaction. An expired original HTTP bearer is not the durable SERVICE identity.

Later Domain code preserves the original lookup request/result at inputn, and can separately create an explicitly accepted projection at n+1 if genuinely new verified order facts are accepted. It must not rewrite the raw receipt to pretend the provider originally returned n+1. Repeated identical snapshot identity/version/content must not repeatedly advance input, and conflicting content at the same identity/version must be refused. These are the documented later integration requirements, not behavior claimed by this independent provider.

## Checks and installation

No dependency was added. With the committed locked environment and installed package:

```powershell
python -B -m pytest tests/orders -q
python -B tools/checks/run.py offline --baseline-ref <verified-main-commit>
python -B tools/checks/check-installed.py
```

The offline runner includes the order tests alongside the existing contracts/model/tool checks. The package check builds and installs a wheel into an owned temporary directory, imports outside the checkout, loads the packaged catalogue and performs an actual scoped lookup. The runtime-image CI runs the same probe via stdin from `/tmp`, under the image's existing non-root user; the data resource is explicitly included in the Docker build context.

Focused tests cover all five outcomes, frozen DTO validation, exact reference edges, provider-bound permission, fresh revocation/context checks, safe exception chains, corrupt configuration and line-item constraints, concurrent/read-only behavior, independent copies and new-instance replacement. There is no local PostgreSQL test claim for this pure component; the existing full environment suite remains selected by CI without changing its behavior.
