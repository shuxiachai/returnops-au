"""Actual writer and bounded customer-origin checks; no engine or DB connection."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from returnops_domain import customer_tables as old
from returnops_domain.audit import timestamp
from returnops_domain.canonical import decode_document, digest
from returnops_domain.errors import FlowError
from returnops_domain.notification_history import append_customer
from returnops_domain import notification_customer_origin as origin
from returnops_domain.notification_profile import COMPONENT, render
from returnops_domain.wire import validate


class Rows:
    def __init__(self, rows):
        self.rows, self.rowcount = rows, len(rows)

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def one_or_none(self):
        assert len(self.rows) <= 1
        return self.first()

    def one(self):
        assert len(self.rows) == 1
        return self.rows[0]


class RecordingUow:
    """Interpret only the actual writer's simple SQLAlchemy statements in memory."""
    def __init__(self, head, accepted):
        self.tables = {old.case_heads.name: [dict(head)], old.history.name: [dict(accepted)],
                       old.history_contents.name: [], old.audit.name: []}
        self.poisoned, self.executed = False, []

    def poison(self):
        self.poisoned = True

    def execute(self, statement):
        self.executed.append(statement)
        table = statement.table if hasattr(statement, 'table') else statement.get_final_froms()[0]
        records = self.tables.setdefault(table.name, [])
        def matches(row):
            return all(row[criterion.left.name] == criterion.right.value
                       for criterion in statement._where_criteria)
        if statement.is_insert:
            records.append(dict(statement.compile().params))
            return Rows([records[-1]])
        if statement.is_update:
            chosen = [row for row in records if matches(row)]
            values = {column if isinstance(column, str) else column.name: parameter.value
                      for column, parameter in statement._values.items()}
            for row in chosen:
                row.update(values)
            return Rows(chosen)
        assert statement.is_select
        chosen = [dict(row) for row in records if matches(row)]
        if statement._limit_clause is not None:
            chosen = chosen[:statement._limit_clause.value]
        return Rows(chosen)


def written():
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    head = dict(case_id='case_001', case_version=8, history_sequence=3,
                audit_sequence=0, audit_head=None, store_id='store_001', owner_principal_id='owner_001')
    accepted = dict(record_id='notification_result_001', case_id=head['case_id'], kind='NOTIFICATION',
                    object_id='notification_001', object_version=3, case_version=7,
                    recorded_sequence=3, recorded_at=at, content_sha256='a' * 64,
                    retention_state='AVAILABLE', removal_reason=None)
    control = dict(notification_work_id='notification_work_001', notification_id='notification_001',
                   case_id=head['case_id'], store_id=head['store_id'], owner_id=head['owner_principal_id'],
                   intent_hash='b' * 64, accepted_record_id=accepted['record_id'],
                   accepted_event_id='notification_event_001', accepted_fact_id='fact_001')
    fact = dict(fact_id='fact_001', status='SENT', fact_hash='c' * 64, accepted_at=at)
    note = dict(notification_id=control['notification_id'], status='SENT', outcome='REJECTED',
                **render('REJECTED'), sent_at=timestamp(at))
    uow = RecordingUow(head, accepted)
    append_customer(uow, head, control, fact, note, at)
    row = next(item for item in uow.tables[old.history.name] if item['kind'] == 'OUTCOME_MESSAGE')
    events = [decode_document(item['body']) for item in uow.tables[old.audit.name]]
    proof = SimpleNamespace(revisions={item['record_id']: item for item in uow.tables[old.history.name]},
                            events=events)
    markers = dict(controls=[control], facts=[fact], events=events)
    return uow, head, control, fact, row, proof, markers


def test_actual_customer_writer_keeps_frozen_audit_and_customer_contracts():
    uow, head, control, fact, row, proof, markers = written()
    validate('AuditEvent', proof.events[0], internal=True)
    validate('AuditPage', {'items': proof.events}, internal=True)
    assert proof.events[0]['history_refs'] == [origin.history_ref(proof.revisions[control['accepted_record_id']])]
    assert proof.events[0]['history_refs'][0]['kind'] == 'NOTIFICATION'
    assert row['kind'] == 'OUTCOME_MESSAGE'
    assert proof.events[0]['payload_hash'] == digest(origin.customer_payload(control, fact, row), 'audit-payload/v1')
    assert origin.verify_customer_origin(uow, head, row, control, fact, proof, markers)['record_id'] == control['accepted_record_id']
    invalid = deepcopy(proof.events[0])
    invalid['history_refs'] = [origin.history_ref(row)]
    with pytest.raises(FlowError):
        validate('AuditEvent', invalid, internal=True)


@pytest.mark.parametrize('field', origin.METADATA)
def test_every_immutable_customer_metadata_field_is_bound(field):
    uow, head, control, fact, row, proof, markers = written()
    row[field] = (row[field] + timedelta(seconds=1) if field == 'recorded_at'
                  else row[field] + 1 if type(row[field]) is int else 'different_001')
    with pytest.raises(FlowError):
        origin.verify_customer_origin(uow, head, row, control, fact, proof, markers)
    assert uow.poisoned


@pytest.mark.parametrize('field', ['event_type', 'case_id', 'case_version', 'occurred_at',
                                  'correlation_id', 'actor', 'object_ids', 'history_refs', 'payload_hash'])
def test_customer_origin_mutations_and_duplicate_origin_fail(field):
    uow, head, control, fact, row, proof, markers = written()
    event = proof.events[0]
    event[field] = (9 if field == 'case_version' else {} if field == 'actor'
                    else [] if field in {'object_ids', 'history_refs'} else 'different_001')
    with pytest.raises(FlowError):
        origin.verify_customer_origin(uow, head, row, control, fact, proof, markers)
    assert uow.poisoned


