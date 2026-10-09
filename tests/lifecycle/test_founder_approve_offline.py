"""Offline builder/request/UNKNOWN boundaries only; no database claim is made."""
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from returnops_domain.audit import identifier
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError
from returnops_domain.preview_profile import PROFILE, build, profile, selected_lines


def packet():
    return dict(case_id=identifier('case'), input_version=2, proposal_id=identifier('proposal'),
        proposal_version=1, facts=dict(line_items=[dict(line_item_id='line-b', quantity=1),
        dict(line_item_id='line-a', quantity=2)]))


def order():
    return dict(order_id=identifier('order'), line_items=[dict(line_item_id='line-a', quantity=2),
        dict(line_item_id='line-b', quantity=1)])


def test_AP02_profile_is_server_owned_and_line_selection_is_sorted():
    first, second = profile(), profile()
    assert first == PROFILE and first is not second
    first['currency'] = 'USD'
    assert profile()['currency'] == 'AUD'
    assert selected_lines(packet(), order()) == [dict(line_item_id='line-a', quantity=2),
        dict(line_item_id='line-b', quantity=1)]


@pytest.mark.parametrize('lines', [[], [dict(line_item_id='line-a', quantity=1)] * 2,
    [dict(line_item_id='line-a', quantity=3)], [dict(line_item_id='missing-line', quantity=1)],
    [dict(line_item_id='line-a', quantity=1.0)], [dict(line_item_id='line-a', quantity=True)],
    [dict(line_item_id='行项目', quantity=1)]])
def test_AP02_profile_rejects_invalid_or_untrusted_line_selection(lines):
    value = packet(); value['facts']['line_items'] = lines
    with pytest.raises(FlowError):
        selected_lines(value, order())


@pytest.mark.parametrize('count', [1, 100])
def test_AP02_profile_accepts_one_through_one_hundred_lines(count):
    lines = [dict(line_item_id='line-' + str(index).zfill(3), quantity=1) for index in range(count)]
    value = packet(); value['facts']['line_items'] = list(reversed(lines))
    assert selected_lines(value, dict(order_id=identifier('order'), line_items=lines)) == lines


def test_AP02_profile_rejects_one_hundred_and_one_lines():
    lines = [dict(line_item_id='line-' + str(index).zfill(3), quantity=1) for index in range(101)]
    value = packet(); value['facts']['line_items'] = lines
    with pytest.raises(FlowError):
        selected_lines(value, dict(order_id=identifier('order'), line_items=lines))


def test_AP02_builder_uses_fixed_policy_and_binds_label_to_return():
    from datetime import datetime, timezone
    review = dict(review_id=identifier('review'))
    value = build(identifier('preview'), dict(packet=packet(), order_lookup=dict(status='MATCHED', snapshot=order())),
        review, datetime.now(timezone.utc), profile())
    scope = value['scope']
    assert scope['currency'] == 'AUD' and scope['amount_ceiling_minor'] == 0
    assert scope['environment'] == 'SIMULATED' and scope['allowlist_version'] == 'mock-v1'
    assert scope['commands'][1]['parameters']['return_command_id'] == scope['commands'][0]['command_id']


def test_AP02_scope_fingerprint_changes_for_command_order_or_scope_value():
    from datetime import datetime, timezone
    from returnops_domain.lifecycle_effects import fingerprint
    value = build(identifier('preview'), dict(packet=packet(), order_lookup=dict(status='MATCHED', snapshot=order())),
        dict(review_id=identifier('review')), datetime.now(timezone.utc), profile())
    swapped = deepcopy(value['scope']); swapped['commands'].reverse()
    changed = deepcopy(value['scope']); changed['amount_ceiling_minor'] = 1
    assert fingerprint(swapped) != value['scope_fingerprint']
    assert fingerprint(changed) != value['scope_fingerprint']


def test_AP02_builder_rejects_policy_substitution():
    from datetime import datetime, timezone
    bad = profile(); bad['return_provider'] = 'real-provider'
    with pytest.raises(FlowError):
        build(identifier('preview'), dict(packet=packet(), order_lookup=dict(status='MATCHED', snapshot=order())),
            dict(review_id=identifier('review')), datetime.now(timezone.utc), bad)


