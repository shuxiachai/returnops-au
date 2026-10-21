"""Public invented runner fixtures; no Gold labels, model or runtime calls."""
import asyncio
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
import unittest

from experiments.evaluation_candidate import DATA_ROLE, score_stub_run
from experiments.evaluation_candidate.runner import run_stub_cases


def case(case_id="synthetic-case"):
    return {"case_id": case_id, "input": {"message": "Invented development input."}}


def observation(case_id="synthetic-case"):
    return {"case_id": case_id, "status": "SUCCEEDED", "risk_outcome": "PASS",
            "present_field_ids": ["synthetic-fact"], "retrieved_passage_ids": [],
            "input_tokens": None, "output_tokens": None, "estimated_cost": None}


def reference(case_id="synthetic-case"):
    return {"case_id": case_id, "escalation_expected": False,
            "acceptable_outcomes": ["PASS"], "required_field_ids": ["synthetic-fact"]}


class StubAdapter:
    def __init__(self):
        self.calls = []

    async def __call__(self, invocation):
        self.calls.append(invocation)
        return observation(invocation.case_id)


class EvaluationRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def run_cases(self, cases=None, adapter=None, **kwargs):
        return await run_stub_cases(configuration=kwargs.pop("configuration", "B4_OFFLINE_STUB"),
                                    data_role=kwargs.pop("data_role", DATA_ROLE),
                                    cases=[case()] if cases is None else cases,
                                    adapter=adapter or StubAdapter(), **kwargs)

    async def test_runs_once_per_case_in_order_and_separately_scores(self):
        stub = StubAdapter()
        result = await self.run_cases([case("a"), case("b")], stub)
        self.assertEqual([item.case_id for item in stub.calls], ["a", "b"])
        self.assertEqual(result["adapter_call_count"], 2)
        self.assertEqual(result["retry_count"], 0)
        self.assertFalse(result["formal_performance_claim"])
        self.assertEqual(result["execution_mode"], "STUB_ADAPTER_REHEARSAL_ONLY")
        scored = score_stub_run(configuration="B4_OFFLINE_STUB", data_role=DATA_ROLE,
                                expectations=[reference("a"), reference("b")],
                                observations=result["observations"])
        self.assertEqual(scored["completion"]["numerator"], 2)
        self.assertIsNone(scored["usage_on_expected_cases"]["input_tokens"]["total"])

    async def test_all_cases_preflight_before_any_adapter_call(self):
        bad_lists = [[case(), case()], [case(), {"case_id": "late", "input": []}],
                     [case(), {**case("late"), "expectations": ["PASS"]}],
                     [case(str(i)) for i in range(101)], [case(), {"input": {}}]]
        for cases in bad_lists:
            stub = StubAdapter()
            with self.subTest(cases=len(cases)), self.assertRaises(ValueError):
                await self.run_cases(cases, stub)
            self.assertEqual(stub.calls, [])

    async def test_json_input_budget_and_non_json_values_rejected(self):
        recursive = {}
        recursive["again"] = recursive
        for payload in ({"text": "x" * (2 * 1024 * 1024)}, {"n": float("nan")},
                        {"n": float("inf")}, {1: "coerced-key"}, {"tuple": (1,)}, recursive):
            stub = StubAdapter()
            with self.subTest(kind=type(payload)), self.assertRaises(ValueError) as caught:
                await self.run_cases([{"case_id": "a", "input": payload}], stub)
            self.assertIsNone(caught.exception.__context__)
            self.assertEqual(stub.calls, [])

    async def test_whole_manifest_budget_not_per_case_budget(self):
        cases = [{"case_id": str(i), "input": {"text": "x" * (1024 * 1024)}} for i in range(2)]
        stub = StubAdapter()
        with self.assertRaises(ValueError):
            await self.run_cases(cases, stub)
        self.assertEqual(stub.calls, [])

    async def test_immutable_input_snapshot_survives_caller_mutation(self):
        cases = [case("a"), case("b")]
        before = deepcopy(cases)
        calls = []

        async def mutate(invocation):
            calls.append(invocation)
            with self.assertRaises(FrozenInstanceError):
                invocation.case_id = "forged"
            cases[1]["input"]["message"] = "changed after preflight"
            return observation(invocation.case_id)

        await self.run_cases(cases, mutate)
        self.assertEqual(json.loads(calls[1].input_json), before[1]["input"])
        self.assertNotIn("acceptable_outcomes", calls[0].input_json)

    async def test_exception_is_sanitised_counted_and_later_cases_continue(self):
        calls = []

        async def fails(invocation):
            calls.append(invocation.case_id)
            if invocation.case_id == "a":
                raise RuntimeError("private-provider-secret")
            return observation(invocation.case_id)

        result = await self.run_cases([case("a"), case("b")], fails)
        self.assertEqual(calls, ["a", "b"])
        self.assertNotIn("private-provider-secret", json.dumps(result))
        self.assertEqual(result["case_results"][0]["error_code"], "ADAPTER_FAILURE")
        self.assertEqual(result["observations"][0]["status"], "FAILED")
        self.assertIsNone(result["observations"][0]["input_tokens"])
        scored = score_stub_run(configuration="B4_OFFLINE_STUB", data_role=DATA_ROLE,
                                expectations=[reference("a"), reference("b")],
                                observations=result["observations"])
        self.assertEqual(scored["completion"], {"numerator": 1, "denominator": 2, "value": .5})

    async def test_timeout_and_swallowed_timeout_are_failures_without_retry(self):
        for swallow in (False, True):
            calls = []

            async def slow(invocation):
                calls.append(invocation)
                try:
                    await asyncio.sleep(1)
                except asyncio.CancelledError:
                    if not swallow:
                        raise
                    return observation(invocation.case_id)

            result = await self.run_cases(adapter=slow, timeout_seconds=.01)
            self.assertEqual(len(calls), 1)
            self.assertEqual(result["case_results"][0]["error_code"], "ADAPTER_TIMEOUT")
            self.assertEqual(result["observations"][0]["status"], "FAILED")

    async def test_invalid_or_cross_case_output_cannot_credit_another_case(self):
        for reply in (observation("b"), {**observation("a"), "approval": True}, None,
                      {**observation("a"), "input_tokens": True},
                      {**observation("a"), "estimated_cost": "NaN"}):
            async def malformed(invocation):
                return reply if invocation.case_id == "a" else observation("b")

            result = await self.run_cases([case("a"), case("b")], malformed)
            self.assertEqual(result["observations"][0], {"case_id": "a"})
            self.assertEqual(result["case_results"][0]["disposition"], "INVALID")
            scored = score_stub_run(configuration="B4_OFFLINE_STUB", data_role=DATA_ROLE,
                                    expectations=[reference("a"), reference("b")],
                                    observations=result["observations"])
            self.assertEqual(scored["dispositions"]["INVALID"], 1)
            self.assertEqual(scored["completion"]["numerator"], 1)
            self.assertEqual(scored["duplicate_case_ids"], [])

    async def test_b1_retrieval_is_invalid(self):
        async def retrieved(invocation):
            return {**observation(invocation.case_id), "retrieved_passage_ids": ["passage"]}

        result = await self.run_cases(adapter=retrieved, configuration="B1_OFFLINE_STUB")
        self.assertEqual(result["case_results"][0]["disposition"], "INVALID")

    async def test_valid_failed_observation_preserves_known_usage(self):
        reply = {**observation(), "status": "FAILED", "risk_outcome": None,
                 "present_field_ids": [], "input_tokens": 7, "output_tokens": 1,
                 "estimated_cost": "0.001"}

        async def failed(_):
            return reply

        result = await self.run_cases(adapter=failed)
        self.assertEqual(result["observations"], [reply])
        reply["input_tokens"] = 999
        self.assertEqual(result["observations"][0]["input_tokens"], 7)

    async def test_external_cancellation_propagates_without_partial_success(self):
        entered = asyncio.Event()

        async def pending(_):
            entered.set()
            await asyncio.sleep(10)

        task = asyncio.create_task(self.run_cases(adapter=pending))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_empty_input_calls_nothing_and_does_not_claim_performance(self):
        stub = StubAdapter()
        result = await self.run_cases([], stub)
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["adapter_call_count"], 0)
        self.assertFalse(result["formal_performance_claim"])
        self.assertEqual(stub.calls, [])

    async def test_swallowed_external_cancellation_stops_before_the_next_case(self):
        entered = asyncio.Event()
        calls = []

        async def swallowing(invocation):
            calls.append(invocation.case_id)
            entered.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                return observation(invocation.case_id)

        task = asyncio.create_task(self.run_cases([case("a"), case("b")], swallowing))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(calls, ["a"])

    async def test_invalid_scope_adapter_and_timeout_are_rejected(self):
        for config, role, timeout in (("B4", DATA_ROLE, 1), ("B4_OFFLINE_STUB", "GOLD", 1),
                                     ("B4_OFFLINE_STUB", DATA_ROLE, 0),
                                     ("B4_OFFLINE_STUB", DATA_ROLE, True),
                                     ("B4_OFFLINE_STUB", DATA_ROLE, float("nan")),
                                     ("B4_OFFLINE_STUB", DATA_ROLE, 61)):
            with self.subTest(config=config, timeout=timeout), self.assertRaises(ValueError):
                await self.run_cases(configuration=config, data_role=role, timeout_seconds=timeout)
        with self.assertRaises(ValueError):
            await self.run_cases(adapter=lambda _: observation())


if __name__ == "__main__":
    unittest.main()
