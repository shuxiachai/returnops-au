"""rc.5 fixture checks, not running idempotency, retention or label recovery.

F.01/F.03/F.07/A1/A2; FR-001/010/011/012, NFR-002/003/004/006;
docs/09 sections 7/10.4, MA OperationAttempt and recovery sequence.
"""
from copy import deepcopy
import json
import unittest

from test_contract_v1 import EXAMPLES, OPENAPI, POSITIVE, pointer, validator


def replay_fixture():
    return deepcopy(next(item for item in EXAMPLES['runtime_guards']
                         if item['name'] == 'clarification-replay-after-receipt-retention'))


def assert_removed_text_absent(scenario):
    """Cross-record fixture oracle; no server retention behavior is implemented."""
    context = scenario['fixture_context']
    statements = context['accepted_response']['statements']
    removed = [statement['raw_text'] for statement in statements
               if statement['statement_id'] in context['removed_statement_ids']]
    assert len(removed) == len(context['removed_statement_ids'])
    response = json.dumps(scenario['error'], ensure_ascii=False)
    assert all(text not in response for text in removed), 'Removed text restored by receipt'


class ContractV1Rc5Tests(unittest.TestCase):
    def test_retention_replay_fixture_is_an_accepted_request_not_a_new_stale_intent(self):
        scenario = replay_fixture()
        context = scenario['fixture_context']
        accepted = context['accepted_response']
        validator('ClarificationRequest').validate(scenario['request'])
        validator('CustomerCaseView').validate(accepted)
        validator('IdempotencyKey').validate(context['idempotency_key'])
        self.assertEqual(context['case_id'], accepted['case_id'])
        self.assertLess(scenario['request']['expected_case_version'], accepted['case_version'])
        self.assertLess(accepted['case_version'], context['current_case_version'])
        answer = scenario['request']['answers'][0]
        self.assertTrue(any(s.get('question_id') == answer['question_id']
                            and s['raw_text'] == answer['text'] for s in accepted['statements']))
        for name, window in accepted['collection_windows'].items():
            self.assertEqual(window['snapshot_case_version'], accepted['case_version'])
            self.assertEqual(window['preview_count'], len(accepted[name]))
        op = OPENAPI['paths'][context['route']]['post']
        self.assertEqual(scenario['http_status'], 409)
        success = op['responses'][str(context['accepted_http_status'])]
        self.assertTrue(success['content']['application/json']['schema']['$ref'].endswith('/CustomerCaseView'))
        response = pointer(OPENAPI, op['responses'][str(scenario['http_status'])]['$ref'])
        self.assertTrue(response['content']['application/json']['schema']['$ref'].endswith('/ErrorEnvelope'))
        validator('ErrorEnvelope').validate(scenario['error'])
        self.assertEqual(scenario['error']['error']['code'], 'INVALID_STATE')
        self.assertIs(scenario['error']['error']['retryable'], False)
        self.assertIs(context['receipt_available'], False)
        self.assertEqual(context['expected_additional_mutations'], 0)
        self.assertEqual(context['expected_additional_scheduling'], 0)
        self.assertEqual(scenario['expected_provider_effects'], 0)
        assert_removed_text_absent(scenario)

    def test_retired_text_in_a_schema_valid_error_is_detected(self):
        scenario = replay_fixture()
        scenario['error']['error']['message'] = scenario['fixture_context']['accepted_response']['statements'][0]['raw_text']
        # Shape validity alone must not be treated as removal compliance.
        validator('ErrorEnvelope').validate(scenario['error'])
        with self.assertRaisesRegex(AssertionError, 'Removed text restored'):
            assert_removed_text_absent(scenario)

    def test_label_artifact_pending_and_complete_result_shapes(self):
        attempt = deepcopy(POSITIVE['operation-success']['value'])
        attempt['status'] = 'EXECUTING'
        attempt['provider_operation_id'] = 'provider-label-001'
        attempt.pop('result')
        validator('OperationAttempt').validate(attempt)
        # The internal trusted receipt is persisted separately, not invented
        # as a new public field or an incomplete success payload.
        result = {'type': 'GENERATE_LABEL', 'provider_label_id': 'provider-label-001',
                  'parcel_id': 'parcel-demo-001', 'label_evidence_id': 'evidence-label-001'}
        self.assertFalse(validator('OperationAttempt').is_valid({**attempt, 'result': result}))
        succeeded = {**attempt, 'status': 'SUCCEEDED', 'result': result}
        validator('OperationAttempt').validate(succeeded)
        del succeeded['result']['label_evidence_id']
        self.assertFalse(validator('OperationAttempt').is_valid(succeeded))
        self.assertFalse(validator('OperationAttempt').is_valid({**attempt, 'status': 'SUCCEEDED'}))


if __name__ == '__main__':
    unittest.main()
