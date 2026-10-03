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
        _, bundle = sources.read(state['review_record_id'],{'REVIEW'},current_actor=False)
        review = bundle['review']
        if (state['proposal_record_id'] is None or bundle['proposal_record_id'] != state['proposal_record_id']
                or any(review[name] != result['current_proposal'][name]
                       for name in ('case_id','input_version','proposal_id','proposal_version','corpus_version'))):
            reject(uow)
        result['current_review'] = review
    # This slice has no preview producer/store. A nonempty placeholder pointer
    # cannot be interpreted as an executable preview.
    if state['preview_id'] is not None:
        reject(uow)
