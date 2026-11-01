"""Gate 2 pilot: twelve synthetic cases through the live advisory roles of a deployment (1 November 2026).

Usage: python -I tools/gate2/pilot_run.py <base url> <sessions.json> <photos folder> <pilot cases json> <results json>

For each case the synthetic customer lodges the statement (with the order reference and photos the case names); once
the case has left SUBMITTED, the Founder asks for the photo check (when there are photos), the A1 assessment draft
and the C2 review, in the order of the demonstration. The review reads the facts card, the draft and the photo check.
Prints one line per case and a summary. Keys are read from the local copy before every call (so the copy can be
renewed during a run) and never printed; model text is kept short in the results file. The cases' intent fields are A's design intents, not Gold labels (docs/51).
"""
import json
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1].rstrip('/')
SESSIONS = Path(sys.argv[2])
PHOTOS = Path(sys.argv[3])
CASES = json.loads(Path(sys.argv[4]).read_text(encoding='utf-8'))['cases']
OUT = Path(sys.argv[5])
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
REMEDIES = {'PROPOSE_RETURN', 'PROPOSE_REFUND', 'PROPOSE_REPLACEMENT', 'PROPOSE_REPAIR'}


def call(method, path, who, body=None, headers=None, timeout=150):
    key = json.loads(SESSIONS.read_text(encoding='utf-8'))['tokens'][who]
    request = urllib.request.Request(BASE + path, data=body, method=method,
                                     headers={'Authorization': 'Bearer ' + key, 'Accept': 'application/json', **(headers or {})})
    started = time.monotonic()
    try:
        with OPENER.open(request, timeout=timeout) as answer:
            return answer.status, json.loads(answer.read() or b'null'), round(time.monotonic() - started, 1)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw), round(time.monotonic() - started, 1)
        except ValueError:
            return error.code, None, round(time.monotonic() - started, 1)


def upload(name):
    boundary = 'b' + uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f'Content-Type: image/png\r\n\r\n').encode() + (PHOTOS / name).read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    status, answer, _ = call('POST', '/v1/evidence', 'synthetic_customer_a', body,
                             {'Content-Type': 'multipart/form-data; boundary=' + boundary, 'Idempotency-Key': 'pilot-' + uuid.uuid4().hex})
    assert status in (200, 201), status
    return answer['evidence_id']


def short(text, limit=200):
    return None if text is None else text[:limit]


rows = []
for case in CASES:
    row = {'id': case['id'], 'slot': case['slot'], 'coverage': case['coverage']}
    request = {'original_message': case['message'], 'requested_outcome': case['requested_outcome'],
               'evidence_ids': [upload(name) for name in case['photos']]}
    if case['reference']:
        request['order_reference'] = case['reference']
    status, created, _ = call('POST', '/v1/cases', 'synthetic_customer_a', json.dumps(request).encode(),
                              {'Content-Type': 'application/json', 'Idempotency-Key': 'pilot-' + uuid.uuid4().hex})
    assert status == 201, status
    case_id, view, waited = created['case_id'], {}, time.monotonic()
    for _ in range(60):  # the intake, the order check and the facts card run in the service's workers
        status, view, _ = call('GET', f'/v1/founder/cases/{case_id}', 'founder')
        if status == 200 and view.get('status') != 'SUBMITTED' and view.get('facts') is not None:
            break
        time.sleep(2)
    row['case_status'] = view.get('status')
    row['facts_category'] = (view.get('facts') or {}).get('issue_category')
    row['facts_wait_seconds'] = round(time.monotonic() - waited, 1)
    if case['photos']:
        status, answer, took = call('POST', f'/v1/founder/cases/{case_id}/assistant/image-observations', 'founder')
        row['photos'] = {'http': status, 'seconds': took,
                         'details': None if status != 200 else [d['condition'] + '/' + d['text_in_image'] for d in answer['details']]}
    status, answer, took = call('POST', f'/v1/founder/cases/{case_id}/assistant/assessment', 'founder')
    row['assessment'] = {'http': status, 'seconds': took} if status != 200 else {
        'http': 200, 'seconds': took, 'action': answer['recommended_action'], 'category': answer['issue_category'],
        'status': answer['assessment_status'], 'basis': answer['possible_basis'], 'lines': [l['line'] for l in answer['covered_lines']],
        'citations': [c['passage_id'] for c in answer['citations']], 'confidence': answer['confidence'],
        'questions': len(answer['unresolved_questions']), 'conditions': len(answer['conditions']),
        'rationale': short(answer['rationale'])}
    status, answer, took = call('POST', f'/v1/founder/cases/{case_id}/assistant/risk-review', 'founder')
    row['review'] = {'http': status, 'seconds': took} if status != 200 else {
        'http': 200, 'seconds': took, 'outcome': answer['outcome'], 'inputs_used': answer['inputs_used'],
        'findings': [f['category'] + '/' + f['severity'] for f in answer['findings']],
        'questions': len(answer['questions']), 'revisions': len(answer['revision_requests']), 'summary': short(answer['summary'])}
    intent, assessment, review = case['intent'], row['assessment'], row['review']
    row['intent'] = {
        'category': row['facts_category'] == intent['category'],
        'assessment': assessment.get('action') in intent['assessment'],
        'review': review.get('outcome') is not None and (
            review['outcome'] in intent['review'] if 'review' in intent else review['outcome'] not in intent.get('review_not', [])),
    }
    if 'photo_text' in intent:
        row['intent']['photo_text'] = intent['photo_text'] in ' '.join((row.get('photos') or {}).get('details') or [])
    row['checks'] = {
        'no_remedy_without_lines': not (assessment.get('action') in REMEDIES and not assessment.get('lines')),
        'review_read_draft': assessment.get('http') != 200 or (review.get('inputs_used') or {}).get('assessment_draft') is True,
        'review_read_photos': not case['photos'] or (row.get('photos') or {}).get('http') != 200
                              or (review.get('inputs_used') or {}).get('photo_observations') is True,
    }
    rows.append(row)
    print(json.dumps({key: row[key] for key in ('id', 'case_status', 'facts_category', 'facts_wait_seconds')} |
                     {'photos': (row.get('photos') or {}).get('details'), 'assessment': assessment.get('action', assessment.get('http')),
                      'review': review.get('outcome', review.get('http')), 'intent': row['intent'], 'checks': row['checks']}))

summary = {
    'cases': len(rows),
    'facts_card_present': sum(row['facts_category'] is not None for row in rows),
    'assessment_answered': sum(row['assessment']['http'] == 200 for row in rows),
    'review_answered': sum(row['review']['http'] == 200 for row in rows),
    'intent_category': sum(row['intent']['category'] for row in rows),
    'intent_assessment': sum(row['intent']['assessment'] for row in rows),
    'intent_review': sum(row['intent']['review'] for row in rows),
    'checks_failed': sum(not all(row['checks'].values()) for row in rows),
    'facts_wait_seconds_max': max(row['facts_wait_seconds'] for row in rows),
    'assessment_seconds_max': max(row['assessment']['seconds'] for row in rows),
    'review_seconds_max': max(row['review']['seconds'] for row in rows),
}
OUT.write_text(json.dumps({'summary': summary, 'rows': rows}, indent=1, ensure_ascii=True), encoding='utf-8')
print('SUMMARY ' + json.dumps(summary))
