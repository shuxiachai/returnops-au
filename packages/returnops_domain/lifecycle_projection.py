"""Read current references without initializing business metadata or advancing it."""
from .lifecycle_guards import LifecycleGuards
from .lifecycle_sources import Sources
from .lifecycle_state import current, reject


def project(uow, head, result):
    state = current(uow,head)
    if state is None or not state['available']:
        return
    sources = Sources(uow,head,'lifecycle-read')
    if state['proposal_record_id'] is not None:
        _, packet = LifecycleGuards._current_proposal(uow,head,state,sources)
        result['current_proposal'] = packet
        _,bundle=sources.read(state['proposal_record_id'],{'PROPOSAL'},current_actor=False)
        referenced={citation['passage_id'] for citation in packet['citations']}
        result['cited_passages']=[passage for passage in bundle['retrieval_result']['passages'] if passage['passage_id'] in referenced]
    if state['review_record_id'] is not None:
        from .lifecycle_schema import version, CURRENT, LEGACY
        schema=version(uow.connection)
        if schema==CURRENT:
            # Dispatch by immutable origin AND persisted event/work identity.
            # Outcome text is untrusted until the selected full proof passes.
            from .manual_target import one
            from . import lifecycle_tables as tables
            row,_=sources.read(state['review_record_id'],{'REVIEW'},current_actor=False)
            origin=sources.proof.origin(row)
            event=one(uow,tables.events,record_id=row['record_id'])
            work=one(uow,tables.work,work_id=event['work_id'])
            from .pass_review_sources import COMPONENT as PASS_COMPONENT
            from .review_sources import COMPONENT as ESC_COMPONENT
            identity=(origin['actor'],work['component_id'],event['event_kind'])
            if identity==({'kind':'SERVICE','component_id':PASS_COMPONENT},PASS_COMPONENT,'REVIEW_PASS'):
                from .pass_review_sources import accepted_review
            elif identity==({'kind':'SERVICE','component_id':ESC_COMPONENT},ESC_COMPONENT,'REVIEW'):
                from .review_sources import accepted_review
            else:
                reject(uow)
            accepted_review(uow,head,state,'lifecycle-read')
        elif schema!=LEGACY:
            reject(uow)
        _, bundle = sources.read(state['review_record_id'],{'REVIEW'},current_actor=False)
        review = bundle['review']
        if (state['proposal_record_id'] is None or bundle['proposal_record_id'] != state['proposal_record_id']
                or any(review[name] != result['current_proposal'][name]
                       for name in ('case_id','input_version','proposal_id','proposal_version','corpus_version'))):
            reject(uow)
        result['current_review'] = review
    if state['preview_id'] is not None:
        from datetime import datetime, timezone
        from .preview_sources import accepted_preview, source_target
        preview = accepted_preview(uow, head, state['preview_id'])
        if (preview['row']['input_version'] != head['input_version']
                or preview['row']['generation'] != state['generation']
                or preview['row']['proposal_record_id'] != state['proposal_record_id']
                or preview['row']['review_record_id'] != state['review_record_id']):
            reject(uow)
        if head['status'] == 'AWAITING_APPROVAL':
            _, exact = source_target(uow, head, state, expected_version=head['case_version'])
            if exact != preview:
                reject(uow)
            if datetime.now(timezone.utc) < preview['row']['expires_at']:
                result['action_preview'] = preview['body']
        elif head['status'] == 'APPROVED':
            from .approve_sources import accepted_approval
            from .preview_profile import APPROVAL_COMPONENT
            approved = accepted_approval(uow, head, state['approval_record_id'], APPROVAL_COMPONENT)
            if approved['preview'] != preview or approved['event']['case_version'] != head['case_version']:
                reject(uow)
        else:
            reject(uow)
