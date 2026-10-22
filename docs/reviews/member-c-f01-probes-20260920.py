"""Dated C review probes: artifact-only checks, not runtime or personal acceptance.

Run with the hash-locked Python interpreter from the pinned source checkout.
The caller must first verify source revision 3dd1ff637693a826990eee5712cfb239a3c3da7b.
The script hashes its three input artifacts; it does not independently verify Git.
No repository writes, network, database, LLM or provider calls are performed.
"""

from copy import deepcopy
from pathlib import Path
import hashlib
import sys
import unittest

SOURCE = Path(sys.argv.pop(1)).resolve()
EXPECTED = "3dd1ff637693a826990eee5712cfb239a3c3da7b"
sys.path.insert(0, str(SOURCE / "tests/contracts"))
from test_contract_v1 import POSITIVE, validator


def fixture(name):
    return deepcopy(POSITIVE[name]["value"])


class CReviewProbes(unittest.TestCase):
    def test_unversioned_and_synthetic_source_remain_explicit(self):
        passage = fixture("retrieval-result")["passages"][0]
        passage.update(source_version=None, is_synthetic=True,
                       source_uri="urn:returnops:synthetic-policy-001")
        validator("PolicyPassage").validate(passage)
        for field in ("source_version", "is_synthetic", "accessed_on", "location",
                      "content_sha256", "corpus_version", "retrieved_at"):
            changed = deepcopy(passage)
            del changed[field]
            self.assertFalse(validator("PolicyPassage").is_valid(changed), field)

    def test_no_match_is_not_a_transport_failure_or_automatic_pass(self):
        result = fixture("retrieval-result")
        result.update(status="NO_MATCH", passages=[])
        validator("RetrievalResult").validate(result)
        self.assertFalse(validator("RetrievalResult").is_valid(
            {**result, "status": "PROVIDER_FAILURE"}))
        self.assertFalse(validator("RiskReview").is_valid(result))

    def test_all_five_risk_outcome_fixtures_have_required_version_context(self):
        for name in ("risk-pass", "risk-warning", "risk-revise",
                     "risk-needs-information", "risk-escalate"):
            result = fixture(name)
            validator("RiskReview").validate(result)
            for field in ("case_id", "input_version", "proposal_id",
                          "proposal_version", "corpus_version"):
                changed = deepcopy(result)
                del changed[field]
                self.assertFalse(validator("RiskReview").is_valid(changed), (name, field))

    def test_risk_cannot_return_approval_or_command_authority(self):
        for field in ("approval_id", "command", "scope", "tool_command"):
            result = fixture("risk-pass")
            result[field] = "forbidden-synthetic-field"
            self.assertFalse(validator("RiskReview").is_valid(result), field)

    def test_risk_metadata_cannot_claim_assessment_role(self):
        result = fixture("risk-pass")
        result["model_run"]["role"] = "ASSESSMENT"
        self.assertFalse(validator("RiskReview").is_valid(result))

    def test_hidden_reasoning_is_not_a_declared_risk_input(self):
        request = fixture("risk-review-request")
        request["hidden_reasoning"] = "Synthetic forbidden extra input"
        self.assertFalse(validator("RiskReviewRequest").is_valid(request))

    def test_warning_requires_warning_and_forbids_block(self):
        result = fixture("risk-warning")
        result["findings"] = []
        self.assertFalse(validator("RiskReview").is_valid(result))
        result = fixture("risk-warning")
        result["findings"][0]["severity"] = "BLOCK"
        self.assertFalse(validator("RiskReview").is_valid(result))

    def test_internal_statement_and_attachment_capacity_is_not_lifetime_limit(self):
        request = fixture("risk-review-request")
        for field in ("statements", "attachments"):
            changed = deepcopy(request)
            changed[field] = [deepcopy(request[field][0]) for _ in range(100)]
            validator("RiskReviewRequest").validate(changed)
            changed[field].append(deepcopy(changed[field][0]))
            self.assertFalse(validator("RiskReviewRequest").is_valid(changed), field)


if __name__ == "__main__":
    print(f"C artifact-only review probes; expected source={EXPECTED}; caller verifies checkout; no runtime acceptance.", flush=True)
    for filename in ("schemas.json", "openapi.json", "examples.json"):
        content = (SOURCE / "contracts/v1" / filename).read_bytes()
        print(f"SHA256 contracts/v1/{filename} {hashlib.sha256(content).hexdigest()}", flush=True)
    unittest.main(verbosity=2)
