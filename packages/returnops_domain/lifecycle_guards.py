"""A1.03 persisted event consumer; fixed proposals opt in through A1.05.

Only IDs/expected versions enter this gate. Source bodies and targets are read
from the same fenced transaction. Tests provide explicitly synthetic producers;
no decision, Risk PASS, approval, provider dispatch or message send is produced.
"""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from . import customer_tables as old, lifecycle_tables as t
from .audit import append_event, identifier
from .canonical import digest
from .errors import FlowError
from .lifecycle_events import (LifecycleClaim, ProposalAccepted, ProposalFailed, RevisionRequested,
    OutcomeAccepted, NotificationObserved, EffectObserved)
from .lifecycle_sources import Sources, authority
from .lifecycle_state import current, installed, invalidate, reject, MAX_VERSION

PURPOSES = {ProposalAccepted: 'PROPOSAL', ProposalFailed: 'PROPOSAL', RevisionRequested: 'REVISION',
            OutcomeAccepted: 'OUTCOME', NotificationObserved: 'NOTIFICATION', EffectObserved: 'EFFECT'}
TERMINAL = {'COMPLETED', 'REJECTED', 'MANUAL_HANDLED'}
REVISION_STATES = {'RISK_REVIEW', 'AWAITING_APPROVAL', 'ESCALATED'}
DECISION_STATES = {'AWAITING_APPROVAL', 'ESCALATED'}


def target(head, state, purpose, target_record_id=None):
    fields = ('proposal_record_id', 'review_record_id', 'approval_record_id')
    if purpose == 'NOTIFICATION':
        fields = ('outcome_record_id', 'outcome', 'notification_id', 'notification_hash')
    return digest({'case_id': head['case_id'], 'input_version': head['input_version'],
        'generation': state['generation'], 'purpose': purpose, 'target_record_id':target_record_id,
        'refs': {name: state[name] for name in fields}}, 'lifecycle-target/v1')


def notification_hash(body):
    return digest({name: body[name] for name in ('case_id','notification_id','outcome','message','next_steps')},
                  'lifecycle-notification/v1')


