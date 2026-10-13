"""G1..G6 actual persisted-source checks. Cloud PG only while local DB is paused."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import delete, select, update
from returnops_domain import customer_tables as old, founder_tables as founder
from returnops_domain import investigation_tables as inv, lifecycle_tables as life, storage
from returnops_domain import founder_codec as finite
from returnops_domain.audit import timestamp
from returnops_domain.canonical import digest, encode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.lifecycle_guards import LifecycleGuards
from returnops_domain.preview_profile import APPROVAL_COMPONENT, COMPONENT
from returnops_domain.preview_tables import previews
from approval_admission_helpers import approved, guard, change, current_history, provision_execution
from approve_helpers import approve
from manual_helpers import evidence, rows, snapshot


def assert_unchanged(engine, caller, values, status='DENIED'):
    before = snapshot(engine)
    result = caller.check(**values)
    assert result.status == status, asdict(result)
    assert snapshot(engine) == before
    assert set(asdict(result)) == {'status','safe_code'}
    return result


@pytest.mark.parametrize('outcome', ['PASS','PASS_WITH_WARNING'])
def test_AG_G1_actual_complete_chain_is_checked_without_any_row_change(flow_engine, identities, enabled, request, outcome):
    values, setup = approved(flow_engine, identities, outcome=outcome)
    before = snapshot(flow_engine); caller = guard(flow_engine, identities)
    first = assert_unchanged(flow_engine, caller, values, 'CHECKED')
    second = assert_unchanged(flow_engine, caller, values, 'CHECKED')
    replay = approve(flow_engine, identities).accept(setup['case'], setup['request'],
        values['original_approval_key'], 'admission-original-replay')
    assert replay.receipt == setup['result'].receipt and snapshot(flow_engine) == before
    assert first == second
    expiry = datetime.fromisoformat(setup['action']['scope']['expires_at'].replace('Z','+00:00'))
    expired_replay = approve(flow_engine, identities, clock=lambda:expiry).accept(setup['case'], setup['request'],
        values['original_approval_key'], 'expired-original-replay')
    assert expired_replay.receipt == replay.receipt and snapshot(flow_engine) == before
    assert_unchanged(flow_engine, guard(flow_engine, identities, clock=lambda:expiry), values)
    evidence(request.node.nodeid, result=asdict(first), before=before, after=snapshot(flow_engine),
             actual_scope=setup['action']['scope'], replay=asdict(expired_replay))


@pytest.mark.parametrize('name', [None,'customer_a','customer_b'])
def test_AG_G2_real_identity_is_required(flow_engine, identities, enabled, name):
    values, _ = approved(flow_engine, identities)
    assert_unchanged(flow_engine, guard(flow_engine, identities, name), values)


@pytest.mark.parametrize('mutation', ['session','founder','owner','store','execution_disabled','wrong_component'])
def test_AG_G2_current_registry_and_execution_authority(flow_engine, identities, enabled, mutation):
    values, _ = approved(flow_engine, identities)
    if mutation == 'session':
        change(flow_engine, old.sessions, old.sessions.c.session_id == identities.sessions['founder']['session_id'], revoked=True)
    elif mutation in {'founder','owner'}:
        person = identities.people['founder' if mutation == 'founder' else 'customer_a']['principal_id']
        change(flow_engine, old.principals, old.principals.c.principal_id == person, enabled=False)
    elif mutation == 'store':
        change(flow_engine, old.principals, old.principals.c.principal_id == identities.people['founder']['principal_id'], store_id='store_other')
    else:
        clause = (life.authorities.c.component_id == APPROVAL_COMPONENT) & (life.authorities.c.purpose == 'EXECUTION')
        change(flow_engine, life.authorities, clause, **({'enabled':False} if mutation == 'execution_disabled'
                                                      else {'component_id':'wrong_component'}))
    assert_unchanged(flow_engine, guard(flow_engine, identities), values)


@pytest.mark.parametrize('purpose', ['PREVIEW','APPROVAL','EFFECT'])
def test_AG_G2_other_purposes_do_not_replace_execution(flow_engine, identities, enabled, purpose):
    values, _ = approved(flow_engine, identities, execution=False)
    provision_execution(flow_engine, identities, purpose=purpose)
    assert_unchanged(flow_engine, guard(flow_engine, identities), values)


def test_AG_G2_historical_producer_grants_are_not_current_execution_authority(flow_engine, identities, enabled):
    values, _ = approved(flow_engine, identities)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        changed = uow.execute(update(life.authorities).where(life.authorities.c.purpose != 'EXECUTION').values(enabled=False))
        assert changed.rowcount > 0
        uow.commit()
    assert_unchanged(flow_engine, guard(flow_engine, identities), values, 'CHECKED')


def test_AG_G2_another_real_founder_is_not_the_original_approver(flow_engine,identities,enabled):
    import jwt
    from returnops_domain.registry import TrustedRegistry
    values,_=approved(flow_engine,identities)
    person={**identities.people['founder'],'principal_id':'different_founder'}
    session={**identities.sessions['founder'],'principal_id':person['principal_id'],'session_id':'different_founder_session'}
    TrustedRegistry(flow_engine).provision([person],[session])
    config=identities.auth_config
    token=jwt.encode(dict(iss=config.issuer,aud=config.audience,sub=person['principal_id'],jti=session['session_id'],
        iat=session['issued_at'],nbf=session['not_before'],exp=session['expires_at']),config.signing_key,algorithm='HS256')
    from returnops_api.private_approval_admission import compose_private_approval_admission
    caller=compose_private_approval_admission(flow_engine,config,'Bearer '+token)
    result=assert_unchanged(flow_engine,caller,values)
    assert result.safe_code=='FORBIDDEN'


@pytest.mark.parametrize('kind', ['PROPOSAL','REVIEW','DECISION','APPROVAL'])
def test_AG_G3_missing_history_body_never_reconstructed(flow_engine, identities, enabled, kind):
    values, setup = approved(flow_engine, identities)
    record = current_history(flow_engine, setup['case'], kind)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        assert uow.execute(delete(old.history_contents).where(old.history_contents.c.record_id == record['record_id'])).rowcount == 1
        uow.commit()
    assert_unchanged(flow_engine, guard(flow_engine, identities), values)


@pytest.mark.parametrize('kind',['PROPOSAL','REVIEW','APPROVAL'])
def test_AG_G3_missing_current_finite_encoding_fails_without_backfill(flow_engine,identities,enabled,kind):
    values,setup=approved(flow_engine,identities)
    record=current_history(flow_engine,setup['case'],kind)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert uow.execute(delete(founder.encodings).where(founder.encodings.c.record_id==record['record_id'])).rowcount==1
        uow.commit()
    assert_unchanged(flow_engine,guard(flow_engine,identities),values)


@pytest.mark.parametrize('target', ['source_binding','event','approval_work','preview','audit','statement','order_body','receipt','receipt_ref'])
def test_AG_G3_actual_lower_layer_source_corruption_fails_closed(flow_engine, identities, enabled, target):
    values, setup = approved(flow_engine, identities); case = setup['case']
    record = current_history(flow_engine, case, 'APPROVAL')
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        if target == 'source_binding':
            statement = update(life.sources).where(life.sources.c.record_id == record['record_id']).values(source_hash='0'*64)
        elif target == 'event':
            statement = update(life.events).where(life.events.c.record_id == record['record_id']).values(fingerprint='0'*64)
        elif target == 'approval_work':
            statement = update(life.work).where(life.work.c.case_id == case, life.work.c.purpose == 'APPROVAL').values(epoch=2)
        elif target == 'preview':
            statement = update(previews).where(previews.c.case_id == case).values(body_hash='0'*64)
        elif target == 'audit':
            statement = update(old.audit).where(old.audit.c.case_id == case, old.audit.c.sequence == 1).values(event_hash='0'*64)
        elif target == 'statement':
            ids = select(storage.original_statement_records.c.statement_id).where(storage.original_statement_records.c.case_id == case)
            statement = update(storage.original_statement_contents).where(storage.original_statement_contents.c.statement_id.in_(ids)).values(raw_text=b'changed original')
        elif target == 'order_body':
            ids = select(inv.receipts.c.receipt_id).where(inv.receipts.c.case_id == case)
            statement = update(inv.receipt_contents).where(inv.receipt_contents.c.receipt_id.in_(ids)).values(body=b'changed receipt')
        else:
            fact = uow.execute(select(old.acceptances).where(old.acceptances.c.target == case,
                old.acceptances.c.operation == 'recordFounderDecision')).mappings().one()
            statement = (update(old.receipts).where(old.receipts.c.acceptance_id == fact['acceptance_id']).values(body=None,available=False)
                if target == 'receipt' else delete(old.receipt_refs).where(old.receipt_refs.c.acceptance_id == fact['acceptance_id'],old.receipt_refs.c.kind == 'CASE'))
        assert uow.execute(statement).rowcount >= 1
        uow.commit()
    assert_unchanged(flow_engine, guard(flow_engine, identities), values)


def test_AG_G3_legacy_missing_encoding_cannot_insert_metadata(flow_engine, identities, enabled, monkeypatch):
    """Directly exercise the real legacy read helper through the production facade."""
    from returnops_domain import approval_admission as implementation
    from returnops_domain.founder_integrity import CaseProof, read_revision
    values, setup = approved(flow_engine, identities)
    record = current_history(flow_engine, setup['case'], 'APPROVAL')
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        raw = uow.execute(select(old.history_contents.c.body).where(old.history_contents.c.record_id == record['record_id'])).scalar_one()
        body = finite.decode_document(raw)
        assert uow.execute(delete(founder.encodings).where(founder.encodings.c.record_id == record['record_id'])).rowcount == 1
        assert uow.execute(update(old.history_contents).where(old.history_contents.c.record_id == record['record_id']).values(body=encode_document(body))).rowcount == 1
        assert uow.execute(update(old.history).where(old.history.c.record_id == record['record_id']).values(content_sha256=digest(body,'history/v1'))).rowcount == 1
        uow.commit()
    original = implementation.read_proof; observed=[]
    def legacy_read(reads, actor, head, *args):
        proof = CaseProof(reads, head)
        # Row identity/audit ref remain real; this deliberately legacy-encoded
        # body reaches the actual reader's attempted metadata registration.
        original_execute = reads.execute
        def checked(statement, parameters=None):
            if getattr(statement,'is_insert',False): observed.append(statement.table.name)
            return original_execute(statement,parameters)
        reads.execute = checked
        read_revision(reads, proof.revisions[record['record_id']], proof)
        return original(reads,actor,head,*args)
    monkeypatch.setattr(implementation,'read_proof',legacy_read)
    assert_unchanged(flow_engine,guard(flow_engine,identities),values)
    assert observed == [founder.encodings.name]


@pytest.mark.parametrize('kind',['PROPOSAL','REVIEW','APPROVAL'])
def test_AG_G3_rehashed_body_is_not_original_provenance(flow_engine,identities,enabled,kind):
    values,setup=approved(flow_engine,identities)
    record=current_history(flow_engine,setup['case'],kind)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        raw=uow.execute(select(old.history_contents.c.body).where(old.history_contents.c.record_id==record['record_id'])).scalar_one()
        body=finite.decode_document(raw)
        if kind=='PROPOSAL': body['packet']['proposal_version']+=1
        elif kind=='REVIEW': body['review']['outcome']='ESCALATE'
        else: body['principal_id']='different_founder'
        hashed=finite.digest(body)
        uow.execute(update(old.history_contents).where(old.history_contents.c.record_id==record['record_id']).values(body=finite.encode_document(body)))
        uow.execute(update(old.history).where(old.history.c.record_id==record['record_id']).values(content_sha256=hashed))
        uow.execute(update(founder.encodings).where(founder.encodings.c.record_id==record['record_id']).values(source_content_sha256=hashed,projected_content_sha256=hashed))
        uow.commit()
    assert_unchanged(flow_engine,guard(flow_engine,identities),values)


@pytest.mark.parametrize('field,value', [('case_id','case_unknown'),('expected_case_version',1),
    ('expected_case_version',True),('execution_work_id','execution_unknown')])
def test_AG_G4_request_current_identity_and_versions(flow_engine, identities, enabled, field, value):
    values, _ = approved(flow_engine, identities); values[field]=value
    assert_unchanged(flow_engine,guard(flow_engine,identities),values)


@pytest.mark.parametrize('mutation', ['provider','order','parcel','line','quantity','bool_quantity','float_quantity',
                                    'extra','label','command_id','label_reference','label_chargeable'])
def test_AG_G4_exact_candidate_and_both_saved_commands(flow_engine, identities, enabled, mutation):
    values, setup = approved(flow_engine, identities)
    command=deepcopy(values['candidate_command'])
    if mutation == 'label': command=deepcopy(setup['action']['scope']['commands'][1])
    elif mutation in {'label_reference','label_chargeable'}:
        # Tamper persisted second-command bytes and its body hash together;
        # the full historical preview proof still rejects this altered scope.
        from returnops_domain.canonical import decode_document
        row,=[r for r in rows(flow_engine,previews) if r['case_id']==setup['case']]
        body=decode_document(row['body']); p=body['scope']['commands'][1]['parameters']
        p['return_command_id' if mutation=='label_reference' else 'chargeable']='return_other' if mutation=='label_reference' else True
        from returnops_domain.lifecycle_effects import fingerprint
        body['scope_fingerprint']=fingerprint(body['scope'])
        change(flow_engine,previews,previews.c.preview_id==row['preview_id'],body=encode_document(body),body_hash=digest(body,'action-preview-body/v1'))
    elif mutation=='provider': command['provider_id']='provider_other'
    elif mutation=='order': command['parameters']['order_id']='order_other'
    elif mutation=='parcel': command['parameters']['parcel_id']='parcel_other'
    elif mutation=='line': command['parameters']['line_items'][0]['line_item_id']='line_other'
    elif mutation=='extra': command['parameters']['return_id']='client_forged'
    elif mutation=='command_id': command['command_id']='command_other'
    else: command['parameters']['line_items'][0]['quantity']={'quantity':2,'bool_quantity':True,'float_quantity':1.0}[mutation]
    values['candidate_command']=command
    assert_unchanged(flow_engine,guard(flow_engine,identities),values)


@pytest.mark.parametrize('mutation',['currency','amount','boolean_amount','environment','allowlist','order',
    'count','duplicate_commands','duplicate_lines','unsorted_lines','over_quantity','parcel','pdf','expiry'])
def test_AG_G4_rehashed_saved_full_scope_cannot_replace_original(flow_engine,identities,enabled,mutation):
    from returnops_domain.canonical import decode_document
    from returnops_domain.lifecycle_effects import fingerprint
    values,setup=approved(flow_engine,identities)
    row,=[r for r in rows(flow_engine,previews) if r['case_id']==setup['case']]
    body=decode_document(row['body']); scope=body['scope']; commands=scope['commands']
    if mutation=='currency': scope['currency']='USD'
    elif mutation=='amount': scope['amount_ceiling_minor']=1
    elif mutation=='boolean_amount': scope['amount_ceiling_minor']=False
    elif mutation=='environment': scope['environment']='SANDBOX'
    elif mutation=='allowlist': scope['allowlist_version']='mock-v2'
    elif mutation=='order': commands.reverse()
    elif mutation=='count': commands.pop()
    elif mutation=='duplicate_commands': commands[1]['command_id']=commands[0]['command_id']
    elif mutation=='duplicate_lines': commands[0]['parameters']['line_items'].append(deepcopy(commands[0]['parameters']['line_items'][0]))
    elif mutation=='unsorted_lines':
        assert len(commands[0]['parameters']['line_items'])>1
        commands[0]['parameters']['line_items'].reverse()
    elif mutation=='over_quantity': commands[0]['parameters']['line_items'][0]['quantity']=1000
    elif mutation=='parcel': scope['parcel_id']='parcel_other'
    elif mutation=='pdf': commands[1]['parameters']['label_format']='PNG'
    elif mutation=='expiry': scope['expires_at']='2099-01-01T00:00:00Z'
    body['scope_fingerprint']=fingerprint(scope)
    change(flow_engine,previews,previews.c.preview_id==row['preview_id'],body=encode_document(body),body_hash=digest(body,'action-preview-body/v1'))
    assert_unchanged(flow_engine,guard(flow_engine,identities),values)


@pytest.mark.parametrize('offset', [0,1])
def test_AG_G4_expiry_equality_and_after(flow_engine,identities,enabled,offset):
    values,setup=approved(flow_engine,identities)
    expires=datetime.fromisoformat(setup['action']['scope']['expires_at'].replace('Z','+00:00'))
    assert_unchanged(flow_engine,guard(flow_engine,identities,clock=lambda:expires+timedelta(seconds=offset)),values)


def test_AG_G4_original_key_unknown_and_conflict(flow_engine,identities,enabled):
    values,setup=approved(flow_engine,identities)
    unknown={**values,'original_approval_key':'a-new-key-is-not-a-new-intent'}
    assert_unchanged(flow_engine,guard(flow_engine,identities),unknown,'UNKNOWN')
    fact,=[r for r in rows(flow_engine,old.acceptances) if r['target']==setup['case'] and r['operation']=='recordFounderDecision']
    change(flow_engine,old.acceptances,old.acceptances.c.acceptance_id==fact['acceptance_id'],fingerprint='0'*64)
    result=assert_unchanged(flow_engine,guard(flow_engine,identities),values)
    assert result.safe_code=='IDEMPOTENCY_CONFLICT'


@pytest.mark.parametrize('field,value', [('target_hash','0'*64),('component_id','component_other'),('owner_id','owner_other'),
    ('idempotency_key','different-execution-key'),('state','SUPERSEDED'),('state','PAUSED'),('state','DONE'),
    ('epoch',1),('claim_id','claim_other'),('claimed_case_version',1),('authority_revision',1),
    ('lease_expires_at',datetime(2099,1,1,tzinfo=timezone.utc))])
def test_AG_G5_execution_is_specialized_pending_and_unclaimed(flow_engine,identities,enabled,field,value):
    values,_=approved(flow_engine,identities)
    change(flow_engine,life.work,life.work.c.work_id==values['execution_work_id'],**{field:value})
    assert_unchanged(flow_engine,guard(flow_engine,identities),values)


def test_AG_G5_generic_claim_stays_rejected_with_execution_grant(flow_engine,identities,enabled):
    values,_=approved(flow_engine,identities); before=snapshot(flow_engine)
    with pytest.raises(FlowError):
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            LifecycleGuards(APPROVAL_COMPONENT).claim(uow,values['execution_work_id'],datetime.now(timezone.utc))
    assert snapshot(flow_engine)==before
    assert_unchanged(flow_engine,guard(flow_engine,identities),values,'CHECKED')


@pytest.mark.parametrize('status',['EXECUTING','UNKNOWN','RECONCILING','SUCCEEDED','FAILED','BLOCKED'])
@pytest.mark.parametrize('effect_ref',[False,True])
def test_AG_G6_prior_operations_are_not_retried_under_another_identity(flow_engine,identities,enabled,status,effect_ref,request):
    """Explicit prior-operation fixture only; no actual dispatch is claimed."""
    from returnops_domain.audit import identifier
    from returnops_domain.lifecycle_effects import fingerprint
    from synthetic_sources import stage, head
    values,setup=approved(flow_engine,identities)
    case=setup['case']; scope=setup['action']['scope']; command=scope['commands'][0]
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        h=head(uow,case)
        body=dict(operation_id=identifier('prior_operation'),case_id=case,case_version=h['case_version'],
            command_id=command['command_id'],approval_id=setup['result'].receipt['approval_id'],
            proposal_id=scope['proposal_id'],proposal_version=scope['proposal_version'],input_version=scope['input_version'],
            provider_id='a_different_saved_provider',operation_fingerprint=fingerprint(dict(approval_id=setup['result'].receipt['approval_id'],
                scope_fingerprint=setup['action']['scope_fingerprint'],command=command)),status=status,attempt_count=1,
            updated_at=timestamp(datetime.now(timezone.utc)),idempotency_key='a-different-prior-key')
        if status=='SUCCEEDED':
            body['result']=dict(type='CREATE_RETURN',provider_return_id='prior_provider_return',parcel_id=scope['parcel_id'])
        if status in {'FAILED','BLOCKED','UNKNOWN','RECONCILING'}:
            body['error']={'error':dict(code='PROVIDER_UNAVAILABLE',message='Synthetic earlier outcome.',
                correlation_id='prior_operation_correlation',retryable=False,details=[])}
        record=stage(uow,h,'OPERATION',body)
        if effect_ref:
            state=uow.execute(select(life.state).where(life.state.c.case_id==case)).mappings().one()
            uow.execute(life.effects.insert().values(operation_id=body['operation_id'],case_id=case,record_id=record,
                object_version=1,approval_record_id=state['approval_record_id'],command_id=command['command_id'],
                input_version=scope['input_version'],generation=state['generation'],operation_type='CREATE_RETURN',
                status=status,identity_hash='a'*64))
        uow.commit()
    expected='UNKNOWN' if status in {'UNKNOWN','RECONCILING'} else 'DENIED'
    before=snapshot(flow_engine)
    result=assert_unchanged(flow_engine,guard(flow_engine,identities),values,expected)
    replacement={**values,'original_approval_key':'new-approval-key-cannot-retry'}
    assert_unchanged(flow_engine,guard(flow_engine,identities),replacement,expected)
    evidence(request.node.nodeid,prior_operation_fixture=True,status=status,effect_ref=effect_ref,
             result=asdict(result),before=before,after=snapshot(flow_engine))
