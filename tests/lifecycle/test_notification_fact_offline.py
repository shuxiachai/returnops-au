"""Pure fact/source integrity checks; no lifecycle or business acceptance is implied."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from returnops_domain.canonical import digest, encode_document
from returnops_domain.errors import FlowError
from returnops_domain.notification_mock import fact_payload, verify_fact
from returnops_domain.notification_profile import CHANNEL, PROFILES

FACT_DOMAIN = 'core-mock-notification-fact/v1'
RES_DOMAIN = 'notification-reservation/v2'
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


class NoDatabase:
    def __init__(self):
        self.poisoned = False

    def poison(self):
        self.poisoned = True

    def execute(self, *args, **kwargs):
        raise AssertionError('database access')

    @property
    def connection(self):
        raise AssertionError('connection access')


def sample(status='SENT'):
    identity = dict(notification_work_id='work_001', notification_id='notification_001',
                    case_id='case_001', store_id='store_001', owner_id='owner_001',
                    logical_key='logical_key_001', outcome='REJECTED',
                    profile=PROFILES['REJECTED'], channel=CHANNEL,
                    profile_hash='a' * 64, payload_hash='b' * 64, intent_hash='c' * 64)
    reservation = {**identity, 'message_profile': identity['profile'], 'profile': RES_DOMAIN,
                   'reservation_id': 'reservation_001', 'attempt_count': 1,
                   'claim_id': 'claim_001', 'epoch': 1, 'case_version': 2,
                   'authority_revision': 3, 'reserved_at': '2026-01-01T00:00:00.000000Z',
                   'deadline': '2026-01-01T00:01:00.000000Z'}
    core = encode_document(reservation)
    rh = digest(reservation, RES_DOMAIN)
    control = {**identity, 'attempt_count': 1, 'reservation_id': reservation['reservation_id'],
               'reservation_core': core, 'reservation_hash': rh,
               'reservation_claim_id': 'claim_001', 'reservation_epoch': 1,
               'reservation_case_version': 2, 'reservation_authority_revision': 3,
               'reservation_at': START, 'reservation_deadline': START + timedelta(minutes=1)}
    fact = {**identity, 'fact_id': 'n_fact_' + digest({'reservation_id': reservation['reservation_id']}, 'core-mock-notification-id/v1'),
            'reservation_id': reservation['reservation_id'], 'reservation_hash': rh,
            'reservation_core': core, 'attempt_count': 1, 'status': status,
            'success_work_id': identity['notification_work_id'] if status == 'SENT' else None,
            'accepted_at': START + timedelta(seconds=1), 'fact_hash': '0' * 64}
    seal(fact)
    return control, fact, reservation


def seal(fact):
    fact['fact_hash'] = digest(fact_payload(fact), FACT_DOMAIN)


def update_core(control, fact, reservation):
    fact['reservation_core'] = encode_document(reservation)
    fact['reservation_hash'] = digest(reservation, RES_DOMAIN)
    control['reservation_core'] = fact['reservation_core']
    control['reservation_hash'] = fact['reservation_hash']
    seal(fact)


def denied(control, fact):
    uow = NoDatabase()
    with pytest.raises(FlowError) as exc:
        verify_fact(uow, control, fact)
    assert exc.value.code == 'INVALID_STATE'
    assert uow.poisoned


@pytest.mark.parametrize('status', ['SENT', 'NO_EFFECT_FAILED'])
def test_valid_fact_is_pure(status):
    control, fact, _ = sample(status)
    uow = NoDatabase()
    assert verify_fact(uow, control, fact) is None
    assert not uow.poisoned
    payload = fact_payload(fact)
    assert payload['reservation_core'] == fact['reservation_core'].hex()
    assert payload['accepted_at'] == '2026-01-01T00:00:01.000000Z'
    assert 'fact_hash' not in payload


@pytest.mark.parametrize('field', ['case_id', 'store_id', 'owner_id', 'logical_key', 'payload_hash', 'profile'])
def test_resealed_identity_mismatch_is_denied(field):
    control, fact, _ = sample()
    fact[field] = 'different_001' if not field.endswith('_hash') else 'd' * 64
    seal(fact)
    denied(control, fact)


@pytest.mark.parametrize('change', ['missing', 'extra', 'bad_id', 'bad_hash', 'unknown_status', 'wrong_success', 'hash', 'bytes'])
def test_fact_corruption_is_denied(change):
    control, fact, _ = sample()
    if change == 'missing': del fact['case_id']
    elif change == 'extra': fact['extra'] = 'unexpected'
    elif change == 'bad_id': fact['fact_id'] = 7
    elif change == 'bad_hash': fact['fact_hash'] = 'A' * 64
    elif change == 'unknown_status': fact['status'] = 'UNKNOWN'; seal(fact)
    elif change == 'wrong_success': fact['success_work_id'] = None; seal(fact)
    elif change == 'hash': fact['fact_hash'] = '0' * 64
    else: fact['reservation_core'] += b'\x00'
    denied(control, fact)


@pytest.mark.parametrize('change', ['extra', 'missing', 'profile', 'claim', 'epoch_bool', 'noncanonical_time', 'trailing_bytes'])
def test_reservation_snapshot_is_closed(change):
    control, fact, reservation = sample()
    if change == 'extra': reservation['extra'] = 1
    elif change == 'missing': del reservation['claim_id']
    elif change == 'profile': reservation['profile'] = 'other'
    elif change == 'claim': reservation['claim_id'] = 'x'
    elif change == 'epoch_bool': reservation['epoch'] = True
    elif change == 'noncanonical_time': reservation['reserved_at'] = '2026-01-01T00:00:00Z'
    if change == 'trailing_bytes':
        fact['reservation_core'] += b'\x00'; control['reservation_core'] = fact['reservation_core']; seal(fact)
    else: update_core(control, fact, reservation)
    denied(control, fact)


@pytest.mark.parametrize('value', [True, 0, -1, 2])
def test_invalid_or_future_attempt(value):
    control, fact, reservation = sample()
    fact['attempt_count'] = reservation['attempt_count'] = value
    update_core(control, fact, reservation)
    denied(control, fact)


@pytest.mark.parametrize('value', [START - timedelta(microseconds=1), START + timedelta(minutes=1), START.replace(tzinfo=None)])
def test_acceptance_time_must_be_aware_and_within_interval(value):
    control, fact, _ = sample()
    fact['accepted_at'] = value
    if value.tzinfo is not None: seal(fact)
    denied(control, fact)


@pytest.mark.parametrize('field,value', [('reservation_claim_id', 'claim_other'), ('reservation_epoch', 2), ('reservation_case_version', 4), ('reservation_authority_revision', 4), ('reservation_id', 'reservation_other'), ('reservation_at', START + timedelta(seconds=1))])
def test_current_reservation_mismatch(field, value):
    control, fact, _ = sample()
    control[field] = value
    denied(control, fact)


def test_only_prior_no_effect_fact_can_survive_retry_with_same_identity():
    control, fact, _ = sample('NO_EFFECT_FAILED')
    control['attempt_count'] = 2
    control['reservation_id'] = 'reservation_002'
    control['reservation_core'] = b'new reservation'
    uow = NoDatabase()
    assert verify_fact(uow, control, fact) is None
    assert not uow.poisoned
    changed = deepcopy(control)
    changed['owner_id'] = 'other_owner'
    denied(changed, fact)
    fact['status'] = 'SENT'
    fact['success_work_id'] = fact['notification_work_id']
    seal(fact)
    denied(control, fact)


def proposal_body():
    """Use the real frozen DTO shape and its existing finite decode contract."""
    from returnops_domain import founder_codec as finite
    examples = json.loads((Path(__file__).resolve().parents[2] / 'contracts/v1/examples.json').read_text())
    value = deepcopy(next(item['value']['content'] for item in examples['positive']
                          if item['name'] == 'history-proposal'))
    finite.validate('HistoricalProposalBundle', value)
    return finite.decode_document(finite.encode_document(value))


def source_inventory(monkeypatch, body, *, record_patch=None, origin_hash='b' * 64):
    """Isolate inventory hashing only; this stub does not claim source authority."""
    from returnops_domain import notification_intent as intent
    record = dict(record_id='proposal_record', case_id='case_001', kind='PROPOSAL',
                  object_id='proposal_001', object_version=1, case_version=10,
                  recorded_sequence=3, recorded_at=START, content_sha256='a' * 64,
                  retention_state='AVAILABLE', removal_reason=None)
    record.update(record_patch or {})
    later = {**record, 'record_id': 'later_record', 'recorded_sequence': 4}
    seen = []
    def read(record_id, kinds, *, current_actor):
        assert record_id == record['record_id'] and kinds == {'PROPOSAL'} and current_actor is False
        seen.append(record_id)
        return record, body
    proof = SimpleNamespace(revisions={record['record_id']: record, 'later_record': later},
                            origin=lambda row: {'event_hash': origin_hash})
    monkeypatch.setattr(intent, 'Sources', lambda *args: SimpleNamespace(proof=proof, read=read))
    def initial(uow, table, **where):
        assert table is intent.old.history and where == {'record_id': 'notification_initial'}
        return {'recorded_sequence': 3}
    monkeypatch.setattr(intent, 'one', initial)
    result = intent._inventory(NoDatabase(), {'case_id': 'case_001'}, 'notification_initial')
    assert seen == ['proposal_record'] and len(result) == 1
    return result


def test_inventory_accepts_real_finite_proposal_and_keeps_complete_record_origin(monkeypatch):
    from returnops_domain import founder_codec as finite
    body = proposal_body()
    original = deepcopy(body)
    assert body['packet']['confidence'] == 0.8 and type(body['packet']['confidence']) is float
    with pytest.raises(FlowError) as strict:
        digest(body, 'notification-source-body/v2')
    assert strict.value.code == 'VALIDATION_ERROR'
    inventory = source_inventory(monkeypatch, body)
    assert inventory == [{
        'record': dict(record_id='proposal_record', case_id='case_001', kind='PROPOSAL',
                       object_id='proposal_001', object_version=1, case_version=10,
                       recorded_sequence=3, recorded_at='2026-01-01T00:00:00.000000Z',
                       content_sha256='a' * 64, retention_state='AVAILABLE', removal_reason=None),
        'content_hash': digest(dict(profile=finite.PROFILE, history_domain=finite.HISTORY_DOMAIN,
                                    content_hash=finite.digest(body)), 'notification-source-body/finite-v2'),
        'origin_hash': 'b' * 64,
    }]
    assert body == original
    # The outer manifest remains accepted by the unchanged strict codec.
    assert len(digest({'records': inventory}, 'notification-source/v2')) == 64
    with pytest.raises(FlowError):
        encode_document(body)


@pytest.mark.parametrize('mutation', ['confidence_bit', 'original_text', 'rationale'])
def test_inventory_binds_every_finite_body_field_without_rewriting_sources(monkeypatch, mutation):
    body = proposal_body()
    before = source_inventory(monkeypatch, body)
    changed = deepcopy(body)
    if mutation == 'confidence_bit':
        changed['packet']['confidence'] = math.nextafter(body['packet']['confidence'], 1.0)
    elif mutation == 'original_text':
        changed['statements'][0]['raw_text'] += ' exact additional source text'
    else:
        changed['packet']['rationale'] += ' exact additional rationale'
    after = source_inventory(monkeypatch, changed)
    assert after[0]['content_hash'] != before[0]['content_hash']
    assert after[0]['record'] == before[0]['record'] and after[0]['origin_hash'] == before[0]['origin_hash']


def test_inventory_keeps_metadata_and_audit_bindings_in_outer_manifest(monkeypatch):
    body = proposal_body()
    original = source_inventory(monkeypatch, body)
    changed = source_inventory(monkeypatch, body, record_patch={'case_version': 11}, origin_hash='c' * 64)
    assert changed[0]['content_hash'] == original[0]['content_hash']
    assert changed[0]['record']['case_version'] == 11 and changed[0]['origin_hash'] == 'c' * 64
    assert digest({'records': changed}, 'notification-source/v2') != digest(
        {'records': original}, 'notification-source/v2')


def test_inventory_preserves_old_strict_fingerprint_and_existing_finite_numeric_rules(monkeypatch):
    from returnops_domain import founder_codec as finite, notification_intent as intent
    body = proposal_body()
    body['packet']['confidence'] = 1
    assert intent._body_hash(body) == digest(body, 'notification-source-body/v2')
    inventory = source_inventory(monkeypatch, body)
    assert inventory[0]['content_hash'] == digest(body, 'notification-source-body/v2')
    projected = finite.decode_document(finite.encode_document({'integer': 1.0, 'zero': -0.0}))
    assert projected == {'integer': 1, 'zero': 0} and all(type(value) is int for value in projected.values())
    assert intent._body_hash(projected) == digest(projected, 'notification-source-body/v2')
    # In a finite body, integral floats follow the existing normalization;
    # booleans remain distinct from integers.
    assert intent._body_hash({'fraction': 0.8, 'value': 1.0}) == intent._body_hash({'fraction': 0.8, 'value': 1})
    assert intent._body_hash({'fraction': 0.8, 'value': True}) != intent._body_hash({'fraction': 0.8, 'value': 1})


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), float('-inf'), Decimal('0.8'),
                               object(), b'not-a-DTO', {1: 'non-string-key'}],
                         ids=['nan', 'inf', 'negative-inf', 'decimal', 'object', 'bytes', 'key'])
def test_inventory_numeric_fallback_still_rejects_unsupported_values(monkeypatch, bad):
    body = proposal_body()
    body['packet']['confidence'] = bad
    with pytest.raises(FlowError):
        source_inventory(monkeypatch, body)


def test_inventory_fallback_does_not_remove_depth_limit():
    from returnops_domain.notification_intent import _body_hash
    body = 0.8
    for _ in range(66):
        body = [body]
    with pytest.raises(FlowError):
        _body_hash(body)


def test_inventory_does_not_fallback_after_non_validation_failure(monkeypatch):
    from returnops_domain import notification_intent as intent
    original = FlowError('INTERNAL_ERROR')
    calls = []
    def failure(*args):
        calls.append(True)
        raise original
    monkeypatch.setattr(intent, 'digest', failure)
    with pytest.raises(FlowError) as caught:
        intent._body_hash({'confidence': 0.8})
    assert caught.value is original and calls == [True]
