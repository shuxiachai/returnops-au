"""F.06 read-only Founder analytics (OF-006, FR-011/012, NFR-005/008; docs/43).

One SELECT reads the store's created-at cohort and each case's current review
reference; counting happens here. Nothing is written: no snapshot, cursor,
encoding row or audit event. Validated output is never returned with a broken
cross-field invariant; any violation is INTERNAL_ERROR (503), never a guess.

Latency is Tier 0 (design F.06 section 2.3 fallback): sample_count = 0, no
percentiles. Tier 0 is kept because trusted start/ready/wait event fields are
the open E.01/E.09 item for C; the intake-DONE start in the design does not
exist for the input a proposal is built for (an order MATCHED result creates
that input through transition(..., input_delta=1) without intake work).
failed_count counts the known technical failures of the proposal step: a
PROPOSAL_FAILED receipt for the head's current input (lifecycle_guards event
kinds; proposal_processor writes the failure). Intake and order-lookup
failures happen before the complete input is accepted and stay unmeasured,
like every other case. Tier 1 candidate for reviewer C (docs/43): start =
accepted_order_projections.accepted_at for the current input; end = the
receipt whose record_id is state.proposal_record_id (unique); unmeasured when
a DECISION-sourced REVISION exists for that input (Founder waiting); failed as
now. percentile_ms/latency_block are its entry point.
"""
import re
from collections import Counter
from datetime import datetime, timezone
from sqlalchemy import and_, select
from . import customer_tables as t, founder_tables as f, lifecycle_tables as lifecycle
from . import founder_codec as finite
from .audit import timestamp
from .canonical import decode_document, digest
from .errors import FlowError
from .wire import _DEFS, validate

METRIC = 'proposal-latency-v1'
STATUSES = tuple(_DEFS['CaseStatus']['enum'])
OUTCOMES = tuple(_DEFS['RiskOutcome']['enum'])
_STAMP = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z')
_REVIEW = t.history.alias('analytics_review')
_PROPOSAL = t.history.alias('analytics_proposal')
ACCEPTED_REVIEWS = ('REVIEW', 'REVIEW_PASS')  # lifecycle_guards: EscalateReviewAccepted, PassReviewAccepted


def parse_query(query):
    """Return (echoed filters, from, before); every invalid input is 422."""
    if type(query) is not dict:
        raise FlowError('VALIDATION_ERROR')
    query = validate('AnalyticsQuery', query)
    bounds = {}
    for name in ('created_from', 'created_before'):
        if name in query:
            value = query[name]
            failed = type(value) is not str or _STAMP.fullmatch(value) is None
            if not failed:
                try:
                    bounds[name] = datetime.fromisoformat(value[:-1] + '+00:00')
                except ValueError:
                    failed = True
            if failed:
                raise FlowError('VALIDATION_ERROR') from None
    if len(bounds) == 2 and not bounds['created_from'] < bounds['created_before']:
        raise FlowError('VALIDATION_ERROR')
    return query, bounds.get('created_from'), bounds.get('created_before')


def cohort_statement(store_id, start, cutoff, status=None):
    """One statement: cohort heads, current review/proposal identity, receipt facts."""
    heads, state, events = t.case_heads, lifecycle.state, lifecycle.events
    conditions = [heads.c.store_id == store_id, heads.c.available.is_(True), heads.c.created_at < cutoff]
    if start is not None:
        conditions.append(heads.c.created_at >= start)
    if status is not None:
        conditions.append(heads.c.status == status)
    source = (heads.outerjoin(state, state.c.case_id == heads.c.case_id)
        .outerjoin(_REVIEW, and_(_REVIEW.c.record_id == state.c.review_record_id, _REVIEW.c.case_id == heads.c.case_id,
                                 _REVIEW.c.kind == 'REVIEW', _REVIEW.c.retention_state == 'AVAILABLE'))
        .outerjoin(t.history_contents, t.history_contents.c.record_id == _REVIEW.c.record_id)
        .outerjoin(f.encodings, f.encodings.c.record_id == _REVIEW.c.record_id)
        .outerjoin(_PROPOSAL, and_(_PROPOSAL.c.record_id == state.c.proposal_record_id,
                                   _PROPOSAL.c.case_id == heads.c.case_id, _PROPOSAL.c.kind == 'PROPOSAL')))
    return (select(heads.c.case_id, heads.c.status, heads.c.input_version,
                   state.c.case_id.label('state_case_id'), state.c.input_version.label('state_input_version'),
                   state.c.proposal_version, state.c.proposal_record_id, state.c.available.label('state_available'),
                   _REVIEW.c.object_id.label('review_object_id'), _REVIEW.c.content_sha256.label('review_sha256'),
                   t.history_contents.c.body.label('review_body'), f.encodings.c.profile.label('review_profile'),
                   _PROPOSAL.c.object_id.label('proposal_object_id'),
                   _PROPOSAL.c.object_version.label('proposal_object_version'),
                   select(events.c.event_id).where(events.c.record_id == state.c.review_record_id,
                       events.c.case_id == heads.c.case_id, events.c.event_kind.in_(ACCEPTED_REVIEWS))
                   .exists().label('review_accepted'),
                   select(events.c.event_id).where(events.c.case_id == heads.c.case_id,
                       events.c.event_kind == 'PROPOSAL_FAILED', events.c.input_version == heads.c.input_version)
                   .exists().label('proposal_failed'))
            .select_from(source).where(*conditions).order_by(heads.c.case_id))


