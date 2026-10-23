"""Same-key re-send rule used by the independent-process probes (REJECT, MANUAL_HANDLING,
REQUEST_REVISION and the original-key manual race); no I/O.

The HTTP boundary (docs/40) answers a DENIED result whose safe code is INTERNAL_ERROR
as 503, retryable, "keep the original request key", whatever the denial audit outcome
was (RECORDED, NOT_RECORDED or UNKNOWN). A caller that follows the client contract
therefore re-sends the same key. The rule is kept here, apart from the probe scripts,
so that offline tests can drive it with scripted results (issue #103, KAN-43). Probes
load this file by path, so installed-package runs (python -I) stay isolated.
"""
import time

MAX_ATTEMPTS = 3


def retryable_transient(result):
    """True only for the retryable 503 transient: DENIED, INTERNAL_ERROR, no receipt."""
    return result.status == 'DENIED' and result.safe_code == 'INTERNAL_ERROR' and result.receipt is None


def accept_with_same_key_retries(accept, max_attempts=MAX_ATTEMPTS, clock=time.monotonic):
    """Call accept() until it returns something other than the retryable transient.

    Returns (last result, attempts); every attempt records its status, safe code,
    denial-audit outcome and wall-clock duration, and nothing else."""
    if type(max_attempts) is not int or not 1 <= max_attempts <= MAX_ATTEMPTS:
        raise ValueError('max_attempts must be an integer from 1 to ' + str(MAX_ATTEMPTS))
    attempts = []
    result = None
    for number in range(1, max_attempts + 1):
        started = clock()
        result = accept()
        attempts.append({'attempt': number, 'status': result.status, 'safe_code': result.safe_code,
                         'audit': result.audit, 'duration_ms': round((clock() - started) * 1000)})
        if not retryable_transient(result):
            break
    return result, attempts
