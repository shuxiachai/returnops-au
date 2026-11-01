"""A3 offline recovery evidence: the carrier sandbox plus the adapter's HTTP logic, no database.

docs/49-a3-carrier-sandbox.md; OF-004, FR-010, UC-04, NFR-004, NFR-007.

Starts the contract-test carrier sandbox on 127.0.0.1 inside this process and
runs the adapter's HTTP logic (label_request and CarrierLabelClient.create_label,
the functions SandboxCarrierLabel._outcome calls) through each scenario with a
fresh synthetic idempotency key. It prints one fields-only JSON receipt:
scenario, expected and actual outcome, the adapter's attempts (phase, method,
route, status, X-Request-Id, elapsed ms), the sandbox's own log for the
scenario's correlation ID, and the labels stored for the scenario's key. Keys,
the test key and request bodies are never printed. No carrier is contacted, no
database is used and no label is real. Exit status 0 only when every scenario
ends as expected.

    python -B tools/carrier_sandbox/run_recovery_demo.py
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'packages'))

from returnops_domain.carrier_adapter import CarrierLabelClient, dispatch_budget, label_request  # noqa: E402
from returnops_domain.carrier_sandbox import CarrierSandbox, identifier  # noqa: E402

PROFILE = 'a3-carrier-sandbox-recovery/v1'
REQUEST_TIMEOUT = 0.5
# name, fault, times (None: every POST), fault delay, expected outcome,
# expected adapter attempts (status, or the transport error), expected sandbox log
# (sorted method/status pairs), labels stored for the key afterwards.
SCENARIOS = (
    ('normal', None, None, None, 'SUCCEEDED', [201], [('POST', 201)], 1),
    ('error_before_commit', 'error_before_commit', 1, None, 'SUCCEEDED', [503, 404, 201],
     [('GET', 404), ('POST', 201), ('POST', 503)], 1),
    ('timeout_after_commit', 'timeout_after_commit', 1, 1.5, 'SUCCEEDED', ['TIMEOUT', 200],
     [('GET', 200), ('POST', 201)], 1),
    ('reject_auth', 'reject_auth', 1, None, 'FAILED', [401], [('POST', 401)], 0),
    ('invalid', 'invalid', 1, None, 'FAILED', [422], [('POST', 422)], 0),
    ('late_original', 'delay_before_commit', 1, 1.2, 'SUCCEEDED', ['TIMEOUT', 404, 201],
     [('GET', 404), ('POST', 200), ('POST', 201)], 1),
    ('still_unknown', 'error_before_commit', None, None, 'UNKNOWN', [503, 404, 503, 404],
     [('GET', 404), ('GET', 404), ('POST', 503), ('POST', 503)], 0),
)


def synthetic_dispatch(name):
    """A synthetic control row and approved GENERATE_LABEL command, as the core passes them."""
    control = dict(effect_key=f'leffect_demo_{name}_' + identifier('K', 8), parcel_id=f'parcel_demo_{name}',
                   provider_return_id=f'return_demo_{name}',
                   dispatch_deadline=datetime.now(timezone.utc) + timedelta(seconds=30))
    command = dict(command_id=f'label_cmd_demo_{name}', type='GENERATE_LABEL', provider_id='provider-mock-label',
                   parameters=dict(parcel_id=control['parcel_id'], return_command_id=f'return_cmd_demo_{name}',
                                   label_format='PDF', chargeable=False))
    return control, command


def run_scenario(sandbox, client, scenario):
    name, fault, times, delay, expected, attempts_expected, server_expected, labels_expected = scenario
    control, command = synthetic_dispatch(name)
    sandbox.clear()
    if fault is not None:
        sandbox.inject(fault, times=times, delay=delay)
    result = client.create_label(control['effect_key'], label_request(control, command),
                                 budget_seconds=dispatch_budget(control['dispatch_deadline']))
    sandbox.clear()
    idle = sandbox.wait_idle(10)
    server = [{field: entry[field] for field in ('method', 'route', 'status', 'request_id', 'fault')}
              for entry in sandbox.requests(result.correlation_id)]
    labels = sandbox.labels_for_key(control['effect_key'])
    seen = [attempt['status'] if attempt['status'] is not None else attempt['error'] for attempt in result.attempts]
    checks = dict(outcome=result.outcome == expected, attempts=seen == attempts_expected,
                  sandbox_log=idle and sorted((entry['method'], entry['status']) for entry in server) == server_expected,
                  labels_for_key=labels == labels_expected)
    receipt = result.receipt()
    return dict(scenario=name, fault=fault, fault_repeats='every POST' if fault and times is None else times,
                expected_outcome=expected, outcome=result.outcome, error=result.error, recovered=result.recovered,
                correlation_id=result.correlation_id,
                label_id=None if result.label is None else result.label['label_id'],
                attempts=receipt['attempts'], sandbox_requests=server, labels_for_key=labels,
                checks=checks, passed=all(checks.values()))


def main() -> int:
    recorded_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    results = []
    with CarrierSandbox() as sandbox:
        client = CarrierLabelClient(sandbox.base_url, request_timeout=REQUEST_TIMEOUT)
        for scenario in SCENARIOS:
            try:
                results.append(run_scenario(sandbox, client, scenario))
            except Exception as error:  # Report and fail; never hide an unexpected path.
                results.append(dict(scenario=scenario[0], passed=False, error=type(error).__name__))
        total = sandbox.label_count()
    passed = all(entry['passed'] for entry in results) and total == sum(entry[-1] for entry in SCENARIOS)
    receipt = dict(profile=PROFILE, recorded_at=recorded_at, environment='LOCAL_CONTRACT_TEST_SANDBOX',
                   real_carrier=False, database=False, request_timeout_seconds=REQUEST_TIMEOUT,
                   scenarios=results, labels_stored_total=total, passed=passed,
                   limits='Contract-test sandbox in this repository on 127.0.0.1; not a carrier test environment.')
    print(json.dumps(receipt, indent=2, sort_keys=False, ensure_ascii=True))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
