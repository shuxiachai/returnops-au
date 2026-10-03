"""New interpreter resolves one retained synthetic acceptance; no source staging."""
import json, os, re, sys
from pathlib import Path
from sqlalchemy import create_engine
from returnops_api.settings import require_environment_database
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.lifecycle_events import LifecycleClaim, ProposalAccepted
from returnops_domain.lifecycle_guards import LifecycleGuards
from datetime import datetime,timezone

schema=sys.argv[1]
assert re.fullmatch('customer_test_[0-9a-f]{32}',schema)
raw=os.environ['DATABASE_URL'];require_environment_database(raw)
payload=json.loads(Path(sys.argv[2]).read_text())
event=ProposalAccepted(payload['event_id'],LifecycleClaim(**payload['claim']),payload['record_id'])
engine=create_engine(raw,hide_parameters=True,echo=False,connect_args={'options':'-c search_path='+schema})
try:
    with CustomerUnitOfWork(engine,write=True) as uow:
        result=LifecycleGuards('synthetic_lifecycle_producer').apply(uow,event,datetime.now(timezone.utc));uow.commit()
        assert result['record_id']==event.record_id
        print('PASS original persisted lifecycle acceptance after interpreter restart')
finally:
    engine.dispose()
