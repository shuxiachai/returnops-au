"""Bounded E.09 adapter rehearsal using public synthetic inputs only.

There is no separate expectations/Gold-label argument; callers must supply only
public synthetic inputs. The injected adapter is a trusted, cooperative Python
callable, NOT a sandboxed or proven offline
program. This module supplies no network client, credential or operation port.
An adapter must enforce its own network deadline if later separately approved;
this stub runner is not the real B1/B4 runner or a delivery-gate result.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from inspect import iscoroutinefunction
import json
from time import monotonic
from typing import Awaitable, Callable

from .scoring import CONFIGURATIONS, DATA_ROLE, _identifier, _observation


_MAX_CASES = 100
_MAX_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class StubInvocation:
    """Immutable invocation without a label channel; input_json is untrusted data."""

    configuration: str
    case_id: str
    input_json: str
    timeout_seconds: float


def _json_value(value):
    # json.dumps otherwise coerces integer dictionary keys to strings, changing
    # the caller's input. Accept only literal JSON-compatible Python values.
    if type(value) is dict:
        return all(type(key) is str and _json_value(item) for key, item in value.items())
    if type(value) is list:
        return all(_json_value(item) for item in value)
    return value is None or type(value) in (str, int, float, bool)


def _snapshot(value):
    try:
        if not _json_value(value):
            raise ValueError("unsupported JSON value")
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
        if len(raw.encode("utf-8")) > _MAX_BYTES:
            raise ValueError("oversize")
        return json.loads(raw)
    except (ValueError, TypeError, OverflowError, RecursionError):
        pass
    # Do not retain JSON/input text or a prior exception in __context__.
    raise ValueError("INVALID_STUB_DATA") from None


def _prepare(cases, configuration, data_role, adapter, timeout_seconds):
    is_async = iscoroutinefunction(adapter) or iscoroutinefunction(getattr(adapter, "__call__", None))
    if (type(configuration) is not str or configuration not in CONFIGURATIONS
            or type(data_role) is not str or data_role != DATA_ROLE or not is_async
            or type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 60):
        raise ValueError("INVALID_STUB_CONFIGURATION")
    if type(cases) is not list or len(cases) > _MAX_CASES:
        raise ValueError("INVALID_STUB_CASES")
    snapshot = _snapshot(cases)  # One 2 MiB budget for the entire input manifest.
    seen = set()
    invocations = []
    for case in snapshot:
        if (type(case) is not dict or set(case) != {"case_id", "input"}
                or not _identifier(case["case_id"]) or case["case_id"] in seen
                or type(case["input"]) is not dict):
            raise ValueError("INVALID_STUB_CASES")
        seen.add(case["case_id"])
        invocations.append(StubInvocation(
            configuration, case["case_id"],
            json.dumps(case["input"], ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False),
            timeout_seconds,
        ))
    return invocations


def _failed(case_id):
    return {"case_id": case_id, "status": "FAILED", "risk_outcome": None,
            "present_field_ids": [], "retrieved_passage_ids": [],
            "input_tokens": None, "output_tokens": None, "estimated_cost": None}


async def run_stub_cases(*, configuration: str, data_role: str, cases: list[dict],
                         adapter: Callable[[StubInvocation], Awaitable[dict]],
                         timeout_seconds: float = 30) -> dict:
    """Call once per prevalidated case, retaining failures in scorer denominators.

    Pass returned observations to score_stub_run separately, with separately
    held *public synthetic fixture* expectations. The runner does not receive
    them. Caller-declared data_role cannot prove the provenance of input data.
    Cancellation from the caller propagates; it never returns a partial report
    falsely presented as a completed run. A cooperative adapter is required:
    asyncio cannot stop blocking Python or an adapter ignoring cancellation.
    """
    invocations = _prepare(cases, configuration, data_role, adapter, timeout_seconds)
    observations, case_results = [], []
    for invocation in invocations:
        error_code = None
        task = asyncio.current_task()
        cancelling_before = task.cancelling()
        began = monotonic()
        try:
            reply = await asyncio.wait_for(adapter(invocation), timeout=timeout_seconds)
        except TimeoutError:
            error_code = "ADAPTER_TIMEOUT"
        except Exception:
            error_code = "ADAPTER_FAILURE"
        # wait_for's deadline restores its own cancellation count. A caller's
        # cancellation must still win if a cooperative adapter swallows the
        # delivered CancelledError and returns a seemingly valid observation.
        if task.cancelling() > cancelling_before:
            raise asyncio.CancelledError
        if monotonic() - began > timeout_seconds:
            error_code = "ADAPTER_TIMEOUT"
        if error_code:
            observation = _failed(invocation.case_id)
            disposition = "FAILED"
        else:
            try:
                observation = _snapshot(reply)
                if type(observation) is not dict or observation.get("case_id") != invocation.case_id:
                    raise ValueError("wrong case")
                _observation(observation, configuration)
                disposition = observation["status"]
            except (ValueError, TypeError, OverflowError, RecursionError):
                # A deliberately invalid, sanitised sentinel preserves INVALID
                # accounting without retaining an arbitrary adapter response.
                observation = {"case_id": invocation.case_id}
                disposition, error_code = "INVALID", "INVALID_ADAPTER_OUTPUT"
        observations.append(observation)
        case_results.append({"case_id": invocation.case_id, "disposition": disposition,
                             "error_code": error_code})
    return {
        "data_role": DATA_ROLE, "configuration": configuration,
        "execution_mode": "STUB_ADAPTER_REHEARSAL_ONLY", "formal_performance_claim": False,
        "adapter_isolation": "TRUSTED_COOPERATIVE_CALLABLE_NOT_SANDBOXED",
        "expected_case_count": len(invocations), "adapter_call_count": len(invocations),
        "retry_count": 0, "observations": observations, "case_results": case_results,
    }
