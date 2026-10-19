"""PMP02/05/08 offline fail-closed routing and no-connection boundaries only."""
from dataclasses import asdict

import pytest

from returnops_api.private_manual import compose_private_manual
from returnops_api.security.authentication import AuthConfig
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError
from returnops_domain.manual_decision import FounderDecisionService


REQUEST = dict(expected_case_version=7, proposal_id='proposal_fixture', proposal_version=1,
    decision='MANUAL_HANDLING', reason='The Founder will handle the retained proposal.')


@pytest.mark.parametrize('patch', [
    {'decision':'APPROVE'}, {'decision':'REJECT'}, {'decision':'REQUEST_REVISION'},
    {'principal_id':'forged'}, {'risk_outcome':'PASS'}, {'review_id':'forged'},
    {'preview_id':'forged'}, {'scope_fingerprint':'a' * 64}, {'grant':'forged'},
    {'generation':1}, {'processing_failure_id':'mixed_target'}, {'order_lookup_block_id':'mixed_target'},
])
def test_PMP02_offline_request_cannot_supply_provenance_or_authority(patch):
    with pytest.raises(FlowError):
        FounderDecisionService._request({**REQUEST, **patch})


@pytest.mark.parametrize('family', ['REVIEW_ESCALATE', 'PROPOSAL', 'OUTCOME', ''])
@pytest.mark.parametrize('historical', [False, True])
def test_PMP02_offline_unknown_persisted_family_cannot_fall_back(monkeypatch, family, historical):
    from returnops_domain import pass_manual_sources, pass_review_sources, review_sources
    class PoisonOnly:
        poisoned = False
        def poison(self):
            self.poisoned = True
    uow = PoisonOnly()
    reads = []
    def persisted(uow, table, **keys):
        reads.append(keys['record_id'])
        return {'event_kind':family}
    def no_alternate(*args, **kwargs):
        raise AssertionError('An unrecognized family must not try either source proof')
    monkeypatch.setattr(pass_manual_sources, 'one', persisted)
    monkeypatch.setattr(pass_review_sources, 'accepted_review', no_alternate)
    monkeypatch.setattr(review_sources, 'accepted_review', no_alternate)
    with pytest.raises(FlowError):
        pass_manual_sources._review(uow, {}, {'review_record_id':'current_review'}, 'founder-manual-v1',
            record_id='original_review' if historical else None, current=not historical)
    assert uow.poisoned and reads == ['original_review' if historical else 'current_review']


def test_PMP08_offline_private_composition_cannot_connect_or_provision():
    class NeverConnect:
        def __getattr__(self, name):
            raise AssertionError('Composition touched engine ' + name)
    engine = NeverConnect()
    caller = compose_private_manual(engine, AuthConfig('fixture-issuer', 'fixture-audience', b'x' * 32), None)
    assert isinstance(caller, FounderDecisionService) and caller.engine is engine
    assert caller.guard.component_id == 'founder-manual-v1'


@pytest.mark.parametrize('operation', ['accept', 'recover'])
def test_PMP05_offline_unknown_entry_never_retries_or_records_denial(monkeypatch, operation):
    from returnops_domain import manual_decision
    calls = []
    class UnknownUow:
        def __init__(self, *args, **kwargs):
            calls.append('construct')
        def __enter__(self):
            calls.append('enter')
            raise AcceptanceOutcomeUnknown()
        def __exit__(self, *args):
            raise AssertionError('Unentered UoW cannot exit')
    def no_denial(*args, **kwargs):
        raise AssertionError('UNKNOWN must not record a denial')
    monkeypatch.setattr(manual_decision, 'record_denial', no_denial)
    caller = FounderDecisionService(object(), object(), uow_factory=UnknownUow, recovery_uow=UnknownUow)
    result = (caller.accept('case_fixture', REQUEST, 'original-key', 'corr_fixture') if operation == 'accept'
        else caller.recover('case_fixture', REQUEST, 'original-key'))
    assert asdict(result) == dict(status='UNKNOWN', receipt=None, safe_code=None, audit='NOT_ATTEMPTED')
    assert calls == ['construct', 'enter']