class LifecycleGuards:
    def __init__(self, component_id, *, clock=lambda:datetime.now(timezone.utc)):
        self.component_id = component_id
        self.clock = clock

    def _load(self, uow, case_id, purpose):
        if not uow.write or not installed(uow):
            reject(uow)
        head = uow.execute(select(old.case_heads).where(old.case_heads.c.case_id == case_id).with_for_update()).mappings().one_or_none()
        if head is None or not head['available']:
            reject(uow, 'NOT_FOUND')
        grant = authority(uow, head, self.component_id, purpose)
        return head, current(uow, head, initialize=True), grant

    def prepare(self, uow, case_id, expected_case_version, event_type, now, *, target_record_id=None, work_id=None):
        """Register metadata for one exact target; never runs its future producer."""
        try:
            purpose = PURPOSES.get(event_type)
            head, state, grant = self._load(uow, case_id, purpose)
            if purpose is None or head['case_version'] != expected_case_version:
                reject(uow, 'STALE_CASE_VERSION')
            self._allowed(uow, head, state, purpose)
            if purpose == 'EFFECT':
                Sources(uow,head,self.component_id).read(target_record_id,{'OPERATION'},current_actor=False)
            elif target_record_id is not None:
                reject(uow)
            fingerprint = target(head, state, purpose, target_record_id)
            if work_id is not None:
                from .wire import validate
                validate('Id', work_id)
            existing = uow.execute(select(t.work).where(t.work.c.case_id == case_id,
                t.work.c.purpose == purpose, t.work.c.generation == state['generation'],
                t.work.c.target_hash == fingerprint)).mappings().one_or_none()
            if existing is not None:
                if existing['component_id'] != self.component_id:
                    reject(uow, 'FORBIDDEN')
                if work_id is not None and (existing['work_id'] != work_id
                        or existing['store_id'] != head['store_id']
                        or existing['owner_id'] != head['owner_principal_id']
                        or existing['input_version'] != head['input_version']
                        or existing['target_record_id'] != target_record_id):
                    reject(uow, 'IDEMPOTENCY_CONFLICT')
                return existing['work_id']
            if purpose=='NOTIFICATION':
                # The accepted outcome owns its work identity from its original
                # transaction. Recovery must never invent a replacement intent.
                reject(uow)
            if work_id is not None and uow.execute(select(t.work.c.work_id).where(t.work.c.work_id == work_id)).first():
                reject(uow, 'IDEMPOTENCY_CONFLICT')
            work_id = work_id or identifier('lifecycle_work')
            uow.execute(t.work.insert().values(work_id=work_id,case_id=case_id,component_id=self.component_id,
                store_id=head['store_id'],owner_id=head['owner_principal_id'],purpose=purpose,
                input_version=head['input_version'],generation=state['generation'],target_hash=fingerprint,target_record_id=target_record_id,
                state='PENDING',claim_id=None,epoch=0,claimed_case_version=None,authority_revision=grant['revision'],
                lease_expires_at=None,created_at=now))
            return work_id
        except FlowError:
            uow.poison()
            raise
        except Exception:
            uow.poison()
        raise FlowError('INVALID_STATE') from None

    @staticmethod
    def _allowed(uow, head, state, purpose):
        if not state['available']:
            reject(uow)
        allowed = ((purpose == 'PROPOSAL' and head['status'] == 'POLICY_ASSESSMENT' and state['outcome'] is None)
            or (purpose == 'REVISION' and head['status'] in REVISION_STATES and state['proposal_record_id'] is not None and state['outcome'] is None)
            or (purpose == 'OUTCOME' and head['status'] in DECISION_STATES | {'ACTION_IN_PROGRESS','RECONCILING'} and state['outcome'] is None)
            or (purpose == 'NOTIFICATION' and head['status'] in {'NOTIFICATION_PENDING','NOTIFICATION_FAILED'} and state['outcome'] is not None)
            or purpose == 'EFFECT')
        if not allowed:
            reject(uow)

    def claim(self, uow, work_id, now, *, lease_seconds=60):
        try:
            if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
                reject(uow)
            work = uow.execute(select(t.work).where(t.work.c.work_id == work_id)).mappings().one_or_none()
            if work is None:
                reject(uow)
            head, state, grant = self._load(uow, work['case_id'], work['purpose'])
            self._work_context(uow, head, state, grant, work)
            if work['state'] == 'RUNNING' and work['lease_expires_at'] > now:
                return None
            if work['state'] not in {'PENDING','RUNNING'} or work['epoch'] >= MAX_VERSION:
                reject(uow)
            self._allowed(uow, head, state, work['purpose'])
            claim = LifecycleClaim(work_id,identifier('lifecycle_claim'),work['epoch']+1,
                head['case_version'],work['input_version'],work['generation'],grant['revision'])
            uow.execute(update(t.work).where(t.work.c.work_id == work_id).values(state='RUNNING',
                claim_id=claim.claim_id,epoch=claim.epoch,claimed_case_version=claim.case_version,
                authority_revision=claim.authority_revision,lease_expires_at=now+timedelta(seconds=lease_seconds)))
            return claim
        except FlowError:
            uow.poison()
            raise
        except Exception:
            uow.poison()
        raise FlowError('INVALID_STATE') from None

    def _work_context(self, uow, head, state, grant, work):
        if (work['component_id'] != self.component_id or work['store_id'] != head['store_id']
                or work['owner_id'] != head['owner_principal_id']
                or work['epoch']>0 and work['authority_revision'] != grant['revision']):
            reject(uow, 'FORBIDDEN')
        if work['purpose']=='NOTIFICATION' and state['notification_work_id']!=work['work_id']:
            reject(uow)
        if work['purpose'] != 'EFFECT' and (work['input_version'] != head['input_version']
                or work['generation'] != state['generation'] or work['target_hash'] != target(head,state,work['purpose'])):
            reject(uow)

    def apply(self, uow, event, now):
        """Accept one persisted source, or resolve its exact original acceptance.

        The caller commits. A caught rejection still poisons the whole UoW,
        including producer rows already staged on this connection.
        """
        try:
            purpose = PURPOSES.get(type(event))
            if purpose is None or type(event.claim) is not LifecycleClaim:
                reject(uow)
            claim = event.claim
            work = uow.execute(select(t.work).where(t.work.c.work_id == claim.work_id)).mappings().one_or_none()
            if work is None or work['purpose'] != purpose:
                reject(uow)
            head, state, grant = self._load(uow, work['case_id'], purpose)
            event_kind = 'PROPOSAL_FAILED' if type(event) is ProposalFailed else purpose
            fingerprint = digest({'kind':event_kind, **asdict(event)}, 'lifecycle-event/v1')
            accepted = uow.execute(select(t.events).where(t.events.c.record_id == event.record_id)).mappings().one_or_none()
            if accepted is not None:
                if (accepted['fingerprint'] != fingerprint or accepted['event_kind'] != event_kind or accepted['event_id'] != event.event_id
                        or accepted['case_id'] != head['case_id'] or work['component_id'] != self.component_id):
                    reject(uow, 'IDEMPOTENCY_CONFLICT')
                from .founder_integrity import CaseProof, read_revision
                proof = CaseProof(uow,head)
                original = proof.revisions.get(event.record_id)
                if (original is None or original['content_sha256'] != accepted['source_hash']
                        or proof.origin(original)['event_id'] != accepted['source_audit_event_id']):
                    reject(uow)
                read_revision(uow,original,proof)
                uow.before_commit(lambda: authority(uow,head,self.component_id,purpose))
                return dict(accepted)
            if uow.execute(select(t.events.c.event_id).where(t.events.c.event_id == event.event_id)).first():
                reject(uow, 'IDEMPOTENCY_CONFLICT')
            self._work_context(uow,head,state,grant,work)
            if (work['state'] != 'RUNNING' or work['claim_id'] != claim.claim_id or work['epoch'] != claim.epoch
                    or work['claimed_case_version'] != claim.case_version or work['input_version'] != claim.input_version
                    or work['generation'] != claim.generation or grant['revision'] != claim.authority_revision
                    or work['lease_expires_at'] <= now):
                reject(uow)
            if purpose not in {'NOTIFICATION','EFFECT'} and head['case_version'] != claim.case_version:
                reject(uow, 'STALE_CASE_VERSION')
            self._allowed(uow,head,state,purpose)
            sources = Sources(uow,head,self.component_id)
            failure_id = None
            if type(event) is ProposalFailed:
                row, body, binding = sources.bound(event.record_id,work,claim,{'PROCESSING_FAILURE'})
                self._proposal_failed(uow, head, state, work, row, body)
                failure_id = row['object_id']
                new_status = 'ESCALATED'
            elif purpose == 'PROPOSAL':
                row, body, binding = sources.bound(event.record_id,work,claim,{'PROPOSAL'})
                new_status = self._proposal(uow,head,state,sources,row,body,binding)
            elif purpose == 'REVISION':
                row, body, binding = sources.bound(event.record_id,work,claim,{'REVIEW','DECISION'})
                new_status = self._revision(uow,head,state,sources,row,body,event)
            elif purpose == 'OUTCOME':
                row, body, binding = sources.bound(event.record_id,work,claim,{'DECISION','NOTIFICATION'})
                new_status = self._outcome(uow,head,state,sources,event,row,body,work,claim)
            elif purpose == 'NOTIFICATION':
                row, body, binding = sources.bound(event.record_id,work,claim,{'NOTIFICATION'})
                if binding['target_record_id'] != state['outcome_record_id']:
                    reject(uow)
                new_status = self._notification(uow,head,state,sources,row,body)
            else:
                row, body, binding = sources.bound(event.record_id,work,claim,{'OPERATION'})
                self._effect(uow,head,state,sources,row,body,binding,work)
                new_status = head['status']
            if head['case_version'] >= MAX_VERSION:
                reject(uow)
            head_values = dict(status=new_status, case_version=head['case_version']+1, updated_at=now)
            if failure_id is not None:
                head_values['current_failure_id'] = failure_id
            changed = uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == head['case_id'],
                old.case_heads.c.case_version == head['case_version']).values(**head_values))
            if changed.rowcount != 1:
                reject(uow,'STALE_CASE_VERSION')
            after = uow.execute(select(t.state).where(t.state.c.case_id == head['case_id'])).mappings().one()
            if purpose=='OUTCOME':
                work_id=identifier('notification_work')
                uow.execute(t.work.insert().values(work_id=work_id,case_id=head['case_id'],component_id=self.component_id,
                    store_id=head['store_id'],owner_id=head['owner_principal_id'],purpose='NOTIFICATION',
                    input_version=head['input_version'],generation=after['generation'],
                    target_hash=target(head,after,'NOTIFICATION'),target_record_id=None,state='PENDING',
                    claim_id=None,epoch=0,claimed_case_version=None,authority_revision=None,
                    idempotency_key=identifier('notification_key'),lease_expires_at=None,created_at=now))
                uow.execute(update(t.state).where(t.state.c.case_id==head['case_id']).values(notification_work_id=work_id))
                after=uow.execute(select(t.state).where(t.state.c.case_id==head['case_id'])).mappings().one()
            receipt = dict(event_id=event.event_id,case_id=head['case_id'],work_id=work['work_id'],record_id=row['record_id'],
                fingerprint=fingerprint,event_kind=event_kind,source_id=row['record_id'],
                source_hash=row['content_sha256'],source_audit_event_id=sources.proof.origin(row)['event_id'],
                pre_case_version=head['case_version'],pre_input_version=head['input_version'],pre_generation=state['generation'],
                case_version=head['case_version']+1,input_version=head['input_version'],
                generation=after['generation'],status=new_status,accepted_at=now)
            uow.execute(t.events.insert().values(**receipt))
            # Notification retry keeps exactly the same work/notification/key;
            # epoch is a lease generation, not a delivery attempt count.
            retry = ((purpose == 'NOTIFICATION' and body['status'] != 'SENT')
                     or (purpose == 'EFFECT' and body['status'] not in {'SUCCEEDED','FAILED','BLOCKED'}))
            uow.execute(update(t.work).where(t.work.c.work_id == work['work_id']).values(
                state='PENDING' if retry else 'DONE',lease_expires_at=None))
            append_event(uow,head['case_id'],actor={'kind':'SERVICE','component_id':self.component_id},
                event_type='LIFECYCLE_EVENT_ACCEPTED',correlation_id=event.event_id,
                payload={'event':event_kind,'work_id':work['work_id'],'source_record_id':row['record_id'],'generation':after['generation']},
                object_ids=[row['object_id'],work['work_id']],history_refs=[],now=now)
            sealed_work = dict(uow.execute(select(t.work).where(t.work.c.work_id == work['work_id'])).mappings().one())
            sealed_sources = [dict(item) for item in uow.execute(select(t.sources).where(
                t.sources.c.work_id == work['work_id'],t.sources.c.epoch == claim.epoch)
                .order_by(t.sources.c.slot)).mappings()]
            sealed_notification = (dict(uow.execute(select(t.work).where(
                t.work.c.work_id==after['notification_work_id'])).mappings().one()) if purpose=='OUTCOME' else None)
            uow.before_commit(lambda: self._before_commit(uow,work,claim,receipt,work['lease_expires_at'],
                sealed_work,dict(after),sealed_sources,sealed_notification))
            return receipt
        except FlowError:
            uow.poison()
            raise
        except Exception:
            uow.poison()
        raise FlowError('INVALID_STATE') from None

    def _before_commit(self, uow, work, claim, receipt, lease, sealed_work, sealed_state, sealed_sources, sealed_notification):
        h,state,grant = self._load(uow,work['case_id'],work['purpose'])
        actual_work = uow.execute(select(t.work).where(t.work.c.work_id == work['work_id'])).mappings().one_or_none()
        actual_sources = [dict(item) for item in uow.execute(select(t.sources).where(
            t.sources.c.work_id == work['work_id'],t.sources.c.epoch == claim.epoch).order_by(t.sources.c.slot)).mappings()]
        if (self.clock() >= lease or grant['revision'] != claim.authority_revision
                or h['case_version'] != receipt['case_version'] or h['input_version'] != receipt['input_version']
                or dict(state) != sealed_state or actual_work is None or dict(actual_work) != sealed_work
                or actual_work['claim_id']!=claim.claim_id or actual_work['epoch']!=claim.epoch
                or actual_work['generation']!=receipt['pre_generation'] or actual_work['input_version']!=claim.input_version
                or actual_sources != sealed_sources or not state['available']):
            reject(uow)
        if sealed_notification is not None:
            intended=uow.execute(select(t.work).where(t.work.c.work_id==state['notification_work_id'])).mappings().one_or_none()
            if intended is None or dict(intended)!=sealed_notification:
                reject(uow)
        sources = Sources(uow,h,self.component_id)
        source = sources.proof.revisions.get(receipt['record_id'])
        if source is None or source['content_sha256'] != receipt['source_hash']:
            reject(uow)
        for binding in sealed_sources:
            saved = sources.proof.revisions.get(binding['record_id'])
            if saved is None or saved['content_sha256'] != binding['source_hash']:
                reject(uow)
            sources.read(binding['record_id'],{saved['kind']})
        if receipt['event_kind']=='PROPOSAL_FAILED':
            _,failure=sources.read(receipt['record_id'],{'PROCESSING_FAILURE'})
            if h['status'] != 'ESCALATED' or h['current_failure_id'] != failure['failure_id']:
                reject(uow)
            self._failure_content(uow,h,state,work,source,failure)
        elif work['purpose']=='PROPOSAL':
            from .lifecycle_proposal import verify
            _,bundle=sources.read(receipt['record_id'],{'PROPOSAL'})
            primary=next(item for item in sealed_sources if item['slot']=='PRIMARY')
            verify(uow,h,sources,bundle,primary['order_projection_id'])
        if state['outcome'] == 'RETURN_CREATED' and work['purpose'] in {'OUTCOME','NOTIFICATION'}:
            self._return_sources(uow,h,state,sources,state['return_record_id'],state['label_record_id'])
        elif work['purpose'] == 'EFFECT':
            from .lifecycle_effects import original_dispatch
            _,body = sources.read(receipt['record_id'],{'OPERATION'})
            binding = next(item for item in sealed_sources if item['slot']=='PRIMARY')
            original_dispatch(uow,sources,work,body,binding)
            if body['status']=='SUCCEEDED' and body['result']['type']=='GENERATE_LABEL':
                self._label(uow,h,body['result']['label_evidence_id'],binding['artifact_sha256'])
        # Provenance/PDF validation may take time. The final time sample belongs
        # after that work, immediately before this UoW attempts its commit.
        if self.clock() >= lease:
            reject(uow)

    @staticmethod
    def _failure_content(uow, head, state, work, row, body):
        from . import investigation_tables as investigation
        from .canonical import decode_document
        from .proposal_policy import COMPONENT
        from .proposal_sources import read_material
        from .fixed_proposal import build_fixed_proposal, ProposalCapacityError, CAPACITY_MESSAGE
        from .audit import timestamp
        failure = uow.execute(select(old.processing_failures).where(
            old.processing_failures.c.failure_id == row['object_id'])).mappings().one_or_none()
        block = uow.execute(select(investigation.state.c.current_block_id).where(
            investigation.state.c.case_id == head['case_id'])).scalar_one_or_none()
        binding = uow.execute(select(t.sources).where(t.sources.c.record_id == row['record_id'])).mappings().one_or_none()
        origin = Sources(uow,head,COMPONENT).proof.origin(row)
        error = body['error']['error']
        if (work['component_id'] != COMPONENT or row['object_version'] != 1
                or any(state[name] is not None for name in ('proposal_record_id','review_record_id',
                    'preview_id','approval_record_id','outcome_record_id','outcome'))
                or block is not None or failure is None or binding is None
                or origin['event_type'] != 'FIXED_PROPOSAL_FAILED'
                or origin['actor'] != {'kind':'SERVICE','component_id':COMPONENT}
                or body['case_id'] != head['case_id']
                or body['input_version'] != head['input_version'] or body['stage'] != 'ASSESSMENT'
                or error['code'] != 'REQUEST_TOO_LARGE' or error['retryable'] is not False
                or error['message'] != CAPACITY_MESSAGE or error['details'] != []
                or failure['case_id'] != head['case_id'] or failure['input_version'] != head['input_version']
                or decode_document(failure['body']) != body
                or timestamp(failure['occurred_at']) != body['occurred_at']
                or body['occurred_at'] != timestamp(row['recorded_at'])):
            reject(uow)
        capacity = False
        material = read_material(uow,head)
        if binding['order_projection_id'] != material.projection_id:
            reject(uow)
        try:
            build_fixed_proposal(material,work,state['proposal_version']+1,row['recorded_at'])
        except ProposalCapacityError:
            capacity = True
        if not capacity:
            reject(uow)

    def _proposal_failed(self, uow, head, state, work, row, body):
        if self.component_id != work['component_id'] or head['status'] != 'POLICY_ASSESSMENT' or head['current_failure_id'] is not None:
            reject(uow)
        self._failure_content(uow,head,state,work,row,body)

    @staticmethod
    def _proposal(uow, head, state, sources, row, bundle, binding):
        from .lifecycle_proposal import verify
        verify(uow,head,sources,bundle,binding['order_projection_id'])
        packet = bundle['packet']
        if (packet['input_version'] != head['input_version'] or row['case_version'] != head['case_version']
                or packet['proposal_version'] != state['proposal_version'] + 1):
            reject(uow)
        uow.execute(update(t.state).where(t.state.c.case_id == head['case_id']).values(
            proposal_record_id=row['record_id'],proposal_version=packet['proposal_version'],
            review_record_id=None,preview_id=None,approval_record_id=None))
        return 'RISK_REVIEW'

    @staticmethod
    def _current_proposal(uow, head, state, sources):
        if state['proposal_record_id'] is None:
            reject(uow)
        row, bundle = sources.read(state['proposal_record_id'],{'PROPOSAL'},current_actor=False)
        packet = bundle['packet']
        accepted = uow.execute(select(t.events).where(t.events.c.record_id == row['record_id'],
            t.events.c.event_kind == 'PROPOSAL')).mappings().one_or_none()
        binding=uow.execute(select(t.sources).where(t.sources.c.record_id==row['record_id'])).mappings().one_or_none()
        from . import investigation_tables as investigation
        projection=uow.execute(select(investigation.state.c.current_projection_id).where(
            investigation.state.c.case_id==head['case_id'])).scalar_one_or_none()
        if (accepted is None or accepted['generation'] != state['generation']
                or binding is None or binding['order_projection_id'] is None or binding['order_projection_id']!=projection
                or accepted['source_hash'] != row['content_sha256']
                or packet['input_version'] != head['input_version'] or packet['proposal_version'] != state['proposal_version']):
            reject(uow)
        return row, packet

    def _revision(self, uow, head, state, sources, row, body, event):
        proposal, packet = self._current_proposal(uow,head,state,sources)
        if row['kind'] == 'REVIEW':
            value = body['review']
            if (head['status'] != 'RISK_REVIEW' or body['proposal_record_id'] != proposal['record_id']
                    or value['outcome'] != 'REVISE' or value['input_version'] != head['input_version']):
                reject(uow)
        else:
            value = body
            if value['decision'] != 'REQUEST_REVISION' or head['status'] not in {'AWAITING_APPROVAL','ESCALATED'}:
                reject(uow)
        if any(value.get(name) != packet[name] for name in ('proposal_id','proposal_version')):
            reject(uow)
        invalidate(uow,head,accepting_event=event)
        return 'POLICY_ASSESSMENT'

    def _decision_target(self, uow, head, state, sources, body):
        if 'proposal_id' in body:
            _, packet = self._current_proposal(uow,head,state,sources)
            if any(body[name] != packet[name] for name in ('proposal_id','proposal_version')):
                reject(uow)
            if body['decision'] not in {'REJECT','MANUAL_HANDLING'}:
                reject(uow)
            if (body['decision']=='REJECT' and head['status']!='AWAITING_APPROVAL'
                    or body['decision']=='MANUAL_HANDLING' and head['status'] not in DECISION_STATES):
                reject(uow)
            return 'REJECTED' if body['decision'] == 'REJECT' else 'MANUAL_HANDLED'
        if head['status'] != 'ESCALATED' or state['proposal_record_id'] is not None or body['decision'] != 'MANUAL_HANDLING':
            reject(uow)
        from . import investigation_tables as investigation
        if 'processing_failure_id' in body:
            object_id = head['current_failure_id']
            kind = 'PROCESSING_FAILURE'
            if body['processing_failure_id'] != object_id:
                reject(uow)
        else:
            lookup = uow.execute(select(investigation.state).where(investigation.state.c.case_id == head['case_id'])).mappings().one_or_none()
            object_id = None if lookup is None else lookup['current_block_id']
            kind = 'ORDER_LOOKUP_BLOCK'
            if body.get('order_lookup_block_id') != object_id or object_id is None:
                reject(uow)
        matches = [r for r in sources.proof.revisions.values() if r['kind'] == kind and r['object_id'] == object_id]
        if len(matches) != 1:
            reject(uow)
        _, saved = sources.read(matches[0]['record_id'],{kind},current_actor=False)
        saved = saved['block'] if kind == 'ORDER_LOOKUP_BLOCK' else saved
        if saved['input_version'] != head['input_version']:
            reject(uow)
        return 'MANUAL_HANDLED'

    def _outcome(self, uow, head, state, sources, event, row, body, work, claim):
        if row['kind'] == 'DECISION':
            outcome = self._decision_target(uow,head,state,sources,body)
            if event.return_record_id is not None or event.label_record_id is not None:
                reject(uow)
        else:
            if head['status'] not in {'ACTION_IN_PROGRESS','RECONCILING'} or event.record_id != event.notification_record_id:
                reject(uow)
            self._return_sources(uow,head,state,sources,event.return_record_id,event.label_record_id)
            outcome = 'RETURN_CREATED'
        notification_row, notification, binding = sources.bound(event.notification_record_id,work,claim,{'NOTIFICATION'},
            slot='PRIMARY' if row['kind'] == 'NOTIFICATION' else 'NOTIFICATION')
        if (notification['status'] != 'PENDING' or notification['outcome'] != outcome
                or binding['target_record_id'] != row['record_id']
                or notification['case_version'] != head['case_version']
                or notification_row['case_version'] != head['case_version']):
            reject(uow)
        uow.execute(update(t.state).where(t.state.c.case_id == head['case_id']).values(
            outcome_record_id=row['record_id'],outcome=outcome,notification_id=notification['notification_id'],
            notification_record_id=notification_row['record_id'],notification_hash=notification_hash(notification),
            return_record_id=event.return_record_id,label_record_id=event.label_record_id,
            approval_record_id=state['approval_record_id'] if outcome == 'RETURN_CREATED' else None))
        return 'NOTIFICATION_PENDING'

    def _notification(self, uow, head, state, sources, row, body):
        old_row, previous = sources.read(state['notification_record_id'],{'NOTIFICATION'},current_actor=False)
        if (body['notification_id'] != state['notification_id'] or body['outcome'] != state['outcome']
                or notification_hash(body) != state['notification_hash'] or row['object_version'] != old_row['object_version']+1
                or body['attempt_count'] < previous['attempt_count'] or previous['status'] == 'SENT'):
            reject(uow)
        if head['status']=='NOTIFICATION_FAILED' and body['status']!='PENDING':
            reject(uow)
        if state['outcome'] == 'RETURN_CREATED':
            self._return_sources(uow,head,state,sources,state['return_record_id'],state['label_record_id'])
        uow.execute(update(t.state).where(t.state.c.case_id == head['case_id']).values(notification_record_id=row['record_id']))
        if body['status'] == 'SENT':
            return {'RETURN_CREATED':'COMPLETED','REJECTED':'REJECTED','MANUAL_HANDLED':'MANUAL_HANDLED'}[state['outcome']]
        return 'NOTIFICATION_FAILED' if body['status'] == 'FAILED' else 'NOTIFICATION_PENDING'

    def _effect(self, uow, head, state, sources, row, body, binding, work):
        from .lifecycle_effects import original_dispatch, fingerprint
        dispatch, approval_row, approval = original_dispatch(uow,sources,work,body,binding)
        scope = approval['scope']
        commands = [command for command in scope['commands'] if command['command_id'] == body['command_id']]
        if (len(commands) != 1 or body['approval_id'] != approval['approval_id']
                or any(body[name] != scope[name] for name in ('case_id','input_version','proposal_id','proposal_version'))):
            reject(uow)
        command = commands[0]
        expected_fingerprint = fingerprint({'approval_id':approval['approval_id'],
            'scope_fingerprint':approval['scope_fingerprint'],'command':command})
        if (body['provider_id'] != command['provider_id'] or body['operation_fingerprint'] != expected_fingerprint
                or binding['target_record_id'] != approval_row['record_id']
                or body.get('provider_operation_id') != binding['provider_operation_id']):
            reject(uow)
        if body['status'] == 'SUCCEEDED':
            result = body['result']
            if result['type'] != command['type'] or result['parcel_id'] != scope['parcel_id']:
                reject(uow)
            if result['type'] == 'GENERATE_LABEL':
                if (binding['artifact_evidence_id'] != result['label_evidence_id']
                        or dispatch['artifact_evidence_id'] != binding['artifact_evidence_id']
                        or dispatch['artifact_sha256'] != binding['artifact_sha256']):
                    reject(uow)
                self._label(uow,head,result['label_evidence_id'],binding['artifact_sha256'])
        identity = digest({name:body[name] for name in ('operation_id','case_id','command_id','approval_id',
            'proposal_id','proposal_version','input_version','provider_id','operation_fingerprint','idempotency_key')},'lifecycle-effect/v1')
        previous = uow.execute(select(t.effects).where(t.effects.c.operation_id == body['operation_id'])).mappings().one_or_none()
        if previous is not None and (previous['identity_hash'] != identity
                or row['object_version'] != previous['object_version']+1 or previous['status'] in {'SUCCEEDED','FAILED','BLOCKED'}):
            reject(uow)
        values = dict(operation_id=body['operation_id'],case_id=head['case_id'],record_id=row['record_id'],
            object_version=row['object_version'],approval_record_id=approval_row['record_id'],command_id=body['command_id'],
            input_version=body['input_version'],generation=dispatch['generation'],operation_type=command['type'],
            status=body['status'],identity_hash=identity,artifact_evidence_id=binding['artifact_evidence_id'],
            artifact_sha256=binding['artifact_sha256'],dispatch_source_record_id=binding['dispatch_source_record_id'])
        if previous is None:
            uow.execute(t.effects.insert().values(**values))
        else:
            uow.execute(update(t.effects).where(t.effects.c.operation_id == body['operation_id']).values(**values))

    @staticmethod
    def _label(uow, head, evidence_id, expected_hash):
        evidence = uow.execute(select(old.evidence).where(old.evidence.c.evidence_id == evidence_id)).mappings().one_or_none()
        raw = uow.execute(select(old.evidence_contents.c.body).where(old.evidence_contents.c.evidence_id == evidence_id)).scalar_one_or_none()
        if (evidence is None or not evidence['available'] or evidence['status'] != 'BOUND'
                or evidence['case_id'] != head['case_id'] or evidence['store_id'] != head['store_id'] or raw is None
                or evidence['sha256'] != expected_hash or evidence['media_type'] != 'application/pdf'):
            reject(uow)
        from hashlib import sha256
        if len(raw) != evidence['size_bytes'] or sha256(raw).hexdigest() != evidence['sha256']:
            reject(uow)
        from .evidence_validation import validate_evidence
        validate_evidence(bytes(raw),'label.pdf','application/pdf')

    def _return_sources(self, uow, head, state, sources, return_id, label_id):
        if return_id is None or label_id is None or return_id == label_id:
            reject(uow)
        latest = {}
        for revision in sources.proof.revisions.values():
            if revision['kind']=='OPERATION':
                previous = latest.get(revision['object_id'])
                if previous is None or revision['object_version'] > previous['object_version']:
                    latest[revision['object_id']] = revision
        indexed = {item['operation_id']:item for item in uow.execute(select(t.effects).where(
            t.effects.c.case_id==head['case_id'])).mappings()}
        # A missing index is missing knowledge, not proof that no effect exists.
        # Require complete coverage of every latest saved operation, including
        # old generations/approvals and records from a different producer path.
        if set(latest)!=set(indexed):
            reject(uow)
        for operation_id,revision in latest.items():
            _,body = sources.read(revision['record_id'],{'OPERATION'},current_actor=False)
            effect = indexed[operation_id]
            accepted = uow.execute(select(t.events.c.event_id).where(t.events.c.record_id==revision['record_id'],
                t.events.c.event_kind=='EFFECT',t.events.c.source_hash==revision['content_sha256'])).first()
            if (accepted is None or effect['record_id']!=revision['record_id']
                    or effect['object_version']!=revision['object_version'] or effect['status']!=body['status']):
                reject(uow)
        records = []
        for record_id, kind in ((return_id,'CREATE_RETURN'),(label_id,'GENERATE_LABEL')):
            row, body = sources.read(record_id,{'OPERATION'},current_actor=False)
            effect = uow.execute(select(t.effects).where(t.effects.c.operation_id == body['operation_id'])).mappings().one_or_none()
            if (effect is None or effect['record_id'] != record_id or effect['operation_type'] != kind
                    or effect['generation'] != state['generation'] or effect['input_version'] != head['input_version']
                    or body['status'] != 'SUCCEEDED' or body['result']['type'] != kind):
                reject(uow)
            records.append((effect,body))
        left,right = records
        if (left[0]['approval_record_id'] != right[0]['approval_record_id']
                or left[1]['result']['parcel_id'] != right[1]['result']['parcel_id']):
            reject(uow)
        if state['outcome'] is None and state['approval_record_id'] != left[0]['approval_record_id']:
            reject(uow)
        from .lifecycle_effects import saved_approval
        approval_row,approval = saved_approval(uow,sources,left[1]['approval_id'])
        if (state['proposal_record_id'] is None or state['review_record_id'] is None
                or approval_row['record_id'] != state['approval_record_id']):
            reject(uow)
        _,packet = self._current_proposal(uow,head,state,sources)
        review_row,review = sources.read(state['review_record_id'],{'REVIEW'},current_actor=False)
        if (approval['scope']['review_id'] != review['review']['review_id']
                or review['proposal_record_id'] != state['proposal_record_id']
                or any(approval['scope'][name] != packet[name] for name in ('proposal_id','proposal_version','input_version'))):
            reject(uow)
        unresolved = uow.execute(select(t.effects.c.operation_id).where(t.effects.c.case_id == head['case_id'],
            t.effects.c.operation_id.not_in([left[1]['operation_id'],right[1]['operation_id']]),
            t.effects.c.status.in_(['PENDING','EXECUTING','UNKNOWN','RECONCILING','SUCCEEDED']))).first()
        if unresolved:
            reject(uow)
        self._label(uow,head,right[1]['result']['label_evidence_id'],right[0]['artifact_sha256'])
