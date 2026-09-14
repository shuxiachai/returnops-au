"""rc.4 artifact and fixture oracles, NOT a history service or state guard.

FR-001/006/008/010/011/012, NFR-001/003/006/008; docs/09, shared class/state/
sequence and MA recovery models. No HTTP/auth/database/provider is executed.
"""
from copy import deepcopy
import hashlib
import unittest

from test_contract_v1 import OPENAPI, POSITIVE, SCHEMAS, pointer, validator


def value(name):
    return deepcopy(POSITIVE[name]['value'])


def assert_proposal_bundle(record):
    """Test-only exact-material oracle for a retained proposal fixture.

    It binds citation verification to the historical packet and requires one
    verification entry per cited ID. Check outcomes deliberately remain
    unrestricted: failed citations are evidence for later Risk rejection.
    """
    validator('FounderHistoryRecord').validate(record)
    bundle = record['content']
    packet = bundle['packet']
    assert record['kind'] == 'PROPOSAL'
    assert record['case_id'] == packet['case_id']
    assert record['object_id'] == packet['proposal_id']
    assert record['object_version'] == packet['proposal_version']
    for name in ('order_lookup', 'retrieval_result', 'citation_verification'):
        source = bundle[name]
        for key in ('case_id', 'input_version'):
            assert source[key] == packet[key], (name, key)
    for name in ('retrieval_result', 'citation_verification'):
        assert bundle[name]['corpus_version'] == packet['corpus_version']
    verification = bundle['citation_verification']
    for key in ('proposal_id', 'proposal_version'):
        assert verification[key] == packet[key], ('citation_verification', key)
    assert any(s['statement_id'] == packet['original_statement_id'] for s in bundle['statements'])
    citation_ids = [citation['citation_id'] for citation in packet['citations']]
    check_ids = [check['citation_id'] for check in verification['checks']]
    assert len(citation_ids) == len(set(citation_ids)), 'duplicate packet citation IDs'
    assert len(check_ids) == len(set(check_ids)), 'duplicate verification citation IDs'
    assert set(check_ids) == set(citation_ids), 'verification must cover exactly the cited IDs'
    for citation in packet['citations']:
        matching = [p for p in bundle['retrieval_result']['passages'] if p['passage_id'] == citation['passage_id']]
        assert len(matching) == 1
        passage = matching[0]
        for key in ('document_id', 'source_version', 'corpus_version', 'content_sha256', 'location'):
            assert passage[key] == citation[key], key
        assert hashlib.sha256(passage['content'].encode('utf-8')).hexdigest() == passage['content_sha256']
    for attachment in bundle['attachments']:
        assert attachment['status'] == 'BOUND'
        assert attachment['case_id'] == packet['case_id']


def assert_snapshot_pages(pages, frozen_records):
    """Check a constructed trace against its declared immutable fixture snapshot.

    This does not issue a cursor, query a store or implement pagination. Actual
    cursor authentication/as-of storage/retention still require runtime tests.
    """
    first = pages[0]
    seen = []
    for page in pages:
        validator('FounderHistoryPage').validate(page)
        for key in ('case_id', 'kind', 'snapshot_id', 'snapshot_case_version', 'as_of'):
            assert page[key] == first[key], key
        for record in page['items']:
            assert record['case_id'] == page['case_id']
            assert record['case_version'] <= page['snapshot_case_version']
            assert record == frozen_records[record['record_id']]
            seen.append(record)
    keys = [(r['recorded_sequence'], r['record_id']) for r in seen]
    assert keys == sorted(keys)
    assert len({r['record_id'] for r in seen}) == len(seen)
    assert set(frozen_records) == {r['record_id'] for r in seen}
    assert 'next_cursor' not in pages[-1]


