"""Offline boundaries are separate from real PostgreSQL acceptance evidence."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime,timedelta,timezone
from inspect import signature
from itertools import permutations
from types import SimpleNamespace
import pytest
from sqlalchemy import BigInteger,Boolean,DateTime,String,text
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from returnops_domain import founder_codec as finite
from returnops_domain.canonical import digest
from returnops_domain.errors import AcceptanceOutcomeUnknown,FlowError
from returnops_domain.label_execution import LabelExecutionService,LabelExecutionResult
from returnops_domain.label_execution_sources import identities,stable,control_payload,confirmation_body,ledger_payload,verify_fact,accepted_payload
from returnops_domain.label_execution_tables import controls,permissions,ledger,artifact_work,CONTROL_IDS,CONTROL_HASHES,CONTROL_NUMBERS
from returnops_domain.core_label_mock import Ticket
from returnops_domain import label_execution_schema as label_schema


def reservation():
    now = datetime(2026,10,15,tzinfo=timezone.utc)
    row = {name:name+'_original' for name in CONTROL_IDS}
    row.update({name:'1'*64 for name in CONTROL_HASHES});row.update({name:1 for name in CONTROL_NUMBERS})
    row.update(effect_key='effect_original',dispatch_at=now,dispatch_deadline=now+timedelta(seconds=30))
    return row


def operation():
    return dict(operation_id='operation_original',case_id='case_original',case_version=7,command_id='command_original',
        approval_id='approval_original',proposal_id='proposal_original',proposal_version=1,input_version=2,
        provider_id='provider-mock-label',operation_fingerprint='a'*64,status='EXECUTING',attempt_count=1,
        updated_at='2026-10-15T00:00:00.000000Z',idempotency_key='effect_original')


def test_LE_G2_G8_stable_identity_has_only_original_work_and_fixed_label_slot():
    first = identities('work_original')
    assert first == identities('work_original') and set(first) == {'control_id','operation_id','first_record_id','dispatch_record_id','dispatch_claim_id','effect_key'}
    assert all(v != identities('work_changed')[k] for k,v in first.items())
    from returnops_domain.execution_preparation_sources import identities as returns
    assert not set(first.values()) & set(returns('work_original').values())
    assert list(signature(LabelExecutionService.execute_accepted_label).parameters) == ['self','case_id','expected_case_version','execution_work_id','original_approval_key','correlation_id']
    assert all(len(value) <= 80 for value in first.values())


@pytest.mark.parametrize('field',['bridge_event_id','bridge_target_hash','bridge_receipt_hash','return_result_hash','return_ledger_hash',
    'provider_return_id','command_hash','parcel_id','operation_fingerprint','provider_revision','effect_authority_revision','dispatch_deadline'])
def test_LE_G3_binding_covers_full_original_source_command_and_authority(field):
    row = reservation();original = digest(control_payload(row),'label-reservation/v1')
    row[field] = row[field]+timedelta(seconds=1) if field == 'dispatch_deadline' else 2 if type(row[field]) is int else 'changed'
    assert digest(control_payload(row),'label-reservation/v1') != original


@pytest.mark.parametrize('field,value',[('case_id',''),('execution_work_id','bad id'),('original_approval_key',[]),
    ('correlation_id','x'*81),('expected_case_version',True),('expected_case_version',0),('expected_case_version',1.5),
    ('expected_case_version',9007199254740992)])
def test_LE_G3_invalid_request_never_opens_transaction(field,value):
    calls=[]
    def forbidden(*args,**kwargs):calls.append('transaction');raise AssertionError('Invalid request reached I/O')
    caller=LabelExecutionService(object(),object(),uow_factory=forbidden)
    args=dict(case_id='case_original',execution_work_id='work_original',original_approval_key='original-key',
        correlation_id='correlation_original',expected_case_version=7);args[field]=value
    result=caller.execute_accepted_label(**args)
    assert result.status=='DENIED' and result.safe_code=='VALIDATION_ERROR' and calls==[]


@pytest.mark.parametrize('entry',['execute','reconcile'])
def test_LE_G5_unknown_transaction_never_invokes_mock(entry):
    calls=[]
    class Uncertain:
        def __init__(self,*args,**kwargs):calls.append('construct')
        def __enter__(self):raise AcceptanceOutcomeUnknown()
        def __exit__(self,*args):raise AssertionError('Never entered')
    def mock(*args):raise AssertionError('No confirmed T1 commit and close')
    caller=LabelExecutionService(object(),object(),uow_factory=Uncertain,mock_factory=mock)
    result=caller.execute_accepted_label('case_original',7,'work_original','original-key','correlation_original') if entry=='execute' else caller.reconcile_label('case_original','work_original','original-key','correlation_original')
    assert result==LabelExecutionResult('UNKNOWN') and calls==['construct']


def test_LE_G1_G9_ledger_independent_and_artifact_intent_cannot_be_claimed_or_duplicated():
    assert not ledger.foreign_key_constraints
    assert set(controls.metadata.tables)=={'lifecycle_label_execution_controls','label_provider_permissions','core_mock_label_ledger','lifecycle_label_artifact_work'}
    sql=str(CreateTable(artifact_work).compile(dialect=postgresql.dialect()))
    assert 'FOREIGN KEY(control_id, case_id)' in sql and 'UNIQUE (control_id)' in sql and 'UNIQUE (case_id)' in sql
    assert 'epoch = 0 AND claim_id IS NULL' in sql and 'PENDING' in sql and 'PAUSED' in sql
    assert not {'body','command','parameters','token','original_key','label_evidence_id'} & set(ledger.columns.keys())
    assert all(c.default is None and c.server_default is None for table in controls.metadata.tables.values() for c in table.columns)


@pytest.mark.parametrize('status',['SUCCEEDED','FAILED'])
def test_LE_G2_G9_confirmation_preserves_dispatch_version_and_never_fabricates_artifact(status):
    body=operation();before=deepcopy(body);now=datetime(2026,10,15,0,1,tzinfo=timezone.utc)
    fact=dict(status=status,provider_operation_id='mock_label_original')
    result=confirmation_body(body,fact,now,'correlation_original')
    assert result['case_version']==7 and result['attempt_count']==1 and body==before
    assert result['status']==('EXECUTING' if status=='SUCCEEDED' else 'FAILED')
    assert result['provider_operation_id']=='mock_label_original' and 'result' not in result and 'label_evidence_id' not in repr(result)
    assert ('error' in result)==(status=='FAILED')
    assert finite.validate('OperationAttempt',result)==result


def test_LE_G9_minimal_retained_payload_binds_fact_without_reconstructing_body():
    row=reservation();fact=dict(fact_hash='2'*64,provider_operation_id='mock_label_original',status='SUCCEEDED')
    value=accepted_payload(row,fact)
    assert value['content_available'] is False and not {'body','parameters','provider_label_id','parcel_id','provider_return_id','original_key'} & value.keys()
    assert accepted_payload(row,{**fact,'fact_hash':'3'*64})!=value


def test_LE_G11_result_and_internal_ticket_are_immutable_and_hide_sensitive_repr():
    result=LabelExecutionResult('UNKNOWN');ticket=Ticket('control_original','case_original','secret-original','a'*64,'QUERY','claim_original',1)
    with pytest.raises(FrozenInstanceError):result.status='COMMITTED'
    with pytest.raises(FrozenInstanceError):ticket.epoch=2
    assert 'secret-original' not in repr(ticket)


def test_LE_G1_G2_ledger_payload_uses_plain_keys_and_exact_accepted_time():
    now=datetime(2026,10,15,tzinfo=timezone.utc)
    row={str(name):'value_original' for name in ledger.columns.keys()};row.update(accepted_at=now,fact_hash='a'*64)
    payload=ledger_payload(row)
    assert all(type(k) is str for k in payload) and 'fact_hash' not in payload
    assert payload['accepted_at']=='2026-10-15T00:00:00.000000Z' and row['accepted_at'] is now


def _label_catalog_rows():
    """Synthetic catalog values for batching tests, not actual PostgreSQL evidence."""
    result=[]
    for table in label_schema.metadata.tables.values():
        columns=[]
        for column in table.columns:
            kind=('timestamp with time zone' if isinstance(column.type,DateTime) else
                  'bigint' if isinstance(column.type,BigInteger) else 'boolean' if isinstance(column.type,Boolean)
                  else f'character varying({column.type.length})')
            columns.append(dict(name=column.name,type=kind,notnull=not column.nullable,default=None,
                                identity='',generated='',collation='default' if isinstance(column.type,String) else None))
        constraints=[dict(name=table.name+'_pkey',type='p',definition='PRIMARY KEY ('+
                          ', '.join(c.name for c in table.primary_key)+')')]
        constraints.extend(dict(name=name,type='c',definition=value) for name,value in label_schema.CHECKS[table.name].items())
        keys={table.name+'_pkey':(True,tuple(c.name for c in table.primary_key))}
        for constraint in table.constraints:
            if constraint.__class__.__name__=='UniqueConstraint':
                names=tuple(c.name for c in constraint.columns)
                constraints.append(dict(name=constraint.name,type='u',definition='UNIQUE ('+', '.join(names)+')'))
                keys[constraint.name]=(True,names)
        for constraint in table.foreign_key_constraints:
            elements=list(constraint.elements)
            constraints.append(dict(name=constraint.name,type='f',definition='FOREIGN KEY ('+
                ', '.join(e.parent.name for e in elements)+') REFERENCES '+elements[0].column.table.name+
                '('+', '.join(e.column.name for e in elements)+')'))
        constraints=[{**item,'validated':True,'deferrable':False,'deferred':False} for item in constraints]
        keys.update({index.name:(index.unique,tuple(c.name for c in index.columns)) for index in table.indexes})
        indexes=[dict(name=name,definition=f"CREATE {'UNIQUE ' if unique else ''}INDEX {name} ON descriptor_probe.{table.name} "
                      f"USING btree ({', '.join(names)})",valid=True,ready=True,immediate=True,nulls_not_distinct=False)
                 for name,(unique,names) in keys.items()]
        result.append(dict(table_name=table.name,schema='descriptor_probe',kind='r',persistence='p',rls=False,
                           force_rls=False,options=None,triggers=0,columns=columns,constraints=constraints,indexes=indexes))
    return result


class _LabelCatalogConnection:
    def __init__(self, rows, *, error=None, error_stage='execute'):
        self.rows=rows;self.error=error;self.error_stage=error_stage;self.calls=[]
        self.dialect=postgresql.dialect()

    def execute(self, statement, parameters):
        self.calls.append((str(statement),dict(parameters)))
        if self.error is not None and self.error_stage=='execute':raise self.error
        return self

    def scalars(self):
        if self.error is not None and self.error_stage=='scalars':raise self.error
        return self

    def all(self):
        if self.error is not None and self.error_stage=='all':raise self.error
        return deepcopy(self.rows)


@pytest.mark.parametrize('order',list(permutations(range(4))))
def test_LE_G1_descriptor_batch_accepts_all_row_orders_with_one_fixed_query(order):
    rows=_label_catalog_rows();connection=_LabelCatalogConnection([rows[i] for i in order])
    assert label_schema.descriptor(connection) is True
    assert len(connection.calls)==1
    sql,parameters=connection.calls[0]
    assert parameters==dict(control_name='lifecycle_label_execution_controls',permission_name='label_provider_permissions',
                           ledger_name='core_mock_label_ledger',artifact_work_name='lifecycle_label_artifact_work')
    assert "'table_name', r.relname" in sql and 'n.nspname=current_schema()' in sql
    assert 'r.relname IN (:control_name, :permission_name, :ledger_name, :artifact_work_name)' in sql
    assert all(fragment in sql for fragment in ('t.tgrelid=r.oid','a.attrelid=r.oid','c.conrelid=r.oid','i.indrelid=r.oid',
                                               'ORDER BY a.attnum','ORDER BY c.conname','ORDER BY ix.relname'))


@pytest.mark.parametrize('fault',['missing','duplicate','extra','unknown','null_row','list_row','missing_name','int_name','bool_name','null_name'])
def test_LE_G1_descriptor_batch_rejects_incomplete_ambiguous_or_malformed_rows(fault):
    rows=_label_catalog_rows()
    if fault=='missing':rows.pop()
    elif fault=='duplicate':rows[3]=deepcopy(rows[0])
    elif fault=='extra':rows.append(deepcopy(rows[0]))
    elif fault=='unknown':rows[0]['table_name']='unexpected_label_table'
    elif fault=='null_row':rows[0]=None
    elif fault=='list_row':rows[0]=[]
    elif fault=='missing_name':del rows[0]['table_name']
    else:rows[0]['table_name']={'int_name':1,'bool_name':True,'null_name':None}[fault]
    connection=_LabelCatalogConnection(rows)
    assert label_schema.descriptor(connection) is False and len(connection.calls)==1


@pytest.mark.parametrize('table_index',range(4))
@pytest.mark.parametrize('fault',['kind','persistence','rls','force_rls','options','triggers','column_type','notnull','default',
    'identity','generated','collation','column_order','missing_constraint','constraint_definition','validated','deferrable',
    'deferred','extra_index','index_definition','valid','ready','immediate','nulls_not_distinct'])
def test_LE_G1_descriptor_batch_preserves_each_table_structural_checks(table_index,fault):
    rows=_label_catalog_rows();row=rows[table_index]
    if fault in {'kind','persistence','rls','force_rls','options','triggers'}:
        row[fault]={'kind':'v','persistence':'u','rls':True,'force_rls':True,'options':['fillfactor=70'],'triggers':1}[fault]
    elif fault in {'column_type','notnull','default','identity','generated','collation'}:
        field='type' if fault=='column_type' else fault
        row['columns'][0][field]={'column_type':'text','notnull':False,'default':'0','identity':'a','generated':'s','collation':'C'}[fault]
    elif fault=='column_order':row['columns'].reverse()
    elif fault=='missing_constraint':row['constraints'].pop()
    elif fault=='constraint_definition':row['constraints'][0]['definition']='PRIMARY KEY (wrong_id)'
    elif fault in {'validated','deferrable','deferred'}:row['constraints'][0][fault]=fault!='validated'
    elif fault=='extra_index':row['indexes'].append(deepcopy(row['indexes'][0]))
    elif fault=='index_definition':row['indexes'][0]['definition']='CREATE INDEX wrong_index'
    else:row['indexes'][0][fault]=fault=='nulls_not_distinct'
    connection=_LabelCatalogConnection(rows)
    assert label_schema.descriptor(connection) is False and len(connection.calls)==1


@pytest.mark.parametrize('anchor',["SELECT jsonb_build_object(","r.relname='lifecycle_execution_preparations'",
                                 "'identity', a.attidentity, 'generated', a.attgenerated)"])
@pytest.mark.parametrize('fault',['missing','duplicate'])
def test_LE_G1_descriptor_batch_refuses_changed_query_anchors_before_io(monkeypatch,anchor,fault):
    source=label_schema.CATALOG.text
    changed=source.replace(anchor,'changed_anchor',1) if fault=='missing' else source+' '+anchor
    monkeypatch.setattr(label_schema,'CATALOG',text(changed))
    connection=_LabelCatalogConnection(_label_catalog_rows())
    assert label_schema.descriptor(connection) is False and connection.calls==[]


@pytest.mark.parametrize('fault',['missing','duplicate','extra','unknown'])
def test_LE_G1_descriptor_batch_requires_one_exact_metadata_snapshot(monkeypatch,fault):
    tables=list(label_schema.metadata.tables.values())
    if fault=='missing':tables.pop()
    elif fault=='duplicate':tables[3]=tables[0]
    elif fault=='extra':tables.append(tables[0])
    else:tables[0]=SimpleNamespace(name='unexpected_label_table')
    calls=[]
    class Once:
        def values(self):
            calls.append('values')
            assert len(calls)==1
            return iter(tables)
    monkeypatch.setattr(label_schema,'metadata',SimpleNamespace(tables=Once()))
    connection=_LabelCatalogConnection([])
    assert label_schema.descriptor(connection) is False and connection.calls==[] and calls==['values']


@pytest.mark.parametrize('stage',['execute','scalars','all'])
def test_LE_G1_descriptor_batch_propagates_original_error_without_retry(stage):
    from sqlalchemy.exc import OperationalError
    error=OperationalError('synthetic catalog query',{},RuntimeError('synthetic driver failure'))
    connection=_LabelCatalogConnection(_label_catalog_rows(),error=error,error_stage=stage)
    with pytest.raises(OperationalError) as caught:label_schema.descriptor(connection)
    assert caught.value is error and len(connection.calls)==1


def test_LE_G1_descriptor_batch_reads_fresh_after_success_and_after_failure():
    original=_label_catalog_rows();connection=_LabelCatalogConnection(original)
    assert label_schema.descriptor(connection) is True
    connection.rows=deepcopy(original);connection.rows[1]['columns'][0]['default']='changed'
    assert label_schema.descriptor(connection) is False
    connection.rows=original
    assert label_schema.descriptor(connection) is True and len(connection.calls)==3
    separate=_LabelCatalogConnection(connection.rows)
    assert label_schema.descriptor(separate) is True and len(separate.calls)==1


# C12: fresh descriptor batches. Synthetic catalog evidence is not PostgreSQL evidence.
def _c12_schema(kind):
    from returnops_domain import return_execution_schema, label_artifact_schema, notification_schema
    return {'return': return_execution_schema, 'artifact': label_artifact_schema,
            'notification': notification_schema}[kind]


def _c12_parameters(kind):
    return {
        'return': dict(control_name='lifecycle_return_execution_controls',
                       permission_name='return_provider_permissions', ledger_name='core_mock_return_ledger'),
        'artifact': dict(permission_name='label_artifact_permissions', control_name='lifecycle_label_artifact_controls',
                         claim_name='lifecycle_label_artifact_claims', artifact_name='generated_label_artifacts',
                         content_name='generated_label_artifact_contents'),
        'notification': dict(control_name='notification_delivery_controls', fact_name='core_mock_notification_facts'),
    }[kind]


def _c12_catalog_rows(kind):
    """Complete synthetic rows from real frozen metadata; no connection or engine."""
    from sqlalchemy import LargeBinary
    schema = _c12_schema(kind)
    result = []
    for table in schema.metadata.tables.values():
        columns = []
        for column in table.columns:
            sql_type = ('timestamp with time zone' if isinstance(column.type, DateTime) else
                        'bigint' if isinstance(column.type, BigInteger) else
                        'boolean' if isinstance(column.type, Boolean) else
                        'bytea' if isinstance(column.type, LargeBinary) else
                        f'character varying({column.type.length})')
            columns.append(dict(name=column.name, type=sql_type, notnull=not column.nullable,
                                default=None, identity='', generated='',
                                collation='default' if isinstance(column.type, String) else None))
        constraints = [dict(name=table.name + '_pkey', type='p',
                            definition='PRIMARY KEY (' + ', '.join(c.name for c in table.primary_key) + ')')]
        constraints.extend(dict(name=name, type='c', definition=value)
                           for name, value in schema.CHECKS[table.name].items())
        keys = {table.name + '_pkey': (True, tuple(c.name for c in table.primary_key))}
        for constraint in table.constraints:
            if constraint.__class__.__name__ == 'UniqueConstraint':
                names = tuple(c.name for c in constraint.columns)
                constraints.append(dict(name=constraint.name, type='u', definition='UNIQUE (' + ', '.join(names) + ')'))
                keys[constraint.name] = (True, names)
        for constraint in table.foreign_key_constraints:
            elements = list(constraint.elements)
            constraints.append(dict(name=constraint.name, type='f', definition='FOREIGN KEY (' +
                ', '.join(e.parent.name for e in elements) + ') REFERENCES ' + elements[0].column.table.name +
                '(' + ', '.join(e.column.name for e in elements) + ')'))
        constraints = [{**item, 'validated': True, 'deferrable': False, 'deferred': False} for item in constraints]
        keys.update({index.name: (index.unique, tuple(c.name for c in index.columns)) for index in table.indexes})
        indexes = [dict(name=name, definition=f"CREATE {'UNIQUE ' if unique else ''}INDEX {name} "
                        f"ON descriptor_probe.{table.name} USING btree ({', '.join(names)})",
                        valid=True, ready=True, immediate=True, nulls_not_distinct=False)
                   for name, (unique, names) in keys.items()]
        result.append(dict(table_name=table.name, schema='descriptor_probe', kind='r', persistence='p',
                           rls=False, force_rls=False, options=None, triggers=0, columns=columns,
                           constraints=constraints, indexes=indexes))
    return result


class _C12CatalogResult:
    def __init__(self, connection, step, rows):
        self.connection, self.step, self.rows = connection, step, rows

    def scalars(self):
        self.connection.fail(self.step, 'scalars')
        return self

    def mappings(self):
        self.connection.fail(self.step, 'mappings')
        return self

    def all(self):
        self.connection.fail(self.step, 'all')
        return deepcopy(self.rows)


class _C12CatalogConnection:
    def __init__(self, kind, rows=None, *, error=None, error_step='structural', error_stage='execute'):
        from returnops_domain.customer_tables import evidence
        from returnops_domain.label_artifact_tables import NAMESPACE_CHECK
        self.kind = kind
        self.rows = _c12_catalog_rows(kind) if rows is None else rows
        self.calls = []
        self.error, self.error_step, self.error_stage = error, error_step, error_stage
        self.dialect = postgresql.dialect()
        self.ownership_rows = [dict(table_name=name, table_owner=17, baseline_owner=17,
                                   owner_only_acl=True, column_acl=False)
                               for name in _c12_parameters('notification').values()]
        names = {c.name for c in evidence.constraints if c.__class__.__name__ == 'CheckConstraint'} | {NAMESPACE_CHECK}
        self.namespace_rows = [dict(conname=name, contype='c', convalidated=True, condeferrable=False,
                                   condeferred=False, expression="((evidence_id)::text !~ '^glabel_[0-9a-f]{64}$'::text)"
                                   if name == NAMESPACE_CHECK else 'synthetic existing check')
                               for name in sorted(names)]

    def fail(self, step, stage):
        if self.error is not None and (step, stage) == (self.error_step, self.error_stage):
            raise self.error

    def execute(self, statement, parameters=None):
        sql = str(statement)
        if 'SELECT jsonb_build_object(' in sql:
            step, rows = 'structural', self.rows
        elif 'relation.relowner AS table_owner' in sql:
            step, rows = 'ownership', self.ownership_rows
        else:
            assert "r.relname='customer_evidence'" in sql
            step, rows = 'namespace', self.namespace_rows
        self.calls.append((step, sql, dict(parameters or {})))
        self.fail(step, 'execute')
        return _C12CatalogResult(self, step, rows)


@pytest.mark.parametrize('kind,order', [(kind, order) for kind, size in
    [('return', 3), ('artifact', 5), ('notification', 2)] for order in permutations(range(size))])
def test_C12_batches_accept_each_row_order_and_only_fixed_binds(kind, order):
    rows = _c12_catalog_rows(kind)
    connection = _C12CatalogConnection(kind, [rows[i] for i in order])
    assert _c12_schema(kind).descriptor(connection) is True
    expected_steps = {'return': ['structural'], 'artifact': ['structural', 'namespace'],
                      'notification': ['ownership', 'structural']}[kind]
    assert [call[0] for call in connection.calls] == expected_steps
    _, sql, parameters = next(call for call in connection.calls if call[0] == 'structural')
    assert parameters == _c12_parameters(kind)
    assert "'table_name', r.relname" in sql and 'n.nspname=current_schema()' in sql
    assert 'a.attrelid=r.oid' in sql and 'ORDER BY a.attnum' in sql
    assert all(':' + name in sql for name in parameters)
    assert all(name not in sql for name in parameters.values())


@pytest.mark.parametrize('kind', ['return', 'artifact', 'notification'])
@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'extra', 'unknown', 'null_row', 'list_row',
                                   'missing_name', 'int_name', 'bool_name', 'null_name'])
def test_C12_batches_reject_bad_row_identity_before_table_validation(kind, fault):
    rows = _c12_catalog_rows(kind)
    if fault == 'missing': rows.pop()
    elif fault == 'duplicate': rows[-1] = deepcopy(rows[0])
    elif fault == 'extra': rows.append(deepcopy(rows[0]))
    elif fault == 'unknown': rows[0]['table_name'] = 'unexpected_relation'
    elif fault == 'null_row': rows[0] = None
    elif fault == 'list_row': rows[0] = []
    elif fault == 'missing_name': del rows[0]['table_name']
    else: rows[0]['table_name'] = {'int_name': 1, 'bool_name': True, 'null_name': None}[fault]
    connection = _C12CatalogConnection(kind, rows)
    assert _c12_schema(kind).descriptor(connection) is False
    assert [c[0] for c in connection.calls] == (['ownership', 'structural'] if kind == 'notification' else ['structural'])


@pytest.mark.parametrize('kind,table_index', [(kind, index) for kind, size in
    [('return', 3), ('artifact', 5), ('notification', 2)] for index in range(size)])
@pytest.mark.parametrize('fault', ['kind', 'persistence', 'rls', 'force_rls', 'options', 'triggers',
    'column_type', 'notnull', 'default', 'identity', 'generated', 'collation', 'column_order',
    'missing_constraint', 'constraint_definition', 'validated', 'deferrable', 'deferred',
    'extra_index', 'index_definition', 'valid', 'ready', 'immediate', 'nulls_not_distinct'])
def test_C12_batches_keep_every_table_structural_rejection(kind, table_index, fault):
    rows = _c12_catalog_rows(kind)
    row = rows[table_index]
    if fault in {'kind', 'persistence', 'rls', 'force_rls', 'options', 'triggers'}:
        row[fault] = {'kind': 'v', 'persistence': 'u', 'rls': True, 'force_rls': True,
                      'options': ['fillfactor=70'], 'triggers': 1}[fault]
    elif fault in {'column_type', 'notnull', 'default', 'identity', 'generated', 'collation'}:
        field = 'type' if fault == 'column_type' else fault
        row['columns'][0][field] = {'column_type': 'text', 'notnull': False, 'default': '0',
                                   'identity': 'a', 'generated': 's', 'collation': 'C'}[fault]
    elif fault == 'column_order': row['columns'].reverse()
    elif fault == 'missing_constraint': row['constraints'].pop()
    elif fault == 'constraint_definition': row['constraints'][0]['definition'] = 'PRIMARY KEY (wrong_id)'
    elif fault in {'validated', 'deferrable', 'deferred'}: row['constraints'][0][fault] = fault != 'validated'
    elif fault == 'extra_index': row['indexes'].append(deepcopy(row['indexes'][0]))
    elif fault == 'index_definition': row['indexes'][0]['definition'] = 'CREATE INDEX wrong_index'
    else: row['indexes'][0][fault] = fault == 'nulls_not_distinct'
    connection = _C12CatalogConnection(kind, rows)
    assert _c12_schema(kind).descriptor(connection) is False
    assert [c[0] for c in connection.calls] == (['ownership', 'structural'] if kind == 'notification' else ['structural'])


@pytest.mark.parametrize('kind', ['return', 'artifact', 'notification'])
@pytest.mark.parametrize('anchor', ["SELECT jsonb_build_object(", "r.relname='lifecycle_execution_preparations'",
                                   "'identity', a.attidentity, 'generated', a.attgenerated)"])
@pytest.mark.parametrize('fault', ['missing', 'duplicate'])
def test_C12_batches_check_exact_query_anchors_without_structural_io(monkeypatch, kind, anchor, fault):
    schema = _c12_schema(kind)
    connection = _C12CatalogConnection(kind)
    source = schema.CATALOG.text
    changed = source.replace(anchor, 'changed_anchor', 1) if fault == 'missing' else source + ' ' + anchor
    monkeypatch.setattr(schema, 'CATALOG', text(changed))
    assert schema.descriptor(connection) is False
    assert [c[0] for c in connection.calls] == (['ownership'] if kind == 'notification' else [])


@pytest.mark.parametrize('kind', ['return', 'artifact', 'notification'])
@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'extra', 'unknown'])
def test_C12_batches_snapshot_exact_metadata_once_after_ownership(monkeypatch, kind, fault):
    schema = _c12_schema(kind)
    connection = _C12CatalogConnection(kind)
    original_names = tuple(schema.metadata.tables)
    tables = list(schema.metadata.tables.values())
    if fault == 'missing': tables.pop()
    elif fault == 'duplicate': tables[-1] = tables[0]
    elif fault == 'extra': tables.append(tables[0])
    else: tables[0] = SimpleNamespace(name='unexpected_relation')
    calls = []
    class Once:
        def __iter__(self):
            return iter(original_names)
        def values(self):
            calls.append('values')
            assert calls == ['values']
            return iter(tables)
    monkeypatch.setattr(schema, 'metadata', SimpleNamespace(tables=Once()))
    assert schema.descriptor(connection) is False
    assert calls == ['values']
    assert [c[0] for c in connection.calls] == (['ownership'] if kind == 'notification' else [])


@pytest.mark.parametrize('kind,step,stage', [
    (kind, 'structural', stage) for kind in ['return', 'artifact', 'notification']
    for stage in ['execute', 'scalars', 'all']] + [
    (kind, step, stage) for kind, step in [('artifact', 'namespace'), ('notification', 'ownership')]
    for stage in ['execute', 'mappings', 'all']])
def test_C12_batches_propagate_the_original_stage_error_without_retry(kind, step, stage):
    from sqlalchemy.exc import OperationalError
    error = OperationalError('synthetic catalog query', {}, RuntimeError('synthetic driver failure'))
    connection = _C12CatalogConnection(kind, error=error, error_step=step, error_stage=stage)
    with pytest.raises(OperationalError) as caught:
        _c12_schema(kind).descriptor(connection)
    assert caught.value is error
    expected = {'return': ['structural'], 'artifact': ['structural', 'namespace'],
                'notification': ['ownership', 'structural']}[kind]
    assert [c[0] for c in connection.calls] == expected[:expected.index(step) + 1]


@pytest.mark.parametrize('kind', ['return', 'artifact', 'notification'])
def test_C12_batches_are_fresh_after_success_failure_and_on_independent_connections(kind):
    schema = _c12_schema(kind)
    connection = _C12CatalogConnection(kind)
    original = deepcopy(connection.rows)
    assert schema.descriptor(connection) is True
    connection.rows[0]['columns'][0]['default'] = 'changed'
    assert schema.descriptor(connection) is False
    connection.rows = original
    assert schema.descriptor(connection) is True
    assert sum(c[0] == 'structural' for c in connection.calls) == 3
    separate = _C12CatalogConnection(kind)
    assert schema.descriptor(separate) is True
    assert sum(c[0] == 'structural' for c in separate.calls) == 1
    if kind == 'artifact':
        assert [c[0] for c in connection.calls] == ['structural', 'namespace', 'structural', 'structural', 'namespace']
    if kind == 'notification':
        assert [c[0] for c in connection.calls] == ['ownership', 'structural'] * 3


@pytest.mark.parametrize('fault', ['owner', 'table_acl', 'column_acl', 'missing', 'duplicate', 'unknown'])
def test_C12_notification_ownership_denial_stops_before_structural_query(fault):
    connection = _C12CatalogConnection('notification')
    if fault == 'owner': connection.ownership_rows[0]['table_owner'] = 99
    elif fault == 'table_acl': connection.ownership_rows[0]['owner_only_acl'] = False
    elif fault == 'column_acl': connection.ownership_rows[0]['column_acl'] = True
    elif fault == 'missing': connection.ownership_rows.pop()
    elif fault == 'duplicate': connection.ownership_rows[-1] = deepcopy(connection.ownership_rows[0])
    else: connection.ownership_rows[0]['table_name'] = 'unexpected_relation'
    assert _c12_schema('notification').descriptor(connection) is False
    assert [c[0] for c in connection.calls] == ['ownership']


@pytest.mark.parametrize('fault', ['expression', 'validated', 'deferrable', 'deferred', 'missing', 'extra'])
def test_C12_artifact_namespace_checks_still_run_last(fault):
    from returnops_domain.label_artifact_tables import NAMESPACE_CHECK
    connection = _C12CatalogConnection('artifact')
    row = next(r for r in connection.namespace_rows if r['conname'] == NAMESPACE_CHECK)
    if fault == 'expression': row['expression'] = 'true'
    elif fault == 'validated': row['convalidated'] = False
    elif fault == 'deferrable': row['condeferrable'] = True
    elif fault == 'deferred': row['condeferred'] = True
    elif fault == 'missing': connection.namespace_rows.remove(row)
    else: connection.namespace_rows.append({**row, 'conname': 'unexpected_namespace_check'})
    assert _c12_schema('artifact').descriptor(connection) is False
    assert [c[0] for c in connection.calls] == ['structural', 'namespace']


@pytest.mark.parametrize('fault', ['return_ledger_fk', 'artifact_bytea', 'artifact_composite_fk', 'notification_bytea'])
def test_C12_batches_keep_binary_and_foreign_key_boundaries(fault):
    kind = 'return' if fault == 'return_ledger_fk' else 'notification' if fault == 'notification_bytea' else 'artifact'
    connection = _C12CatalogConnection(kind)
    assert _c12_schema(kind).descriptor(connection) is True
    connection.calls.clear()
    if fault == 'return_ledger_fk':
        row = next(r for r in connection.rows if r['table_name'] == 'core_mock_return_ledger')
        assert not any(c['type'] == 'f' for c in row['constraints'])
        row['constraints'].append(dict(name='forbidden_ledger_fk', type='f', definition='FOREIGN KEY (effect_key) REFERENCES case_heads(case_id)',
                                       validated=True, deferrable=False, deferred=False))
    elif fault.endswith('bytea'):
        column = next(c for r in connection.rows for c in r['columns'] if c['type'] == 'bytea')
        column['type'] = 'text'
    else:
        constraint = next(c for r in connection.rows for c in r['constraints']
                          if c['type'] == 'f' and ', ' in c['definition'].split(') REFERENCES ')[0])
        constraint['definition'] = 'FOREIGN KEY (wrong_id) REFERENCES case_heads(case_id)'
    assert _c12_schema(kind).descriptor(connection) is False
    assert [c[0] for c in connection.calls] == (['ownership', 'structural'] if kind == 'notification' else ['structural'])
