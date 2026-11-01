"""Development check of the live Coordinator and C2 reviewer on C's ten E01 development examples (1 November 2026).

Builds one script that runs inside the Railway service, where the model key stays (docs/50, section 5):

    python -I tools/gate2/e01_development_check.py experiments/evaluation_candidate/examples/e01_development_examples.json <out folder>
    railway ssh --service returnops-demo-app -- python -c "import base64,zlib;exec(zlib.decompress(base64.b64decode('<contents of devcheck_bootstrap.txt>')))"

The remote script prints one JSON row per example and a SUMMARY line: categories, outcomes and timings only, never a key
or model text. The examples are C's invented public scorer fixtures with proposed labels (C_PROPOSAL_PENDING_A_REVIEW):
this is a development check, not Gold, not E.12 and not acceptance. The reviewer's inputs are adapted: the candidate
sketch as the proposal rationale, the order text as one order line, policy and passage texts as guidance_sources.
"""
import base64
import json
import sys
import zlib
from pathlib import Path

examples = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
out = Path(sys.argv[2])
common = {source['source_id']: source for source in examples['common_sources']}
cases = []
for case in examples['cases']:
    own = {source['source_id']: source for source in case['sources']}
    statement = next(source['text'] for source in case['sources'] if source['kind'] == 'INVENTED_CUSTOMER_STATEMENT')
    order = next((source['text'] for source in case['sources'] if source['kind'] == 'INVENTED_ORDER_SNAPSHOT'), None)
    guidance = []
    for ref in case['available_source_ids']:
        source = own.get(ref) or common.get(ref)
        if source and source['kind'] not in ('INVENTED_CUSTOMER_STATEMENT', 'INVENTED_ORDER_SNAPSHOT'):
            guidance.append({'id': ref, 'kind': source['kind'], 'text': source['text']})
    cases.append({'id': case['case_id'], 'statement': statement, 'order': order, 'guidance': guidance,
                  'candidate': case['candidate_under_review']['text'],
                  'category': case['quality_expectation']['category'],
                  'escalate': case['risk_expectation']['escalation_expected'],
                  'acceptable': case['risk_expectation']['acceptable_outcomes']})

REMOTE = r'''
import base64, json, time, zlib
from returnops_api.model_settings import ModelSettings
from returnops_domain.coordinator_showcase import CoordinatorInput, StatementSource, build_invocation, parse_facts, redact, _printable
from returnops_domain.risk_reviewer import RISK_PROMPT, PROMPT_VERSION as RISK_VERSION, parse_risk_review
from returnops_domain.model_transport import ModelInvocation

CASES = json.loads(zlib.decompress(base64.b64decode(DATA)))
settings = ModelSettings.from_environment()
transport = settings.transport()


def clean(text, limit):
    return redact(_printable(text))[0][:limit]


def ask(invocation, parse):
    started = time.monotonic()
    try:
        value = parse(transport(invocation).content)
        return value, None, round(time.monotonic() - started, 1)
    except Exception as error:
        return None, type(error).__name__ + ':' + str(getattr(error, 'code', '')), round(time.monotonic() - started, 1)


rows = []
for case in CASES:
    data = CoordinatorInput(case['id'], (StatementSource('dev', '0' * 64, 'ORIGINAL', case['statement']),), 'UNSPECIFIED',
                            case['order'] is not None, 'dev')
    invocation, _ = build_invocation(data, provider_id=settings.provider_id, model_id=settings.model_id)
    facts, facts_error, facts_seconds = ask(invocation, lambda text: parse_facts(text, 'UNSPECIFIED'))
    payload = {
        'case_status': 'RISK_REVIEW',
        'statements': [{'kind': 'ORIGINAL', 'requested_outcome': 'UNSPECIFIED', 'text': clean(case['statement'], 2000)}],
        'attachments': [], 'open_questions_to_customer': [],
        'order': None if case['order'] is None else {'currency': 'AUD', 'purchased_at': None, 'line_items': [
            {'line': 1, 'description': clean(case['order'], 600), 'quantity': 1, 'unit_price_minor': 0}]},
        'order_lookup_block': None,
        'proposal': {'recommended_action': 'SEE_RATIONALE', 'rationale': clean(case['candidate'], 2000), 'covered_lines': [],
                     'conditions': [], 'alternatives': [], 'unresolved_questions': [], 'guidance_citations': len(case['guidance'])},
        'guidance_sources': [{'source_id': g['id'], 'kind': g['kind'], 'text': clean(g['text'], 1200)} for g in case['guidance']],
        'coordinator_facts': None, 'photo_observations': None, 'assessment_draft': None,
    }
    invocation = ModelInvocation(RISK_PROMPT, json.dumps(payload, ensure_ascii=True, sort_keys=True), RISK_VERSION,
                                 settings.provider_id, settings.model_id)
    review, review_error, review_seconds = ask(invocation, lambda text: parse_risk_review(text, True))
    row = {'id': case['id'], 'expected_category': case['category'], 'category': None if facts is None else facts['issue_category'],
           'facts_error': facts_error, 'facts_seconds': facts_seconds,
           'escalate_expected': case['escalate'], 'acceptable': case['acceptable'],
           'outcome': None if review is None else review['outcome'], 'review_error': review_error, 'review_seconds': review_seconds,
           'findings': [] if review is None else [f['category'] + '/' + f['severity'] for f in review['findings']]}
    rows.append(row)
    print(json.dumps(row))

escalating = [row for row in rows if row['escalate_expected']]
calm = [row for row in rows if not row['escalate_expected']]
summary = {
    'model': settings.model_id, 'coordinator_prompt': 'a106-coordinator-showcase-v1', 'review_prompt': RISK_VERSION,
    'cases': len(rows),
    'category_matches': sum(row['category'] == row['expected_category'] for row in rows),
    'category_rejected': sum(row['facts_error'] is not None for row in rows),
    'outcome_acceptable': sum(row['outcome'] in row['acceptable'] for row in rows),
    'escalation_found': sum(row['outcome'] == 'ESCALATE' for row in escalating), 'escalation_expected': len(escalating),
    'no_escalation_kept': sum(row['outcome'] != 'ESCALATE' and row['outcome'] is not None for row in calm), 'no_escalation_expected': len(calm),
    'review_rejected': sum(row['review_error'] is not None for row in rows),
    'facts_seconds_max': max(row['facts_seconds'] for row in rows), 'review_seconds_max': max(row['review_seconds'] for row in rows),
}
print('SUMMARY ' + json.dumps(summary))
'''

data = base64.b64encode(zlib.compress(json.dumps(cases, ensure_ascii=True).encode('ascii'), 9)).decode('ascii')
script = 'DATA = ' + repr(data) + '\n' + REMOTE
(out / 'devcheck_remote.py').write_text(script, encoding='utf-8', newline='\n')
bootstrap = base64.b64encode(zlib.compress(script.encode('utf-8'), 9)).decode('ascii')
(out / 'devcheck_bootstrap.txt').write_text(bootstrap, encoding='ascii', newline='\n')
print('cases', len(cases), 'data chars', len(data), 'bootstrap chars', len(bootstrap))
for case in cases:
    print(case['id'], case['category'], case['escalate'], case['acceptable'], 'order' if case['order'] else 'no order',
          [g['id'] for g in case['guidance']])
