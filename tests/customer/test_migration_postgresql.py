"""Migrate a real old0002 dataset in an isolated schema, preserving exact bytes."""
import os,re
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine,select,text,inspect,func
from alembic import command
from alembic.config import Config
from returnops_api.settings import require_environment_database
from returnops_domain import customer_tables as t
from returnops_domain.storage import InitialRecordUnitOfWork,case_records,original_statement_records,original_statement_contents
from returnops_domain.canonical import decode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.audit import verify_chain

def test_upgrade_real_0002_preserves_data_and_records_service_import_only(initial_bundle):
    raw=os.environ['DATABASE_URL'];require_environment_database(raw)
    schema='customer_migration_'+uuid4().hex;assert re.fullmatch(r'customer_migration_[0-9a-f]{32}',schema)
    control=create_engine(raw,hide_parameters=True,echo=False)
    with control.begin() as c:
        assert c.execute(text('SELECT count(*) FROM pg_namespace WHERE nspname=:name'),{'name':schema}).scalar_one()==0
        c.execute(text('CREATE SCHEMA '+schema))
    engine=create_engine(raw,hide_parameters=True,echo=False,connect_args={'options':'-c search_path='+schema})
    config=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'))
    def migrate(target):
        with engine.begin() as c: config.attributes['connection']=c;command.upgrade(config,target)
    try:
        migrate('0002_initial_records')
        with InitialRecordUnitOfWork(engine) as uow:
            uow.repository.insert_initial_record(initial_bundle);uow.commit()
        with engine.connect() as c:
            before={table.name:list(c.execute(select(table)).mappings()) for table in [case_records,original_statement_records,original_statement_contents]}
        migrate('head');migrate('head')
        with engine.connect() as c:
            for table in [case_records,original_statement_records,original_statement_contents]:
                assert list(c.execute(select(table)).mappings())==before[table.name]
            assert c.execute(select(func.count()).select_from(t.case_heads)).scalar_one()==1
            for table in [t.acceptances,t.receipts,t.principals,t.sessions,t.intake_sessions,t.intake_work]:
                assert c.execute(select(func.count()).select_from(table)).scalar_one()==0
            event=decode_document(c.execute(select(t.audit.c.body)).scalar_one())
            assert event['event_type']=='INITIAL_RECORD_IMPORTED'
            assert event['actor']=={'kind':'SERVICE','component_id':'a1_storage_import'}
            history=decode_document(c.execute(select(t.history_contents.c.body)).scalar_one())
            assert history['raw_text']==initial_bundle.content.raw_text
        with CustomerUnitOfWork(engine,write=False) as uow: assert verify_chain(uow,initial_bundle.case.case_id);uow.commit()
    finally:
        engine.dispose()
        with control.begin() as c:c.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        control.dispose()
