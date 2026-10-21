"""Independent durable CORE_MOCK notification effects (A2.06 / AH-10 / UC-04).

FR-009..012, NFR-004/008: T2 commits only its own fact. It never changes a
Domain notification, sends externally, or invokes return, label or rendering
work. An absent reply is UNKNOWN; only a committed explicit no-effect fact
can support a later guarded failure/retry decision.
"""
from copy import deepcopy
from datetime import datetime
import re

from sqlalchemy import exists, func, literal, select, update, or_
from sqlalchemy.dialects.postgresql import insert

from . import customer_tables as old, lifecycle_tables as life
from .audit import timestamp
from .canonical import decode_document, digest, encode_document
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError
from .lifecycle_state import reject
from .notification_profile import CHANNEL, COMPONENT, PROFILES
from .notification_tables import controls, facts


_FACT_DOMAIN = 'core-mock-notification-fact/v1'
_RESERVATION_DOMAIN = 'notification-reservation/v2'
_MAX_VERSION = 9007199254740991
_IDENTITY_FIELDS = (
    'notification_work_id', 'notification_id', 'case_id', 'store_id',
    'owner_id', 'logical_key', 'outcome', 'profile', 'channel', 'profile_hash',
    'payload_hash', 'intent_hash',
)
_RESERVATION_KEYS = {
    'profile', 'notification_work_id', 'notification_id', 'case_id', 'store_id',
    'owner_id', 'reservation_id', 'logical_key', 'outcome', 'message_profile',
    'channel', 'profile_hash', 'payload_hash', 'intent_hash', 'attempt_count',
    'claim_id', 'epoch', 'case_version', 'authority_revision', 'reserved_at',
    'deadline',
}
_CURRENT_RESERVATION_FIELDS = {
    'claim_id': 'reservation_claim_id',
    'epoch': 'reservation_epoch',
    'case_version': 'reservation_case_version',
    'authority_revision': 'reservation_authority_revision',
}


def _raw_core(value):
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise ValueError('Invalid reservation encoding')
    return bytes(value)