def _same(value, expected):
    return type(value) is int and type(expected) is int and value == expected


def current_outcome(row):
    """Outcome of a decodable review bound to the current input and proposal.

    Lighter than lifecycle_projection's per-case proof: no audit chain or
    component seal is replayed. Anything not proven here is 'without'.
    """
    if (row['state_case_id'] is None or row['state_available'] is not True or row['review_accepted'] is not True
            or row['review_body'] is None
            or row['proposal_object_id'] is None or not _same(row['state_input_version'], row['input_version'])):
        return None
    try:
        if row['review_profile'] == finite.PROFILE:
            content = finite.decode_document(row['review_body'])
            actual = finite.digest(content)
        elif row['review_profile'] in (None, finite.LEGACY_PROFILE):
            content = decode_document(row['review_body'])
            actual = digest(content, 'history/v1')
        else:
            return None
    except FlowError:
        return None
    review = content.get('review') if type(content) is dict else None
    if (actual != row['review_sha256'] or type(review) is not dict
            or content.get('proposal_record_id') != row['proposal_record_id']
            or review.get('review_id') != row['review_object_id'] or review.get('case_id') != row['case_id']
            or review.get('outcome') not in OUTCOMES or review.get('proposal_id') != row['proposal_object_id']
            or not _same(review.get('input_version'), row['input_version'])
            or not _same(review.get('proposal_version'), row['proposal_version'])
            or not _same(row['proposal_object_version'], row['proposal_version'])):
        return None
    return review['outcome']


def percentile_ms(samples, percent):
    """Linear (type 7) percentile of integer ms, exact ratio rounded half-even."""
    ordered = sorted(samples)
    if not ordered or type(percent) is not int or not 0 <= percent <= 100:
        raise FlowError()
    quotient, remainder = divmod((len(ordered) - 1) * percent, 100)
    low, high = ordered[quotient], ordered[min(quotient + 1, len(ordered) - 1)]
    whole, rest = divmod(low * 100 + (high - low) * remainder, 100)
    if rest * 2 > 100 or (rest * 2 == 100 and whole % 2):
        whole += 1
    return whole


def latency_block(case_count, samples=(), failed=0):
    samples = list(samples)
    if (type(case_count) is not int or type(failed) is not int or failed < 0
            or any(type(value) is not int or value < 0 for value in samples) or len(samples) + failed > case_count):
        raise FlowError()
    result = {'metric_version': METRIC, 'sample_count': len(samples), 'failed_count': failed,
              'unmeasured_count': case_count - len(samples) - failed}
    if samples:
        result.update(p50_ms=percentile_ms(samples, 50), p95_ms=percentile_ms(samples, 95))
    return result


def check_snapshot(snapshot):
    """Contract shape plus the docs/09 section 10 cross-field rules."""
    snapshot = validate('AnalyticsSnapshot', snapshot, internal=True)
    count, latency = snapshot['case_count'], snapshot['proposal_latency']
    statuses = [item['status'] for item in snapshot['cases_by_status']]
    outcomes = [item['outcome'] for item in snapshot['current_risk_counts']]
    measured = latency['sample_count'] > 0
    if (statuses != sorted(set(statuses), key=STATUSES.index) or outcomes != sorted(set(outcomes), key=OUTCOMES.index)
            or any(item['count'] < 1 for item in snapshot['cases_by_status'] + snapshot['current_risk_counts'])
            or sum(item['count'] for item in snapshot['cases_by_status']) != count
            or sum(item['count'] for item in snapshot['current_risk_counts']) + snapshot['cases_without_current_review'] != count
            or latency['sample_count'] + latency['failed_count'] + latency['unmeasured_count'] != count
            or ('p50_ms' in latency) != measured or ('p95_ms' in latency) != measured
            or (measured and latency['p50_ms'] > latency['p95_ms'])):
        raise FlowError()
    return snapshot


def analytics(uow, actor, query, now):
    filters, start, before = parse_query(query)
    if type(now) is not datetime or now.utcoffset() is None:
        raise FlowError()
    now = now.astimezone(timezone.utc)
    cutoff = now if before is None or before > now else before
    rows = uow.execute(cohort_statement(actor.store_id, start, cutoff, filters.get('status'))).mappings().all()
    seen, statuses, outcomes, failed = set(), Counter(), Counter(), 0
    for row in rows:
        if (row['case_id'] in seen or row['status'] not in STATUSES or type(row['proposal_failed']) is not bool
                or filters.get('status', row['status']) != row['status']):
            raise FlowError()
        failed += row['proposal_failed']
        seen.add(row['case_id'])
        statuses[row['status']] += 1
        outcome = current_outcome(row)
        if outcome is not None:
            outcomes[outcome] += 1
    count = len(seen)
    return check_snapshot({
        'as_of': timestamp(now), 'filters': filters, 'case_count': count,
        'cases_by_status': [{'status': name, 'count': statuses[name]} for name in STATUSES if statuses[name]],
        'current_risk_counts': [{'outcome': name, 'count': outcomes[name]} for name in OUTCOMES if outcomes[name]],
        'cases_without_current_review': count - sum(outcomes.values()),
        'proposal_latency': latency_block(count, failed=failed)})