def test_AP06_approve_request_is_frozen_and_uses_its_own_domain():
    from returnops_domain.approve_decision import FounderApproveService
    from returnops_domain.canonical import digest
    request = dict(expected_case_version=7, proposal_id=identifier('proposal'), proposal_version=1,
        decision='APPROVE', reason='Approve this exact preview.', preview_id=identifier('preview'),
        scope_fingerprint='a' * 64)
    supplied = deepcopy(request)
    assert FounderApproveService._request(supplied) == request
    supplied['reason'] = 'changed later'
    assert FounderApproveService._request(request)['reason'] == 'Approve this exact preview.'
    observed = []
    def lookup(uow, actor, operation, case_id, key, fingerprint, **options):
        observed.append((operation, case_id, key, fingerprint)); return None
    from returnops_domain import idempotency
    original = idempotency.lookup; idempotency.lookup = lookup
    try:
        _, fingerprint = FounderApproveService(object(), object())._lookup(object(),
            SimpleNamespace(store_id='store_fixture'), {'case_id':'case_fixture'}, request, 'key')
    finally:
        idempotency.lookup = original
    assert fingerprint == digest(request, 'founder-approve-request/v1')
    assert observed[0][:3] == ('recordFounderDecision', 'case_fixture', 'key')


@pytest.mark.parametrize('patch', [
    {'decision':'REJECT'}, {'preview_id':''}, {'scope_fingerprint':'x'}, {'principal_id':'forged'},
    {'expected_case_version':0}, {'proposal_version':0}, {'reason':''}, {'reason':'x'*2001},
    {'provider_id':'forged'}, {'commands':[]}, {'expires_at':'forged'},
])
def test_AP06_approve_request_rejects_untrusted_or_invalid_fields(patch):
    from returnops_domain.approve_decision import FounderApproveService
    request = dict(expected_case_version=7, proposal_id=identifier('proposal'), proposal_version=1,
        decision='APPROVE', reason='Approve this exact preview.', preview_id=identifier('preview'),
        scope_fingerprint='a' * 64)
    with pytest.raises(FlowError):
        FounderApproveService._request({**request, **patch})


def test_AP20_composition_does_not_connect_or_provision_execution():
    from returnops_api.private_approve import compose_private_approve
    from returnops_api.private_preview import compose_private_preview
    from returnops_api.security.authentication import AuthConfig
    class NeverConnect:
        def __getattr__(self, name):
            raise AssertionError('composition touched engine ' + name)
    engine = NeverConnect(); auth = AuthConfig('fixture-issuer', 'fixture-audience', b'x' * 32)
    assert compose_private_preview(engine).engine is engine
    assert compose_private_approve(engine, auth, None).engine is engine


@pytest.mark.parametrize('operation', ['accept', 'recover'])
def test_AP14_unknown_never_retries_or_claims_execution(monkeypatch, operation):
    from returnops_domain.approve_decision import FounderApproveService
    request = dict(expected_case_version=7, proposal_id=identifier('proposal'), proposal_version=1,
        decision='APPROVE', reason='Approve this exact preview.', preview_id=identifier('preview'),
        scope_fingerprint='a' * 64)
    calls = []
    class UnknownUow:
        def __init__(self, *args, **kwargs): calls.append('construct')
        def __enter__(self): calls.append('enter'); raise AcceptanceOutcomeUnknown()
        def __exit__(self, *args): raise AssertionError('unentered UoW cannot exit')
    service = FounderApproveService(object(), object(), uow_factory=UnknownUow, recovery_uow=UnknownUow)
    result = (service.accept('case_fixture', request, 'key', 'corr_fixture') if operation == 'accept'
        else service.recover('case_fixture', request, 'key'))
    assert asdict(result) == dict(status='UNKNOWN', receipt=None, safe_code=None, audit='NOT_ATTEMPTED')
    assert calls == ['construct', 'enter']
