from hashlib import sha256
import pytest
from sqlalchemy import inspect, select, text
from returnops_domain import lifecycle_tables as t
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.lifecycle_state import installed
from returnops_domain.audit import identifier
from conftest import migrate


def fingerprints(engine):
    with engine.connect() as connection:
        return {name:sha256(repr(sorted((tuple(row) for row in connection.execute(text('SELECT * FROM "'+name+'"'))),key=repr)).encode('utf-8','surrogatepass')).hexdigest()
                for name in inspect(connection).get_table_names() if name!='alembic_version'}


@pytest.mark.parametrize('flow_engine',['0006_founder_reads'],indirect=True)
def test_upgrade_real_0006_acceptance_to_empty_sidecars_repeat_preserves_every_old_byte(flow_engine,identities,enabled):
    original=identities.flow().create({'original_message':'synthetic before 0007','order_reference':'SYN-1001'},'migration-key',identifier('corr'))
    assert IntakeProcessor(flow_engine).run_once() and InvestigationProcessor(flow_engine).run_once()
    before=fingerprints(flow_engine)
    migrate(flow_engine);migrate(flow_engine)
    after=fingerprints(flow_engine)
    assert {name:value for name,value in after.items() if name not in t.metadata.tables}==before
    assert set(after)-set(before)==set(t.metadata.tables)
    with flow_engine.connect() as connection:
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0008_review_escalation'
        assert all(connection.execute(select(table)).first() is None for table in t.metadata.tables.values())
    assert identities.flow().create({'original_message':'synthetic before 0007','order_reference':'SYN-1001'},'migration-key',identifier('corr')).body==original.body


@pytest.mark.parametrize('flow_engine',['0006_founder_reads','head'],indirect=True)
def test_partial_or_corrupt_migration_never_silently_disables_guard(flow_engine):
    with flow_engine.begin() as connection:
        names=inspect(connection).get_table_names()
        if 'lifecycle_authorities' in names:
            connection.execute(text('DROP TABLE lifecycle_authorities'))
        else:
            t.authorities.create(connection)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError): installed(uow)
        with pytest.raises(FlowError): uow.commit()
