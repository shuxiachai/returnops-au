"""G7/G8 late checks and actual advisory-fence races; cloud PG only."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import delete, select, update, text
from sqlalchemy.exc import OperationalError
from returnops_domain import customer_tables as old, lifecycle_tables as life, storage
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown
from returnops_domain.preview_profile import APPROVAL_COMPONENT
from returnops_domain.retention import RetentionService
from approval_admission_helpers import approved, guard
from manual_helpers import evidence, rows, snapshot
from test_approval_admission_postgresql import assert_unchanged
from test_founder_approve_late_postgresql import _overlap_at_actual_fence


def _short_signed_session(engine,identities):
    """Test-only registry/JWT pair whose real expiry precedes preview expiry."""
    import jwt
    session={**identities.sessions['founder'],
             'expires_at':int(datetime.now(timezone.utc).timestamp())+120}
    with CustomerUnitOfWork(engine,write=True) as uow:
        assert uow.execute(update(old.sessions).where(old.sessions.c.session_id==session['session_id'])
            .values(expires_at=session['expires_at'])).rowcount==1
        uow.commit()
    identities.sessions['founder']=session
    config=identities.auth_config
    identities.tokens['founder']=jwt.encode(dict(iss=config.issuer,aud=config.audience,
        sub=session['principal_id'],jti=session['session_id'],iat=session['issued_at'],
        nbf=session['not_before'],exp=session['expires_at']),config.signing_key,algorithm='HS256')
    return datetime.fromtimestamp(session['expires_at'],timezone.utc)


def _authentication_wall(monkeypatch,wall):
    import jwt.api_jwt
    from returnops_api.security import authentication
    class Wall:
        @staticmethod
        def now(tz): return wall[0].astimezone(tz)
    monkeypatch.setattr(authentication,'datetime',Wall)
    monkeypatch.setattr(jwt.api_jwt,'datetime',Wall)


@pytest.mark.parametrize('boundary',['closure','authorize_reads','last_session_leeway'])
def test_AG_G7_real_signed_session_expires_at_final_read_boundary(flow_engine,identities,enabled,monkeypatch,request,boundary):
    from dataclasses import replace
    from sqlalchemy import event
    from returnops_api.private_approval_admission import compose_private_approval_admission
    from returnops_domain import approval_admission as implementation, approval_admission_sources as sources
    deadline=_short_signed_session(flow_engine,identities)
    values,setup=approved(flow_engine,identities)
    preview_expiry=datetime.fromisoformat(setup['action']['scope']['expires_at'].replace('Z','+00:00'))
    assert deadline<preview_expiry
    wall=[datetime.now(timezone.utc)]; _authentication_wall(monkeypatch,wall)
    assert wall[0]<deadline
    config=replace(identities.auth_config,leeway_seconds=5 if boundary=='last_session_leeway' else 0)
    caller=compose_private_approval_admission(flow_engine,config,'Bearer '+identities.tokens['founder'],clock=lambda:wall[0])
    closures=[]; versions=[]; sessions=[]; crossed=[]; last_returned=[]; later_sql=[]
    original_closure=implementation.source_closure; original_version=sources.version; real_authority=caller.authority
    def closure(*args):
        value=original_closure(*args); closures.append(len(closures)+1)
        if boundary=='closure' and len(closures)==2:
            wall[0]=deadline; crossed.append('after_final_raw_closure')
        return value
    def schema(connection):
        value=original_version(connection); versions.append(len(versions)+1)
        if boundary=='authorize_reads' and len(versions)==2:
            wall[0]=deadline; crossed.append('after_final_authorize_schema_read')
        return value
    def authority(connection,operation,resource=None):
        if operation=='getSession':
            sessions.append(len(sessions)+1)
            if boundary=='last_session_leeway' and len(sessions)==3:
                wall[0]=deadline; crossed.append('last_real_f03_with_leeway')
        actor=real_authority(connection,operation,resource)
        if operation=='getSession' and len(sessions)==3: last_returned.append(True)
        return actor
    def observe(*args):
        if last_returned: later_sql.append('SQL_after_last_session')
    monkeypatch.setattr(implementation,'source_closure',closure)
    monkeypatch.setattr(sources,'version',schema)
    caller.authority=authority
    before=snapshot(flow_engine); event.listen(flow_engine,'before_cursor_execute',observe)
    try: result=caller.check(**values)
    finally: event.remove(flow_engine,'before_cursor_execute',observe)
    assert result.status=='DENIED' and snapshot(flow_engine)==before
    assert closures==[1,2] and crossed and wall[0]==deadline<preview_expiry
    assert not later_sql
    if boundary=='last_session_leeway':
        # This real signed JWT was accepted by unchanged F.03's five-second
        # leeway. The guard's additional strict final deadline rejects equality.
        assert sessions==[1,2,3] and last_returned==[True]
    elif boundary=='authorize_reads': assert versions==[1,2] and sessions==[1,2,3]
    evidence(request.node.nodeid,boundary=boundary,closure_calls=closures,authorize_schema_calls=versions,
        session_calls=sessions,crossed=crossed,real_final_f03_returned=last_returned,
        no_sql_after_last_session=not later_sql,session_deadline=deadline,preview_expiry=preview_expiry,
        result=asdict(result),before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('field',['issued_at','not_before','expires_at'])
def test_AG_G7_changed_registry_dates_cannot_keep_original_signed_identity(flow_engine,identities,enabled,monkeypatch,field):
    from returnops_domain import approval_admission as implementation
    _short_signed_session(flow_engine,identities)
    values,_=approved(flow_engine,identities); original=implementation.read_proof; calls=[]
    def changed(reads,*args):
        value=original(reads,*args); calls.append(len(calls)+1)
        if len(calls)==2:
            saved=identities.sessions['founder'][field]
            assert reads._uow.execute(update(old.sessions).where(old.sessions.c.session_id==identities.sessions['founder']['session_id'])
                .values(**{field:saved-1 if field=='issued_at' else saved+1})).rowcount==1
        return value
    monkeypatch.setattr(implementation,'read_proof',changed)
    assert_unchanged(flow_engine,guard(flow_engine,identities),values)
    assert calls==[1,2]


@pytest.mark.parametrize('change',['revoked','disabled','replacement_session'])
def test_AG_G7_last_real_session_check_detects_current_identity_change(flow_engine,identities,enabled,change):
    import jwt
    from returnops_api.customer_authority import CurrentRequestAuthority
    values,_=approved(flow_engine,identities); caller=guard(flow_engine,identities); real=caller.authority
    replacement={**identities.sessions['founder'],'session_id':'admission_replacement_session'}
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(old.sessions.insert().values(**replacement)); uow.commit()
    config=identities.auth_config
    token=jwt.encode(dict(iss=config.issuer,aud=config.audience,sub=replacement['principal_id'],jti=replacement['session_id'],
        iat=replacement['issued_at'],nbf=replacement['not_before'],exp=replacement['expires_at']),config.signing_key,algorithm='HS256')
    other=CurrentRequestAuthority(config,'Bearer '+token); calls=[]; changes=[]
    def current(connection,operation,resource=None):
        if operation=='getSession': calls.append(len(calls)+1)
        if operation=='getSession' and len(calls)==3:
            if change=='replacement_session':
                changes.append(change); return other(connection,operation,resource)
            statement=(update(old.sessions).where(old.sessions.c.session_id==identities.sessions['founder']['session_id']).values(revoked=True)
                if change=='revoked' else update(old.principals).where(old.principals.c.principal_id==identities.people['founder']['principal_id']).values(enabled=False))
            assert connection.execute(statement).rowcount==1; changes.append(change)
        return real(connection,operation,resource)
    caller.authority=current
    assert_unchanged(flow_engine,caller,values)
    assert calls==[1,2,3] and changes==[change]


@pytest.mark.parametrize('change',['raw_statement','session','execution_revoked','execution_revision','head_version',
    'work_claim','receipt','schema','expiry','backwards_time'])
def test_AG_G7_mutation_after_final_expensive_read_is_detected(flow_engine,identities,enabled,monkeypatch,request,change):
    from returnops_domain import approval_admission as implementation
    values,setup=approved(flow_engine,identities)
    initial=datetime.now(timezone.utc); current=[initial]
    expires=datetime.fromisoformat(setup['action']['scope']['expires_at'].replace('Z','+00:00'))
    original=implementation.read_proof; calls=[]; changes=[]
    def late(reads,*args):
        result=original(reads,*args); calls.append(len(calls)+1)
        if len(calls)==2:
            # Deliberate same-transaction fault injection after proof, not an
            # unfenced external writer supposedly bypassing supported locking.
            uow=reads._uow
            if change=='expiry': current[0]=expires
            elif change=='backwards_time': current[0]=initial-timedelta(microseconds=1)
            elif change=='raw_statement':
                ids=select(storage.original_statement_records.c.statement_id).where(storage.original_statement_records.c.case_id==setup['case'])
                assert uow.execute(update(storage.original_statement_contents).where(storage.original_statement_contents.c.statement_id.in_(ids)).values(raw_text=b'changed after final proof')).rowcount==1
            elif change=='session':
                assert uow.execute(update(old.sessions).where(old.sessions.c.session_id==identities.sessions['founder']['session_id']).values(revoked=True)).rowcount==1
            elif change.startswith('execution_'):
                patch={'enabled':False} if change=='execution_revoked' else {'revision':2}
                assert uow.execute(update(life.authorities).where(life.authorities.c.component_id==APPROVAL_COMPONENT,
                    life.authorities.c.purpose=='EXECUTION').values(**patch)).rowcount==1
            elif change=='head_version':
                assert uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==setup['case']).values(case_version=values['expected_case_version']+1)).rowcount==1
            elif change=='work_claim':
                assert uow.execute(update(life.work).where(life.work.c.work_id==values['execution_work_id']).values(claim_id='late_claim')).rowcount==1
            elif change=='receipt':
                fact=uow.execute(select(old.acceptances).where(old.acceptances.c.target==setup['case'],old.acceptances.c.operation=='recordFounderDecision')).mappings().one()
                assert uow.execute(update(old.receipts).where(old.receipts.c.acceptance_id==fact['acceptance_id']).values(body=None,available=False)).rowcount==1
            elif change=='schema':
                assert uow.connection.execute(text("UPDATE alembic_version SET version_num='unknown_guard_schema'")).rowcount==1
            changes.append(change)
        return result
    monkeypatch.setattr(implementation,'read_proof',late)
    before=snapshot(flow_engine)
    result=assert_unchanged(flow_engine,guard(flow_engine,identities,clock=lambda:current[0]),values)
    assert calls==[1,2] and changes==[change]
    evidence(request.node.nodeid,change=change,proof_calls=calls,after_final_proof_faults=changes,
             result=asdict(result),before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('committed',[False,True])
def test_AG_G7_uncertain_commit_never_retries_or_writes(flow_engine,identities,enabled,request,committed):
    values,_=approved(flow_engine,identities); entered=[]
    class UnknownCommit(CustomerUnitOfWork):
        def __enter__(self): entered.append('enter'); return super().__enter__()
        def commit(self):
            for check in self._commit_checks: check()
            if committed: self.transaction.commit()
            else: self.transaction.rollback()
            self.finished=True
            raise AcceptanceOutcomeUnknown()
    before=snapshot(flow_engine)
    result=assert_unchanged(flow_engine,guard(flow_engine,identities,uow_factory=UnknownCommit),values,'UNKNOWN')
    assert entered==['enter']
    evidence(request.node.nodeid,ack_lost_after_commit=committed,result=asdict(result),before=before,after=snapshot(flow_engine))


def test_AG_G7_close_ambiguity_does_not_return_checked(flow_engine,identities,enabled):
    values,_=approved(flow_engine,identities); calls=[]
    class UnknownClose(CustomerUnitOfWork):
        def __exit__(self,*args):
            result=super().__exit__(*args); calls.append('close')
            raise AcceptanceOutcomeUnknown()
    assert_unchanged(flow_engine,guard(flow_engine,identities,uow_factory=UnknownClose),values,'UNKNOWN')
    assert calls==['close']


@pytest.mark.parametrize('change',['retention','revocation'])
@pytest.mark.parametrize('first',['check','mutation'])
def test_AG_G8_actual_fence_orders_check_against_supported_mutation(flow_engine,identities,enabled,monkeypatch,request,change,first):
    values,setup=approved(flow_engine,identities)
    original=next(row for row in rows(flow_engine,old.history) if row['case_id']==setup['case'] and row['kind']=='STATEMENT')
    before=snapshot(flow_engine); captured={}
    def mutate():
        if change=='retention': result=RetentionService(flow_engine).remove('STATEMENT',original['object_id'])
        else:
            with CustomerUnitOfWork(flow_engine,write=True) as uow:
                assert uow.execute(update(life.authorities).where(life.authorities.c.component_id==APPROVAL_COMPONENT,
                    life.authorities.c.purpose=='EXECUTION').values(enabled=False,revision=2)).rowcount==1
                uow.commit()
            result=True
        captured['after_mutation']=snapshot(flow_engine)
        return result
    caller=guard(flow_engine,identities)
    results,overlap=_overlap_at_actual_fence(flow_engine,monkeypatch,
        dict(check=lambda:caller.check(**values),mutation=mutate),first=first)
    assert results['mutation'] is True
    assert results['check'].status==('CHECKED' if first=='check' else 'DENIED')
    after=snapshot(flow_engine)
    assert after==captured['after_mutation']
    if change=='revocation':
        unchanged={name:value for name,value in after.items() if name!=life.authorities.name}
        assert unchanged=={name:value for name,value in before.items() if name!=life.authorities.name}
    assert_unchanged(flow_engine,caller,values)
    evidence(request.node.nodeid,change=change,first=first,before=before,after=after,overlap=overlap,
             checked=asdict(results['check']),mutation_result=results['mutation'])


def test_AG_G8_installed_actual_private_checks_outside_checkout(flow_engine,identities,enabled,request,tmp_path,installed_manual):
    import json, os, subprocess, sys
    from hashlib import sha256
    from pathlib import Path
    values,_=approved(flow_engine,identities)
    root=Path(__file__).resolve().parents[2]; hashes={}
    for relative,installed_name in (
        ('packages/returnops_domain/approval_admission.py','returnops_domain/approval_admission.py'),
        ('packages/returnops_domain/approval_admission_sources.py','returnops_domain/approval_admission_sources.py'),
        ('apps/api/returnops_api/private_approval_admission.py','returnops_api/private_approval_admission.py')):
        source=(root/relative).read_bytes(); installed=(installed_manual/installed_name).read_bytes()
        assert source==installed
        hashes[relative]=sha256(installed).hexdigest()
    assert not (installed_manual/'tests').exists() and not (installed_manual/'approval_admission_helpers.py').exists()
    auth=identities.auth_config
    config=dict(arguments=values,schema=flow_engine._customer_test_schema,issuer=auth.issuer,audience=auth.audience,
        signing_key=auth.signing_key.hex(),token=identities.tokens['founder'])
    path=tmp_path/'admission-installed.json'; path.write_text(json.dumps(config),encoding='utf-8')
    before=snapshot(flow_engine)
    process=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).with_name('approval_admission_installed_probe.py')),
        str(path),str(installed_manual)],cwd=tmp_path,env=os.environ.copy(),capture_output=True,timeout=60)
    assert process.returncode==0 and process.stderr==b''
    result=json.loads(process.stdout)
    assert [item['status'] for item in result['results']]==['CHECKED','DENIED','UNKNOWN']
    assert not any(result['effects'].values()) and result['claims']==0
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=result,installed_hashes=hashes,
             installed_outside_checkout=True,isolated_python=True)


# Reuse existing isolated wheel fixture without altering its implementation.
from test_manual_postgresql import installed_manual