def _timestamp(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('An aware database timestamp is required')
    return timestamp(value)


def _parsed_time(value):
    if type(value) is not str or not value.endswith('Z'):
        raise ValueError('Invalid reservation timestamp')
    parsed = datetime.fromisoformat(value)
    if _timestamp(parsed) != value:
        raise ValueError('Noncanonical reservation timestamp')
    return parsed


def _positive(value):
    return type(value) is int and 1 <= value <= _MAX_VERSION


def _fact_id(reservation_id):
    return 'n_fact_' + digest({'reservation_id': reservation_id},
                              'core-mock-notification-id/v1')


def fact_payload(fact):
    """Bind every persisted fact field except its own digest, including bytes."""
    payload = {str(name): fact[name] for name in facts.columns.keys()
               if name != 'fact_hash'}
    payload['reservation_core'] = _raw_core(payload['reservation_core']).hex()
    payload['accepted_at'] = _timestamp(payload['accepted_at'])
    return payload


def verify_fact(uow, control, fact):
    """Check integrity/binding; callers still prove T1/T3 lifecycle provenance.

    A prior no-effect fact keeps its original reservation after an authorised
    retry. The current attempt must additionally match the current reservation
    byte for byte. This function neither grants sending authority nor accepts
    a Domain notification.
    """
    valid = False
    try:
        if fact is None or set(fact) != set(facts.columns.keys()):
            raise ValueError('Invalid fact fields')
        core_bytes = _raw_core(fact['reservation_core'])
        reservation = decode_document(core_bytes)
        if (type(reservation) is not dict or set(reservation) != _RESERVATION_KEYS
                or encode_document(reservation) != core_bytes
                or reservation['profile'] != _RESERVATION_DOMAIN):
            raise ValueError('Invalid reservation snapshot')
        for name in _IDENTITY_FIELDS:
            source_name = 'message_profile' if name == 'profile' else name
            if fact[name] != control[name] or reservation[source_name] != fact[name]:
                raise ValueError('Conflicting notification identity')
        if (fact['channel'] != CHANNEL or fact['profile'] != PROFILES.get(fact['outcome'])
                or fact['reservation_id'] != reservation['reservation_id']
                or fact['attempt_count'] != reservation['attempt_count']
                or not _positive(fact['attempt_count'])
                or not _positive(reservation['attempt_count'])
                or not _positive(control['attempt_count'])
                or fact['attempt_count'] > control['attempt_count']
                or any(not _positive(reservation[name]) for name in
                       ('epoch', 'case_version', 'authority_revision'))
                or fact['reservation_hash'] != digest(reservation, _RESERVATION_DOMAIN)
                or fact['fact_id'] != _fact_id(fact['reservation_id'])):
            raise ValueError('Conflicting reservation identity')
        for name in facts.columns.keys():
            value = fact[name]
            if name.endswith('_id') and not (name == 'success_work_id' and value is None):
                if type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{2,79}', value) is None:
                    raise ValueError('Invalid fact identifier')
            if name.endswith('_hash'):
                if type(value) is not str or re.fullmatch(r'[0-9a-f]{64}', value) is None:
                    raise ValueError('Invalid fact digest')
        if (type(reservation['claim_id']) is not str
                or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{2,79}', reservation['claim_id']) is None
                or type(fact['logical_key']) is not str
                or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{7,127}', fact['logical_key']) is None):
            raise ValueError('Invalid reservation claim or key')
        reserved_at = _parsed_time(reservation['reserved_at'])
        deadline = _parsed_time(reservation['deadline'])
        _timestamp(fact['accepted_at'])
        if not reserved_at <= fact['accepted_at'] < deadline:
            raise ValueError('Fact outside its original sending interval')
        if fact['status'] == 'SENT':
            if fact['success_work_id'] != fact['notification_work_id']:
                raise ValueError('Invalid success identity')
        elif fact['status'] != 'NO_EFFECT_FAILED' or fact['success_work_id'] is not None:
            raise ValueError('Invalid no-effect status')
        if fact['attempt_count'] == control['attempt_count']:
            if (core_bytes != _raw_core(control['reservation_core'])
                    or fact['reservation_id'] != control['reservation_id']
                    or fact['reservation_hash'] != control['reservation_hash']
                    or any(reservation[key] != control[column]
                           for key, column in _CURRENT_RESERVATION_FIELDS.items())
                    or reservation['reserved_at'] != _timestamp(control['reservation_at'])
                    or reservation['deadline'] != _timestamp(control['reservation_deadline'])):
                raise ValueError('Conflicting current reservation')
        elif fact['status'] != 'NO_EFFECT_FAILED':
            # A successful send can never be followed by another send attempt.
            raise ValueError('Success followed by another attempt')
        valid = fact['fact_hash'] == digest(fact_payload(fact), _FACT_DOMAIN)
    except (FlowError, KeyError, TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        reject(uow)


class CoreMockNotification:
    """Private fixed provider; each call owns and closes its fenced transaction."""

    def __init__(self, engine, *, uow_factory=CustomerUnitOfWork):
        self.engine, self.uow_factory = engine, uow_factory

    def _outcome(self):
        """Only a trusted test subclass may inject an explicit no-effect result."""
        return 'SENT'

    @staticmethod
    def _validate(uow, reservation_id, *, sending):
        # Kept local because Domain guards also consume verify_fact.
        from .notification_sources import validate_reservation
        context = validate_reservation(uow, reservation_id, sending=sending)
        control, reservation = context['control'], context['reservation']
        if (control['reservation_id'] != reservation_id
                or reservation['reservation_id'] != reservation_id
                or encode_document(reservation) != _raw_core(control['reservation_core'])
                or digest(reservation, _RESERVATION_DOMAIN) != control['reservation_hash']):
            reject(uow)
        return context

    @staticmethod
    def _aliases(control):
        return or_(facts.c.notification_work_id==control['notification_work_id'],
                   facts.c.notification_id==control['notification_id'],
                   facts.c.logical_key==control['logical_key'],
                   facts.c.intent_hash==control['intent_hash'],
                   facts.c.reservation_id==control['reservation_id'])

    @staticmethod
    def _read(uow, control, reservation_id):
        linked = [dict(row) for row in uow.execute(select(facts).where(
            CoreMockNotification._aliases(control))).mappings()]
        for row in linked:
            verify_fact(uow,control,row)
        active = [row for row in linked if row['reservation_id']==reservation_id]
        if len(active)>1:
            reject(uow)
        found = active[0] if active else None
        successes = [row for row in linked if row['status']=='SENT']
        if len(successes) > 1 or any(
                item['reservation_id'] != reservation_id for item in successes):
            reject(uow)
        if found is None:
            if successes:
                reject(uow)
            return None
        fact = dict(found)
        verify_fact(uow, control, fact)
        if (fact['reservation_id'] != control['reservation_id']
                or fact['attempt_count'] != control['attempt_count']
                or _raw_core(fact['reservation_core']) != _raw_core(control['reservation_core'])):
            reject(uow)
        return fact

    def _insert(self, uow, control):
        outcome = self._outcome()
        if outcome not in ('SENT', 'NO_EFFECT_FAILED'):
            reject(uow)
        values = {name: control[name] for name in _IDENTITY_FIELDS}
        values.update(
            fact_id=_fact_id(control['reservation_id']),
            reservation_id=control['reservation_id'],
            reservation_hash=control['reservation_hash'],
            reservation_core=_raw_core(control['reservation_core']),
            attempt_count=control['attempt_count'], status=outcome,
            success_work_id=control['notification_work_id'] if outcome == 'SENT' else None,
            fact_hash='0' * 64,
        )
        # One DB wall-clock sample is the simulated effect's acceptance time.
        # Supported registry/domain writers share this UoW's exclusive fence.
        wall = select(func.clock_timestamp().label('now')).cte(
            'notification_effect_time').prefix_with('MATERIALIZED')
        unchanged_control = exists(select(controls.c.notification_work_id).where(
            controls.c.state == 'RESERVED', controls.c.available.is_(True),
            *(controls.c[name].is_(None) if value is None else controls.c[name] == value
              for name, value in control.items())))
        original_work = exists(select(life.work.c.work_id).where(
            life.work.c.work_id == control['notification_work_id'],
            life.work.c.case_id == control['case_id'],
            life.work.c.store_id == control['store_id'],
            life.work.c.owner_id == control['owner_id'],
            life.work.c.component_id == COMPONENT,
            life.work.c.purpose == 'NOTIFICATION',
            life.work.c.state == 'PENDING',
            life.work.c.claim_id == control['reservation_claim_id'],
            life.work.c.epoch == control['reservation_epoch'],
            life.work.c.claimed_case_version == control['reservation_case_version'],
            life.work.c.authority_revision == control['reservation_authority_revision'],
            life.work.c.input_version == control['input_version'],
            life.work.c.generation == control['generation'],
            life.work.c.idempotency_key == control['logical_key'],
            life.work.c.lease_expires_at.is_(None),
        ))
        current_head = exists(select(old.case_heads.c.case_id).where(
            old.case_heads.c.case_id == control['case_id'],
            old.case_heads.c.store_id == control['store_id'],
            old.case_heads.c.owner_principal_id == control['owner_id'],
            old.case_heads.c.input_version == control['input_version'],
            old.case_heads.c.case_version == control['reservation_case_version'] + 1,
            old.case_heads.c.available.is_(True),
        ))
        current_owner = exists(select(old.principals.c.principal_id).where(
            old.principals.c.principal_id == control['owner_id'],
            old.principals.c.store_id == control['store_id'],
            old.principals.c.role == 'CUSTOMER', old.principals.c.enabled.is_(True),
        ))
        current_authority = exists(select(life.authorities.c.component_id).where(
            life.authorities.c.component_id == COMPONENT,
            life.authorities.c.store_id == control['store_id'],
            life.authorities.c.purpose == 'NOTIFICATION',
            life.authorities.c.revision == control['reservation_authority_revision'],
            life.authorities.c.enabled.is_(True),
        ))
        no_success = ~exists(select(facts.c.fact_id).where(
            self._aliases(control),
            facts.c.status == 'SENT'))
        no_conflicting_alias = ~exists(select(facts.c.fact_id).where(
            self._aliases(control),or_(*(facts.c[name]!=control[name] for name in _IDENTITY_FIELDS))))
        names = list(values) + ['accepted_at']
        selection = select(
            *(literal(value, type_=facts.c[name].type) for name, value in values.items()),
            wall.c.now,
        ).select_from(wall).where(
            wall.c.now >= control['reservation_at'],
            wall.c.now < control['reservation_deadline'],
            unchanged_control, original_work, current_head, current_owner,
            current_authority, no_success, no_conflicting_alias,
        )
        found = uow.execute(insert(facts).from_select(names, selection)
                            .on_conflict_do_nothing().returning(facts)).mappings().one_or_none()
        if found is None:
            return None
        fact = dict(found)
        fact['fact_hash'] = digest(fact_payload(fact), _FACT_DOMAIN)
        if uow.execute(update(facts).where(
                facts.c.fact_id == fact['fact_id'],
                facts.c.reservation_id == control['reservation_id'],
                facts.c.fact_hash == '0' * 64,
        ).values(fact_hash=fact['fact_hash'])).rowcount != 1:
            reject(uow)
        verify_fact(uow, control, fact)
        return fact

    def deliver(self, reservation_id):
        """Send only from a confirmed T1; failures/uncertainty return UNKNOWN."""
        try:
            with self.uow_factory(self.engine, write=True) as uow:
                context = deepcopy(self._validate(uow, reservation_id, sending=True))
                control = context['control']
                fact = self._read(uow, control, reservation_id)
                if fact is None:
                    fact = self._insert(uow, control)
                    if fact is None:
                        fact = self._read(uow, control, reservation_id)

                def final_check():
                    fresh = self._validate(uow, reservation_id, sending=True)
                    if fresh != context or self._read(uow, fresh['control'], reservation_id) != fact:
                        reject(uow)

                uow.before_commit(final_check)
                uow.commit()
            # Return only after BOTH commit and connection close acknowledge.
            return fact
        except Exception:
            # This includes lost commit/close/transport acknowledgements. It is
            # never evidence that the durable sending effect did not occur.
            return None

    def query(self, reservation_id):
        """Observe the original durable fact; never reserve, insert or resend."""
        try:
            with self.uow_factory(self.engine, write=False) as uow:
                context = deepcopy(self._validate(uow, reservation_id, sending=False))
                fact = self._read(uow, context['control'], reservation_id)
                # A read-only UoW holds the shared fence and has no commit-hook
                # registration. Recheck under that same fence before closing.
                fresh = self._validate(uow, reservation_id, sending=False)
                if fresh != context or self._read(uow, fresh['control'], reservation_id) != fact:
                    reject(uow)
                uow.commit()
            return fact
        except Exception:
            return None
