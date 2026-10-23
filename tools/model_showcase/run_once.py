"""Trusted A1.06 showcase CLI: one advisory Coordinator extraction for one case.

docs/44; FR-002, NFR-003/007/008/009. Configuration comes only from the
environment (DATABASE_URL and the RETURNOPS_MODEL_* names in
returnops_api.model_settings); no argument accepts a key. It runs the showcase
worker once for an explicit case ID, with its bounded retries, using its own
in-process store: nothing is written to the database and the running API does
not see this result. The evidence JSON holds digests, codes, counts, tokens and
latency, never statement text, the summary text, the base URL or the key.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

PROFILE = 'a106-coordinator-showcase-evidence/v1'
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{2,79}')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Run the advisory A1.06 Coordinator showcase once for one case.')
    parser.add_argument('--case-id', required=True, help='Existing synthetic case ID.')
    parser.add_argument('--evidence', required=True, help='New local JSON evidence file; it must not exist yet.')
    args = parser.parse_args(argv)
    if _ID.fullmatch(args.case_id) is None:
        parser.error('Use a contract case ID.')
    target = Path(args.evidence)
    if target.exists() or not target.parent.is_dir() or target.suffix != '.json':
        parser.error('Use a new .json file in an existing directory.')
    return args


def evidence(result, case_id, settings, recorded_at):
    """Safe evidence only: no statement text, summary text, URL or key."""
    record = {'profile': PROFILE, 'recorded_at': recorded_at, 'case_id': case_id,
              'provider_id': settings.provider_id, 'model_id': settings.model_id, 'dialect': settings.dialect,
              'deadline_seconds': settings.deadline_seconds}
    from returnops_domain.coordinator_showcase import PROMPT_VERSION
    record['prompt_version'] = PROMPT_VERSION
    if result is None:
        record.update(outcome='NOT_ELIGIBLE', failure_code=None, attempts=0)
        return record
    record.update(input_digest=result.input_digest, outcome=result.outcome, failure_code=result.failure_code,
                  attempts=result.attempts, input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                  latency_ms=result.latency_ms, statement_count=result.statement_count,
                  redaction_counts=dict(result.redaction_counts))
    if result.facts is not None:
        facts = result.facts
        record['facts'] = {name: facts[name] for name in
                           ('issue_category', 'customer_requested_outcome', 'possible_basis', 'assessment_status')}
        record['facts'].update(line_item_count=len(facts['line_items']), summary_length=len(facts['summary']))
    return record


def main(argv=None):
    args = parse_args(argv)
    from returnops_api.database import build_engine
    from returnops_api.model_settings import ModelSettings
    from returnops_api.settings import Settings
    from returnops_domain.coordinator_showcase import CoordinatorAnnotationStore, CoordinatorShowcaseWorker
    model = ModelSettings.from_environment()
    engine = build_engine(Settings.from_environment())
    try:
        worker = CoordinatorShowcaseWorker(engine, model.transport(), CoordinatorAnnotationStore(),
                                           settings=model.worker_settings())
        results = worker.run_once(case_id=args.case_id)
    finally:
        engine.dispose()
    record = evidence(results[0] if results else None, args.case_id, model,
                      datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'))
    raw = (json.dumps(record, sort_keys=True, ensure_ascii=True, indent=2) + '\n').encode('ascii')
    with open(args.evidence, 'xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print('Showcase outcome: ' + record['outcome'] + (' (' + record['failure_code'] + ')' if record.get('failure_code') else '')
          + '; attempts ' + str(record['attempts']) + '. Evidence written; it holds no statement text or key.')
    return 0 if record['outcome'] == 'RECORDED' else 2


if __name__ == '__main__':
    failed = False
    code = 1
    try:
        code = main()
    except SystemExit:
        raise
    except Exception:
        failed = True
    if failed:
        print('Showcase run failed before an outcome was recorded; no key, URL or statement text is printed.')
    raise SystemExit(code)
