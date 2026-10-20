"""Pure synthetic integrity checks; no lifecycle or business acceptance is implied."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta

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
