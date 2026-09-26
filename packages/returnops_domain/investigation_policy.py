"""Explicit trusted SERVICE configuration. No request or startup grants access."""
from datetime import datetime, timezone
from sqlalchemy import select, update
from . import investigation_tables as t
from .audit import identifier, timestamp
from .canonical import digest, encode_document, decode_document
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError
from .mock_orders import load_builtin_catalogue
from .wire import validate

SERVICE_ID = 'order-investigation-v1'
ACTOR = {'kind':'SERVICE','component_id':SERVICE_ID}

def service(uow, store):
    return uow.execute(select(t.services).where(t.services.c.store_id==store,t.services.c.service_id==SERVICE_ID)).mappings().one_or_none()

def permission(uow, row):
    return uow.execute(select(t.grants).where(t.grants.c.store_id==row['store_id'],
        t.grants.c.service_id==row['service_id'],t.grants.c.provider_id==row['provider_id'])).mappings().one_or_none()

def signatures(row, grant):
    # SQLAlchemy RowMapping keys are quoted_name subclasses. Project explicit
    # known columns to plain string keys; keep the typed codec strict.
    binding={key:row[key] for key in ('store_id','service_id','provider_id','dataset_version','provider_version','dataset_sha256','enabled','revision')}
    access={'absent':True} if grant is None else {key:grant[key] for key in ('store_id','service_id','provider_id','can_read','revision')}
    return digest(binding,'order-service/v1'),digest(access,'order-grant/v1')

def metadata_matches(row, metadata):
    return all(row[key]==getattr(metadata,key) for key in ('provider_id','dataset_version','provider_version','dataset_sha256'))

class InvestigationPolicy:
    """An internal bootstrap/admin boundary, never registered on the HTTP app."""
    def __init__(self, engine, *, clock=lambda:datetime.now(timezone.utc)):
        self.engine,self.clock=engine,clock

    def _event(self,uow,store,action,values):
        previous=uow.execute(select(t.policy_events).where(t.policy_events.c.store_id==store)
            .order_by(t.policy_events.c.sequence.desc()).limit(1)).mappings().one_or_none()
        sequence=1 if previous is None else previous['sequence']+1
        body={'event_id':identifier('policy'),'store_id':store,'sequence':sequence,'action':action,
            'values':values,'previous_hash':None if previous is None else previous['event_hash'],'at':timestamp(self.clock())}
        uow.execute(t.policy_events.insert().values(event_id=body['event_id'],store_id=store,sequence=sequence,
            event_hash=digest(body,'investigation-policy/v1'),body=encode_document(body)))

    def configure(self,store,*,enabled=True,catalogue=None):
        validate('Id',store)
        if type(enabled) is not bool: raise FlowError('VALIDATION_ERROR')
        metadata=(catalogue or load_builtin_catalogue()).metadata
        with CustomerUnitOfWork(self.engine,write=True) as uow:
            old=service(uow,store)
            values=dict(store_id=store,service_id=SERVICE_ID,provider_id=metadata.provider_id,
                dataset_version=metadata.dataset_version,provider_version=metadata.provider_version,
                dataset_sha256=metadata.dataset_sha256,enabled=enabled,revision=1 if old is None else old['revision']+1)
            if old is None: uow.execute(t.services.insert().values(**values))
            else: uow.execute(update(t.services).where(t.services.c.store_id==store,t.services.c.service_id==SERVICE_ID).values(**values))
            self._event(uow,store,'SERVICE_CONFIGURED',values);uow.commit()

    def grant(self,store,provider_id,*,can_read):
        validate('Id',store);validate('Id',provider_id)
        if type(can_read) is not bool: raise FlowError('VALIDATION_ERROR')
        with CustomerUnitOfWork(self.engine,write=True) as uow:
            row=service(uow,store)
            if row is None or row['provider_id']!=provider_id: raise FlowError('INVALID_STATE')
            old=permission(uow,row)
            values=dict(store_id=store,service_id=SERVICE_ID,provider_id=provider_id,
                can_read=can_read,revision=1 if old is None else old['revision']+1)
            if old is None: uow.execute(t.grants.insert().values(**values))
            else: uow.execute(update(t.grants).where(t.grants.c.store_id==store,t.grants.c.service_id==SERVICE_ID,
                t.grants.c.provider_id==provider_id).values(**values))
            self._event(uow,store,'PROVIDER_GRANT_CHANGED',values);uow.commit()

    def resume(self,work_id,*,expected_input_version):
        # Explicit operator action only. A new claim performs all current source,
        # owner/account/catalogue checks; no ESCALATED or removed fact is reopened.
        from . import customer_tables as old
        validate('Id',work_id);validate('Version',expected_input_version)
        with CustomerUnitOfWork(self.engine,write=True) as uow:
            work=uow.execute(select(t.work).where(t.work.c.work_id==work_id)).mappings().one_or_none()
            if work is None: raise FlowError('NOT_FOUND')
            head=uow.execute(select(old.case_heads).where(old.case_heads.c.case_id==work['case_id'])).mappings().one()
            if (work['state']!='PAUSED' or work['safe_reason'] in {'CONTENT_UNAVAILABLE','ALTERNATIVE_PROOF_REQUIRES_VERIFICATION'}
                    or head['status']!='UNDER_INVESTIGATION' or head['input_version']!=expected_input_version
                    or work['input_version']!=expected_input_version): raise FlowError('INVALID_STATE')
            uow.execute(update(t.work).where(t.work.c.work_id==work_id).values(state='PENDING',next_attempt_at=self.clock(),safe_reason=None))
            self._event(uow,work['store_id'],'WORK_RESUMED',{'work_id':work_id,'input_version':expected_input_version});uow.commit()

    def verify(self,store):
        with CustomerUnitOfWork(self.engine,write=False) as uow:
            rows=uow.execute(select(t.policy_events).where(t.policy_events.c.store_id==store).order_by(t.policy_events.c.sequence)).mappings().all()
            previous=None
            for number,row in enumerate(rows,1):
                body=decode_document(row['body'])
                if (body['store_id']!=store or body['event_id']!=row['event_id'] or body['sequence']!=number or row['sequence']!=number
                    or body['previous_hash']!=previous or digest(body,'investigation-policy/v1')!=row['event_hash']): return False
                previous=row['event_hash']
            uow.commit();return True
