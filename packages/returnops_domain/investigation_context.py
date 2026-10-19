"""Current SERVICE authority, resolved on the caller's fenced DB connection."""
from dataclasses import dataclass
from sqlalchemy import select
from . import customer_tables as old, investigation_tables as t
from .canonical import decode_document
from .errors import FlowError
from .intake_processor import IntakeProcessor
from .investigation_policy import SERVICE_ID, service, permission, signatures, metadata_matches
from .order_ports import OrderReadContext, OrderLookupError

@dataclass(frozen=True, slots=True, repr=False)
class InvestigationClaim:
    work_id: str
    claim_id: str
    invocation_id: str
    epoch: int
    case_version: int
    input_version: int
    service_signature: str
    grant_signature: str


def context(uow, work, metadata):
    state=uow.execute(select(t.state).where(t.state.c.case_id==work['case_id'])).mappings().one_or_none()
    head=uow.execute(select(old.case_heads).where(old.case_heads.c.case_id==work['case_id'])).mappings().one_or_none()
    if (state is None or head is None or state['current_work_id']!=work['work_id']
            or head['input_version']!=work['input_version'] or head['status']!='UNDER_INVESTIGATION'):
        return 'STALE_INPUT',None
    if head['owner_principal_id']!=work['owner_id'] or head['store_id']!=work['store_id']:
        return 'AUTHORITY_UNAVAILABLE',None
    policy=service(uow,work['store_id'])
    if policy is None or not policy['enabled']: return 'SERVICE_DISABLED',None
    if not metadata_matches(policy,metadata) or work['service_id']!=SERVICE_ID: return 'CONFIGURATION_CHANGED',None
    intake=uow.execute(select(old.intake_work).where(old.intake_work.c.work_id==work['intake_work_id'])).mappings().one_or_none()
    if intake is None or intake['state']!='DONE' or intake['acceptance_id']!=work['acceptance_id']:
        return 'CONTENT_UNAVAILABLE',None
    principal=uow.execute(select(old.principals).where(old.principals.c.principal_id==work['owner_id'])).mappings().one_or_none()
    if principal is None or not principal['enabled'] or principal['role']!='CUSTOMER' or principal['store_id']!=work['store_id']:
        return 'AUTHORITY_UNAVAILABLE',None
    # This reuses only the existing pure connection-level source checks. There
    # is no nested UoW, HTTP credential reuse, processor call or database write.
    validator=IntakeProcessor(None)
    current,material=validator._context(uow,intake)
    if current!='CURRENT': return 'CONTENT_UNAVAILABLE',None
    input_row=uow.execute(select(t.inputs).where(t.inputs.c.work_id==work['work_id'])).mappings().one_or_none()
    if input_row is None or not input_row['available']: return 'CONTENT_UNAVAILABLE',None
    if input_row['alternative']: return 'ALTERNATIVE_PROOF_REQUIRES_VERIFICATION',None
    grant=permission(uow,policy)
    return None,(head,policy,grant,input_row,signatures(policy,grant))


def claimed(work, claim, now):
    return (work is not None and work['state']=='RUNNING' and work['claim_id']==claim.claim_id
        and work['invocation_id']==claim.invocation_id and work['epoch']==claim.epoch
        and work['claimed_case_version']==claim.case_version and work['input_version']==claim.input_version
        and work['service_signature']==claim.service_signature and work['grant_signature']==claim.grant_signature
        and work['lease_expires_at']>now)

class DatabaseOrderResolver:
    def __init__(self,uow,claim,metadata,clock):
        self.uow,self.claim,self.metadata,self.clock=uow,claim,metadata,clock

    def resolve(self,case_id,input_version):
        work=self.uow.execute(select(t.work).where(t.work.c.work_id==self.claim.work_id)).mappings().one_or_none()
        if not claimed(work,self.claim,self.clock()): raise OrderLookupError('STALE_INPUT')
        reason,current=context(self.uow,work,self.metadata)
        if reason is not None: raise OrderLookupError('CASE_ACCESS_DENIED')
        head,policy,grant,material,signature=current
        if (head['case_id']!=case_id or head['input_version']!=input_version or head['case_version']!=self.claim.case_version
                or signature!=(self.claim.service_signature,self.claim.grant_signature)):
            raise OrderLookupError('STALE_INPUT')
        return OrderReadContext(case_id,input_version,head['store_id'],head['owner_principal_id'],SERVICE_ID,
            policy['provider_id'],False if grant is None else grant['can_read'])
