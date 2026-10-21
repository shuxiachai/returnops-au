"""P03/P11 exact real0012→0013 and namespace atomicity; no old DB migration."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from threading import Event
from time import monotonic,sleep
import pytest
from sqlalchemy import inspect,text,update
from sqlalchemy.exc import IntegrityError
from returnops_domain import customer_tables as old
from returnops_domain.label_artifact_tables import metadata,artifacts,NAMESPACE_CHECK
from returnops_domain.lifecycle_schema import LABEL,ARTIFACT,version
from conftest import migrate
from label_execution_helpers import ready as label_ready,service as label_service,execute
from label_artifact_helpers import ready,service,complete,rows,snapshot,evidence

def legacy_reserved(evidence_id):
    now=datetime.now(timezone.utc)
    return dict(evidence_id=evidence_id,uploader_id='legacy_customer',store_id='legacy_store',case_id=None,
        filename=b'',description=None,media_type='application/pdf',size_bytes=1,sha256='0'*64,status='STAGED',
        created_at=now,expires_at=now+timedelta(seconds=30),available=False)

@pytest.mark.parametrize('flow_engine',[LABEL],indirect=True)
def test_LA_P03_P11_exact0012_upgrade_preserves_all_business_rows_without_grants(flow_engine,identities,enabled,request):
    args,_=label_ready(flow_engine,identities);assert execute(label_service(flow_engine,identities),args).status=='COMMITTED'
    before=snapshot(flow_engine);migrate(flow_engine,ARTIFACT);migrate(flow_engine,ARTIFACT);after=snapshot(flow_engine)
    assert set(after)-set(before)==set(metadata.tables) and all(after[n]==[] for n in metadata.tables)
    assert {n:v for n,v in before.items() if n!='alembic_version'}=={n:v for n,v in after.items() if n not in {*metadata.tables,'alembic_version'}}
    with flow_engine.connect() as connection:assert version(connection)==ARTIFACT and len(inspect(connection).get_table_names())==61
    evidence(request.node.nodeid,before=before,after=after)

@pytest.mark.parametrize('flow_engine',[LABEL],indirect=True)
def test_LA_P03_reserved_legacy_tombstone_rolls_back_every_DDL(flow_engine,request):
    with flow_engine.begin() as connection:connection.execute(old.evidence.insert().values(**legacy_reserved('glabel_'+'a'*64)))
    before=snapshot(flow_engine)
    with pytest.raises(RuntimeError,match='namespace is occupied'):migrate(flow_engine,ARTIFACT)
    assert snapshot(flow_engine)==before and not set(metadata.tables)&set(inspect(flow_engine).get_table_names())
    assert NAMESPACE_CHECK not in {c['name'] for c in inspect(flow_engine).get_check_constraints('customer_evidence')}
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine))

@pytest.mark.parametrize('flow_engine',[LABEL],indirect=True)
def test_LA_P03_concurrent_reserved_insert_waits_for_namespace_table_lock(flow_engine,request):
    inserted=Event();completed=Event();result={}
    def upgrade():
        inserted.wait(timeout=10)
        try:migrate(flow_engine,ARTIFACT)
        except Exception as error:result['error']=type(error).__name__
        finally:completed.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with flow_engine.begin() as connection:
            pid=connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            connection.execute(old.evidence.insert().values(**legacy_reserved('glabel_'+'b'*64)))
            inserted.set();future=pool.submit(upgrade);deadline=monotonic()+4;waiting=[]
            while not waiting and monotonic()<deadline:
                with flow_engine.connect() as observer:
                    waiting=[dict(r) for r in observer.execute(text("SELECT pid,wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE :holder=ANY(pg_blocking_pids(pid))"),{'holder':pid}).mappings()]
                if not waiting:sleep(.02)
            assert waiting and not completed.is_set()
        future.result(timeout=15)
    assert result=={'error':'RuntimeError'}
    with flow_engine.connect() as connection:assert version(connection)==LABEL
    assert not set(metadata.tables)&set(inspect(flow_engine).get_table_names())
    evidence(request.node.nodeid,holder_pid=pid,actual_waiters=waiting,result=result,after=snapshot(flow_engine))

@pytest.mark.parametrize('fault',['missing_check','nullable','default','extra_index','namespace_missing','claim_fk'])
def test_LA_P03_exact0013_descriptor_rejects_catalog_counterfeits(flow_engine,identities,enabled,request,fault):
    args,_=ready(flow_engine,identities)
    sql={'missing_check':'ALTER TABLE generated_label_artifacts DROP CONSTRAINT ck_larta_evidence_id',
        'nullable':'ALTER TABLE lifecycle_label_artifact_claims ALTER COLUMN claim_hash DROP NOT NULL',
        'default':"ALTER TABLE label_artifact_permissions ALTER COLUMN revision SET DEFAULT 1",
        'extra_index':'CREATE INDEX counterfeit_artifact_index ON generated_label_artifacts (sha256)',
        'namespace_missing':'ALTER TABLE customer_evidence DROP CONSTRAINT '+NAMESPACE_CHECK,
        'claim_fk':'ALTER TABLE generated_label_artifacts DROP CONSTRAINT fk_generated_label_claim'}[fault]
    with flow_engine.begin() as connection:connection.execute(text(sql));assert version(connection) is None
    before=snapshot(flow_engine);result=complete(service(flow_engine,identities),args)
    assert result.status=='DENIED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,before=before,after=snapshot(flow_engine))

def test_LA_P03_DB_namespace_is_disjoint_even_for_tombstones(flow_engine,identities,enabled,request):
    args,_=ready(flow_engine,identities);result=complete(service(flow_engine,identities),args);assert result.status=='COMMITTED'
    before=snapshot(flow_engine)
    with pytest.raises(IntegrityError) as collision:
        with flow_engine.begin() as connection:connection.execute(old.evidence.insert().values(**legacy_reserved(result.label_evidence_id)))
    assert collision.value.orig.diag.constraint_name==NAMESPACE_CHECK
    with pytest.raises(IntegrityError) as invalid:
        with flow_engine.begin() as connection:connection.execute(update(artifacts).values(evidence_id='ordinary_customer_evidence'))
    assert invalid.value.orig.diag.constraint_name=='ck_larta_evidence_id'
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine))