def test_duplicate_customer_origin_is_not_filtered_by_payload_hash():
    uow, head, control, fact, row, proof, markers = written()
    duplicate = deepcopy(proof.events[0])
    duplicate['payload_hash'] = 'd' * 64
    markers['events'].append(duplicate)
    with pytest.raises(FlowError):
        origin.verify_customer_origin(uow, head, row, control, fact, proof, markers)


@pytest.mark.parametrize('family', ['control', 'fact', 'audit'])
def test_identity_alias_is_discovered_even_when_case_disagrees(family):
    _, _, control, fact, row, proof, _ = written()
    all_controls, all_facts, events = [], [], []
    if family == 'control':
        all_controls = [{**control, 'case_id': 'foreign_case'}]
    elif family == 'fact':
        all_facts = [dict(notification_id=row['object_id'], notification_work_id='work_foreign',
                          case_id='foreign_case', fact_id='fact_foreign')]
    else:
        events = [{**proof.events[0], 'case_id': 'foreign_case'}]
    found = origin.related_markers(row, all_controls, all_facts, events)
    assert any(found.values())
    assert (found['controls'] if family == 'control' else found['facts'] if family == 'fact'
            else found['events'])[0]['case_id'] == 'foreign_case'


def test_wrong_type_customer_event_remains_an_alias_marker():
    _, _, _, _, row, proof, _ = written()
    event = {**proof.events[0], 'event_type': 'OTHER_CUSTOMER_EVENT', 'case_id': 'foreign_case'}
    assert origin.related_markers(row, [], [], [event])['events'] == [event]


def test_legacy_marker_search_is_empty_only_with_no_modern_evidence():
    _, _, _, _, row, _, _ = written()
    row = {**row, 'record_id': 'old_customer_message'}
    assert not any(origin.related_markers(row, [], [], []).values())


def test_row_discovery_rejects_overflow_without_truncating():
    _, _, _, _, _, _, _ = written()
    fake = SimpleNamespace(execute=lambda statement: Rows([{}, {}, {}]), poison=lambda: None)
    with pytest.raises(FlowError):
        origin._bounded(fake, old.audit, 2)


@pytest.mark.parametrize('bound', ['AUDIT_BODY_LIMIT', 'AUDIT_BYTES_LIMIT'])
def test_opaque_audit_byte_overflow_fails_closed(monkeypatch, bound):
    uow, *_ = written()
    monkeypatch.setattr(origin, bound, 1)
    with pytest.raises(FlowError):
        origin.audit_markers(uow)
    assert uow.poisoned


def test_actual_writer_rejects_a_wrong_accepted_notification_kind():
    uow, head, control, fact, row, proof, markers = written()
    # A fresh recording transaction has no pre-existing customer projection.
    accepted = dict(proof.revisions[control['accepted_record_id']], kind='OUTCOME_MESSAGE')
    fresh = RecordingUow(head, accepted)
    note = dict(notification_id=control['notification_id'], status='SENT', outcome='REJECTED',
                **render('REJECTED'), sent_at=timestamp(row['recorded_at']))
    with pytest.raises(FlowError):
        append_customer(fresh, head, control, fact, note, row['recorded_at'])
    assert fresh.poisoned and fresh.tables[old.audit.name] == []


@pytest.mark.parametrize('family',['facts','events'])
def test_empty_current_projection_cannot_hide_independent_modern_markers(monkeypatch,family):
    from returnops_domain.notification_projection import current_messages
    uow,head,control,fact,row,proof,markers=written()
    found=dict(controls=[],facts=[],events=[])
    found[family]=[fact if family=='facts' else proof.events[0]]
    monkeypatch.setattr(origin,'current_case_markers',lambda uow,head:found)
    with pytest.raises(FlowError):
        current_messages(uow,head,[])
    assert uow.poisoned


@pytest.mark.parametrize('revision,reserved,expected',[
    (None,False,'deny'),
    ('0013_label_artifact_result',False,False),
    ('0013_label_artifact_result',True,'deny'),
    ('0014_notification_delivery',False,False),
    ('0014_notification_delivery',True,True),
])
def test_legacy_discriminator_requires_known_schema_and_no_reserved_identity(
        monkeypatch,revision,reserved,expected):
    uow,_,_,_,row,_,_=written()
    uow.connection=object()  # Argument marker only; no real connection exists.
    row={**row,'record_id':row['record_id'] if reserved else 'old_message_001'}
    monkeypatch.setattr(origin,'version',lambda connection:revision)
    monkeypatch.setattr(origin,'_bounded',lambda uow,table,limit:[])
    monkeypatch.setattr(origin,'audit_markers',lambda uow:[])
    if expected=='deny':
        with pytest.raises(FlowError):
            origin.message_markers(uow,row)
        assert uow.poisoned
    else:
        modern,markers=origin.message_markers(uow,row)
        assert modern is expected and not any(markers.values())


def test_case_discovery_finds_orphan_audit_without_any_control_fact_or_message(monkeypatch):
    uow,head,_,_,_,proof,_=written()
    uow.connection=object()
    monkeypatch.setattr(origin,'version',lambda connection:origin.NOTIFICATION)
    monkeypatch.setattr(origin,'_bounded',lambda uow,table,limit:[])
    monkeypatch.setattr(origin,'audit_markers',lambda uow:proof.events)
    found=origin.current_case_markers(uow,head)
    assert found['controls']==[] and found['facts']==[]
    assert found['events']==proof.events