class ContractV1Rc4Tests(unittest.TestCase):
    def test_role_specific_history_queries_and_responses(self):
        for role, route, fixture in [
            ('Founder', '/v1/founder/cases/{case_id}/history', 'founder-proposal-history-page'),
            ('Customer', '/v1/cases/{case_id}/history', 'customer-statement-history-page'),
        ]:
            op = OPENAPI['paths'][route]['get']
            self.assertEqual(op['x-roles'], [role.upper()])
            schema = op['responses']['200']['content']['application/json']['schema']['$ref'].split('/')[-1]
            self.assertEqual(schema, role + 'HistoryPage')
            validator(schema).validate(value(fixture))
            params = [pointer(OPENAPI, p['$ref']) if '$ref' in p else p for p in op['parameters']]
            self.assertEqual({p['name'] for p in params}, {'kind', 'cursor', 'limit', 'object_id', 'object_version'})
            self.assertTrue(next(p for p in params if p['name'] == 'kind')['required'])
        for kind in ('PROPOSAL', 'REVIEW', 'APPROVAL', 'OPERATION', 'NOTIFICATION'):
            self.assertFalse(validator('CustomerHistoryQuery').is_valid({'kind': kind}))
        self.assertEqual(OPENAPI['x-jira-key'], 'KAN-32')

    def test_shared_cursor_boundaries(self):
        self.assertEqual(OPENAPI['components']['parameters']['Cursor']['schema'], {'$ref': './schemas.json#/$defs/Cursor'})
        for name in ('AuditPage', 'CaseList', 'FounderHistoryPage', 'CustomerHistoryPage'):
            self.assertEqual(SCHEMAS['$defs'][name]['properties']['next_cursor'], {'$ref': '#/$defs/Cursor'})
        for token in ('demo_cursor', 'x' * 1024):
            self.assertTrue(validator('Cursor').is_valid(token))
        for token in ('', 'x' * 1025, 'cursor\n', 'cursor\x00', '../path', 'a+b='):
            self.assertFalse(validator('Cursor').is_valid(token))

    def test_old_proposal_keeps_original_material_and_review_binding(self):
        old = value('history-proposal')
        assert_proposal_bundle(old)
        newer = deepcopy(old)
        newer['record_id'] = 'history-proposal-002'
        newer['object_version'] += 1
        newer['content']['packet']['proposal_version'] += 1
        newer['content']['citation_verification']['proposal_version'] += 1
        assert_proposal_bundle(newer)
        review = value('history-risk-review')['content']
        self.assertEqual(review['proposal_record_id'], old['record_id'])
        for key in ('case_id', 'input_version', 'proposal_id', 'proposal_version', 'corpus_version'):
            self.assertEqual(review['review'][key], old['content']['packet'][key])
        self.assertNotEqual(review['review']['proposal_version'], newer['content']['packet']['proposal_version'])

    def test_history_fixture_oracle_rejects_stale_or_rebuilt_sources(self):
        mutations = [
            lambda r: r.update(case_id='case-other'),
            lambda r: r.update(object_version=99),
            lambda r: r['content']['retrieval_result'].update(input_version=99),
            lambda r: r['content']['citation_verification'].update(proposal_id='proposal-other'),
            lambda r: r['content']['citation_verification'].update(proposal_version=99),
            lambda r: r['content']['citation_verification'].update(checks=[]),
            lambda r: r['content']['citation_verification']['checks'][0].update(citation_id='citation-other'),
            lambda r: r['content']['citation_verification']['checks'].append({
                **r['content']['citation_verification']['checks'][0],
                'citation_id': 'citation-extra',
            }),
            lambda r: r['content']['retrieval_result']['passages'][0].update(content='Replacement current source text.'),
            lambda r: r['content']['retrieval_result']['passages'][0].update(source_version='replacement-version'),
        ]
        for change in mutations:
            record = value('history-proposal'); change(record)
            # Shapes remain legal; rejection below comes from a test-only oracle.
            validator('FounderHistoryRecord').validate(record)
            with self.assertRaises(AssertionError):
                assert_proposal_bundle(record)

    def test_history_fixture_oracle_rejects_duplicate_citation_ids(self):
        for target in ('packet', 'verification'):
            with self.subTest(target=target):
                record = value('history-proposal')
                if target == 'packet':
                    duplicate = deepcopy(record['content']['packet']['citations'][0])
                    duplicate['passage_id'] = 'passage-other'
                    record['content']['packet']['citations'].append(duplicate)
                else:
                    duplicate = deepcopy(record['content']['citation_verification']['checks'][0])
                    record['content']['citation_verification']['checks'].append(duplicate)
                validator('FounderHistoryRecord').validate(record)
                with self.assertRaisesRegex(AssertionError, f'duplicate {target} citation IDs'):
                    assert_proposal_bundle(record)

    def test_history_fixture_oracle_allows_failed_and_zero_citation_evidence(self):
        failed = value('history-proposal')
        failed['content']['citation_verification']['checks'][0].update(
            result='HASH_MISMATCH',
            message='Historical verifier reported a content hash mismatch.',
        )
        assert_proposal_bundle(failed)
        uncited = value('history-proposal')
        uncited['content']['packet']['citations'] = []
        uncited['content']['citation_verification']['checks'] = []
        validator('FounderHistoryRecord').validate(uncited)
        assert_proposal_bundle(uncited)

    def test_101_revisions_fit_two_pages_but_not_one(self):
        template = value('history-statement')
        records = []
        for index in range(1, 102):
            record = deepcopy(template)
            record.update(record_id=f'history-statement-{index}', object_id=f'statement-{index}', recorded_sequence=index)
            record['content'].update(statement_id=f'statement-{index}', kind='CLARIFICATION')
            records.append(record)
        first = value('founder-proposal-history-page')
        first.update(kind='STATEMENT', items=records[:100], next_cursor='demo_second_page')
        second = deepcopy(first); second.update(items=records[100:]); second.pop('next_cursor')
        frozen = {r['record_id']: deepcopy(r) for r in records}
        assert_snapshot_pages([first, second], frozen)
        too_many = deepcopy(first); too_many['items'] = records
        self.assertFalse(validator('FounderHistoryPage').is_valid(too_many))
        for mutation in ('duplicate', 'snapshot', 'case', 'content', 'append'):
            changed = deepcopy(second)
            if mutation == 'duplicate': changed['items'] = [records[0]]
            elif mutation == 'snapshot': changed['snapshot_id'] = 'snapshot-other'
            elif mutation == 'case': changed['items'][0]['case_id'] = 'case-other'
            elif mutation == 'content': changed['items'][0]['content']['raw_text'] = 'Changed after snapshot.'
            else: changed['items'].append(deepcopy(records[0]))
            with self.assertRaises(AssertionError):
                assert_snapshot_pages([first, changed], frozen)

    def test_preview_metadata_and_retention_are_explicit(self):
        for name in ('founder-review-ready-view', 'customer-submitted-view', 'customer-retention-view'):
            view = value(name)
            for key, window in view['collection_windows'].items():
                self.assertEqual(window['snapshot_case_version'], view['case_version'])
                self.assertEqual(window['preview_count'], len(view[key]))
                self.assertEqual(window['truncated'], window['total_records'] > len(view[key]))
                self.assertLessEqual(window['unavailable_count'], window['total_records'])
                validator('Cursor').validate(window['start_cursor'])
        deleted = value('history-proposal-tombstone')
        self.assertNotIn('content', deleted)
        restored = deepcopy(deleted); restored['content'] = value('history-proposal')['content']
        self.assertFalse(validator('FounderHistoryRecord').is_valid(restored))
        self.assertEqual(value('customer-retention-view')['statements'], [])

    def test_provenance_is_typed_and_history_reference_is_resolvable(self):
        event = value('audit-with-provenance')
        record = value('history-proposal')
        reference = event['history_refs'][0]
        for key in ('record_id', 'kind', 'object_id', 'object_version'):
            self.assertEqual(reference[key], record[key])
        validator('AuditEvent').validate(event)
        self.assertEqual(event['actor']['model_run'], record['content']['packet']['model_run'])
        coordinator = value('audit-coordinator-provenance')
        self.assertEqual(coordinator['actor']['model_run'], value('coordinator-output')['model_run'])
        for actor in (
            {'kind': 'HUMAN', 'role': 'FOUNDER', 'principal_id': 'founder-demo-001'},
            {'kind': 'MODEL', 'model_run': value('risk-pass')['model_run']},
            {'kind': 'SERVICE', 'component_id': 'domain-service-001'},
        ):
            validator('ActorProvenance').validate(actor)
            actor['email'] = 'forbidden@example.invalid'
            self.assertFalse(validator('ActorProvenance').is_valid(actor))

    def test_all_history_payloads_belong_to_the_recorded_case(self):
        # Test-data consistency, not a service authorization check.
        for fixture in POSITIVE.values():
            if fixture['schema'] not in ('FounderHistoryRecord', 'CustomerHistoryRecord'):
                continue
            record = fixture['value']
            if record['retention_state'] != 'AVAILABLE':
                continue
            payload = record['content']
            nested = {'PROPOSAL': 'packet', 'REVIEW': 'review', 'APPROVAL': 'scope', 'ORDER_LOOKUP_BLOCK': 'block'}
            if record['kind'] in nested:
                payload = payload[nested[record['kind']]]
            with self.subTest(fixture=fixture['name']):
                if 'case_id' in payload:
                    self.assertEqual(record['case_id'], payload['case_id'])
                if 'case_version' in payload:
                    self.assertEqual(record['case_version'], payload['case_version'])
        staged = value('customer-history-evidence')
        staged['content'] = value('staged-photo')
        self.assertFalse(validator('CustomerHistoryRecord').is_valid(staged))

    def test_customer_history_cannot_embed_founder_or_actor_metadata(self):
        for name in ('history-proposal', 'history-risk-review', 'history-approval', 'history-operation'):
            self.assertFalse(validator('CustomerHistoryRecord').is_valid(value(name)))
        safe = value('customer-history-outcome')
        validator('CustomerHistoryRecord').validate(safe)
        for field in ('actor', 'approval', 'risk_review', 'error'):
            altered = deepcopy(safe); altered[field] = {'internal': 'data'}
            self.assertFalse(validator('CustomerHistoryRecord').is_valid(altered))


if __name__ == '__main__':
    unittest.main()
