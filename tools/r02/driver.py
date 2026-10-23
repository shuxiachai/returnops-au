"""R.02 private end-to-end driver (design v2, route C); not installed.

One synthetic two-cups case goes Create Case -> Mock Order -> Fixed Proposal and
the controlled PASS receiver + risk stub -> Founder approval -> mock Return and
Label -> CORE_MOCK notification -> audit, with no LLM. A real API child
(api_child.py) serves the customer create and the Founder decision/read routes.
Intake, investigation and the fixed proposal run in this process for this one
case; the preview and the private execution chain run through their existing
private compositions after just-before-use grants (grants.py). The driver only
orchestrates: every guard, transition and mock effect comes from the Domain
services. UNKNOWN gets one same-key recover/reconcile call, DENIED stops, and
nothing is retried with a replacement key. run-receipt.json never holds tokens,
keys, credentials or local paths.

Demo mode (--identities, optionally --api-port and --keep-api) is for the live
demo only, not CI evidence: it reuses the identities written by
`returnops_api.demo provision` instead of provisioning r02_* identities, requires
the chosen store to have no case, no investigation service and no lifecycle
authority yet, and can keep the API child running on a fixed loopback port after
the receipt is written so the web frontend can read the case. Without these
options the behaviour is unchanged.

docs/08 R.02 and Gate 1; FR-009..FR-012; NFR-001/002/003/004/006/007/008;
docs/diagrams/member-a governed-execution-activity and exact-scope-sequence.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import sys
import time

import httpx
import jwt
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from returnops_api.database import EXPECTED_SCHEMA_REVISION
from returnops_api.private_approval_admission import compose_private_approval_admission
from returnops_api.private_execution_preparation import compose_private_execution_preparation
from returnops_api.private_label_artifact import compose_private_label_artifact
from returnops_api.private_label_execution import compose_private_label_execution
from returnops_api.private_notification import compose_private_notification
from returnops_api.private_pass_review import compose_private_pass_review
from returnops_api.private_preview import compose_private_preview
from returnops_api.private_return_execution import compose_private_return_execution
from returnops_api.private_return_label_bridge import compose_private_return_label_bridge
from returnops_api.security.authentication import AuthConfig
from returnops_api.settings import ConfigurationError, Settings, require_environment_database
from returnops_domain import customer_tables as old, investigation_tables as inv, lifecycle_tables as life
from returnops_domain.audit import identifier, timestamp
from returnops_domain.canonical import decode_document, digest
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.label_execution_sources import CONFIG as LABEL_CONFIG
from returnops_domain.label_execution_tables import ledger as label_ledger
from returnops_domain.notification_profile import CHANNEL
from returnops_domain.notification_tables import controls as notification_controls, facts as notification_facts
from returnops_domain.pass_review_sources import MODEL as REVIEW_MODEL, PROVIDER as REVIEW_PROVIDER
from returnops_domain.pass_scenario import MESSAGE
from returnops_domain.preview_profile import PROFILE
from returnops_domain.proposal_processor import FixedProposalProcessor, Intent
from returnops_domain.registry import TrustedRegistry
from returnops_domain.return_execution_sources import CONFIG as RETURN_CONFIG
from returnops_domain.return_execution_tables import ledger as return_ledger
from returnops_domain.wire import validate

import api_child
import catalogue
import demo_identities
import grants
import scenario

RECEIPT = 'run-receipt.json'
CATALOGUE_FILE = 'cups-catalogue.json'
API_LOG = 'api-child.log'
LOG_WITHHELD = b'R.02: API child log withheld because it contained private material.\n'
LOG_UNSCREENED = b'R.02: API child log withheld because it could not be screened.\n'
STORE = 'r02_synthetic_store'
CUSTOMER_ONE, CUSTOMER_TWO, FOUNDER = 'r02_customer_one', 'r02_customer_two', 'r02_founder'
PEOPLE = {'customer_one': CUSTOMER_ONE, 'customer_two': CUSTOMER_TWO, 'founder': FOUNDER}
ISSUER, AUDIENCE = 'returnops-r02-private', 'returnops-r02-customer'
SESSION_SECONDS = 899  # demo.py: issued now-1, expires now+899 (the 900 s registry window)
REASON = 'The Founder approves this retained simulated return.'
HISTORY_ORDER = ('DECISION', 'APPROVAL', 'OPERATION', 'NOTIFICATION')
MAX_PAGES = 100
LIMITATIONS = (
    'The API child is composed by the driver with create_app(...); demo.py serve and the image default CMD are not exercised.',
    'Intake, investigation and the fixed proposal run in the driver process for this case; the API process runs no worker.',
    'Docker evidence remains the existing image build and import probe; this run is not a deployment proof.',
    'The controlled PASS receiver + risk stub is the fixed risk result of Gate 1, not an independent risk assessment.',
    'A PASSED receipt or a green CI job is not human acceptance; R.02 still needs its designated reviewer.',
)
DEMO_LIMITATIONS = (
    'Demo mode: identities, sessions and the signing key come from returnops_api.demo provision (--identities); '
    'this run supports the live demo and is not CI evidence.',
    'Demo mode: the database may hold other cases (--allow-existing-data); only the chosen store was required to '
    'have no case, investigation service or lifecycle authority, and the store keeps the cups catalogue and the '
    'grants inserted by this run.',
)
KEEP_API_LIMITATION = ('Demo mode: the API child kept running after this receipt was written (--keep-api); '
                       'later requests to it are not part of this receipt.')
# Demo sessions come from demo.py (899 s from provisioning): at step 0 the
# remaining window must still cover the 300 s preview plus this margin.
DEMO_SESSION_MARGIN_SECONDS = 120
RESULT_FIELDS = ('safe_code', 'audit', 'work_id', 'operation_id', 'operation_state', 'provider_fact_status',
                 'preparation_id', 'artifact_work_id', 'label_evidence_id', 'event_id', 'source_record_id',
                 'notification_work_id', 'notification_id', 'case_version')
TOOLS_DIR = Path(__file__).resolve().parent


class Refused(Exception):
    """The environment is unsuitable; nothing was written to the database."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Stop(Exception):
    """A deliberate, recorded stop: DENIED, unexpected status or exhausted time budget."""

    def __init__(self, code, **detail):
        super().__init__(code)
        self.code, self.detail = code, detail


class ReceiptLeak(Exception):
    """The serialized receipt contained private material; it is not written."""


def _now():
    return datetime.now(timezone.utc)


def _text(value):
    return timestamp(value)


def approve_request(view, reason=REASON):
    """APPROVE body built only from the Founder CaseView (lifecycle_projection.py:58-63)."""
    proposal, preview = view.get('current_proposal'), view.get('action_preview')
    if view.get('status') != 'AWAITING_APPROVAL' or proposal is None or preview is None:
        raise Stop('APPROVAL_TARGET_UNAVAILABLE')
    return validate('FounderDecisionRequest', dict(
        expected_case_version=view['case_version'], proposal_id=proposal['proposal_id'],
        proposal_version=proposal['proposal_version'], decision='APPROVE', reason=reason,
        preview_id=preview['preview_id'], scope_fingerprint=preview['scope_fingerprint']))


def wrong_fingerprint(body):
    """The same request with another valid-shaped fingerprint (negative test only)."""
    other = '0' * 64 if body['scope_fingerprint'] != '0' * 64 else '1' * 64
    return {**body, 'scope_fingerprint': other}


def candidate_command(view):
    """The exact server-owned CREATE_RETURN command, scope.commands[0]."""
    return deepcopy(view['action_preview']['scope']['commands'][0])


def preview_checks(preview):
    """Simulated, zero-ceiling, mock-provider preview (preview_profile.PROFILE)."""
    scope = preview['scope']
    create, label = scope['commands']
    return dict(
        preview_environment_simulated=scope['environment'] == PROFILE['environment'] == 'SIMULATED',
        preview_amount_ceiling_zero=scope['amount_ceiling_minor'] == PROFILE['amount_ceiling_minor'] == 0,
        preview_currency_aud=scope['currency'] == PROFILE['currency'] == 'AUD',
        preview_allowlist_profile=scope['allowlist_version'] == PROFILE['version'],
        preview_return_provider_mock=(create['type'] == 'CREATE_RETURN'
            and create['provider_id'] == PROFILE['return_provider'] == RETURN_CONFIG['provider_id']),
        preview_label_provider_mock=(label['type'] == 'GENERATE_LABEL'
            and label['provider_id'] == PROFILE['label_provider'] == LABEL_CONFIG['provider_id']),
        preview_label_not_chargeable=label['parameters']['chargeable'] is False and PROFILE['chargeable'] is False)


def audit_links(items):
    """Every event names its predecessor's hash; the first names none."""
    previous = None
    for event in items:
        if event.get('previous_event_hash') != previous:
            return False
        previous = event.get('event_hash')
    return bool(items)


def audit_hashes(items):
    """Recompute audit.append_event's hash over the complete ordered pages."""
    try:
        return bool(items) and all(
            digest({'sequence': sequence, 'event': {k: v for k, v in event.items() if k != 'event_hash'}},
                   'audit/v1') == event['event_hash'] for sequence, event in enumerate(items, 1))
    except Exception:
        return False


def history_firsts(records):
    """First recorded_sequence of each kind, in HISTORY_ORDER."""
    return [min((row['recorded_sequence'] for row in records.get(kind, ())), default=None) for kind in HISTORY_ORDER]


def history_ordered(firsts):
    return None not in firsts and all(a < b for a, b in zip(firsts, firsts[1:]))


DEMO_STORE_CHECKS = (('store_case_rows_before', 'STORE_HAS_CASES'),
                     ('store_investigation_services_before', 'STORE_INVESTIGATION_CONFIGURED'),
                     ('store_lifecycle_authorities_before', 'STORE_AUTHORITIES_EXIST'),
                     ('pending_work_before', 'FOREIGN_PENDING_WORK'))


def clean_refusal(clean, demo=False):
    """Step 0 refusal code for the clean-environment counts, or None.

    Both modes: case rows need --allow-existing-data, and existing r02_* identities
    always refuse. Demo mode adds checks that --allow-existing-data never relaxes:
    the chosen store has no case, no investigation service and no lifecycle
    authority (configuring the cups catalogue would otherwise pause that store's
    builtin-catalogue investigations with CONFIGURATION_CHANGED, and the plain grant
    inserts would collide), and no case has PENDING or RUNNING intake or
    investigation work that the in-process processors could claim instead."""
    if clean['case_rows_before'] and not clean['allow_existing_data']:
        return 'EXISTING_CASE_ROWS'
    if clean['driver_principals_before']:
        return 'DRIVER_IDENTITIES_EXIST'
    if demo:
        for key, code in DEMO_STORE_CHECKS:
            if clean[key]:
                return code
    return None


def render_receipt(data, forbidden):
    """Serialize, refusing 'Bearer' and every forbidden value, raw or JSON-escaped."""
    content = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n'
    values = [value for value in forbidden if value]
    if 'Bearer' in content or any(value in content or json.dumps(value, ensure_ascii=True)[1:-1] in content
                                  for value in values):
        raise ReceiptLeak()
    return content


def write_receipt(path, data, forbidden):
    content = render_receipt(data, forbidden)
    with open(path, 'x', encoding='ascii', newline='\n') as output:
        output.write(content)


def screen_log(raw, credentials, locations):
    """API log bytes: None if any credential or 'Bearer' occurs; local directories
    are replaced by placeholders (longest first). Returns (bytes, replacements)."""
    if b'Bearer' in raw or any(value.encode('utf-8') in raw for value in credentials if value):
        return None, 0
    replaced = 0
    for placeholder, value in sorted(locations, key=lambda item: -len(item[1])):
        for form in dict.fromkeys((value, value.replace('\\', '\\\\'))):
            encoded = form.encode('utf-8')
            replaced += raw.count(encoded)
            raw = raw.replace(encoded, placeholder.encode('ascii'))
    return raw, replaced


def error_frames(error, limit=20):
    """tools/r02 frames of an unexpected error: basename, line, function only."""
    frames, trace = [], error.__traceback__
    while trace is not None:
        code = trace.tb_frame.f_code
        try:
            inside = Path(code.co_filename).resolve().parent == TOOLS_DIR
        except (OSError, ValueError):
            inside = False
        if inside:
            frames.append(dict(file=Path(code.co_filename).name, line=trace.tb_lineno, function=code.co_name))
        trace = trace.tb_next
    return frames[-limit:]


def source_trees():
    """Content digests of the code this run imported; relative paths only."""
    import returnops_api
    import returnops_domain
    roots = {'returnops_api': (Path(returnops_api.__file__).resolve().parent, '**/*'),
             'returnops_domain': (Path(returnops_domain.__file__).resolve().parent, '**/*'),
             'tools_r02': (TOOLS_DIR, '*.py')}
    result = {}
    for name, (root, pattern) in roots.items():
        files = sorted((path.relative_to(root).as_posix(), path) for path in root.glob(pattern)
                       if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc')
        lines = [relative + ' ' + hashlib.sha256(path.read_bytes()).hexdigest() for relative, path in files]
        result[name] = dict(files=len(lines), sha256=hashlib.sha256('\n'.join(lines).encode('utf-8')).hexdigest())
    return result


class Run:
    def __init__(self, output, *, keep_api_log=False, allow_existing_data=False, identities=None, api_port=None,
                 keep_api=False):
        self.output, self.keep_api_log, self.allow_existing_data = output, keep_api_log, allow_existing_data
        self.identities_dir, self.api_port, self.keep_api = identities, api_port, keep_api
        self.engine = self.private = self.http = self.auth = self.case = self.ids = None
        self.store, self.people, self.receipt_written = STORE, dict(PEOPLE), False
        self.receipt_withheld = False  # every receipt form contained private material; no file exists
        self.cleanup_failures, self.private_left = [], False  # cleanup that did not finish, for the CLI line
        # Credentials withhold a log and refuse a receipt; local directories are
        # replaced in a kept log and refused in a receipt.
        self.tokens, self.secrets, self.locations, self.step_number = {}, [], [], 0
        self.locate('<output>', output)
        if identities is not None:
            self.locate('<identities>', identities)
        try:
            self.locate('<home>', Path.home())
        except RuntimeError:
            pass
        options = dict(keep_api_log=keep_api_log, allow_existing_data=allow_existing_data)
        if api_port is not None:
            options['api_port'] = api_port
        limitations = list(LIMITATIONS)
        self.data = dict(format='r02-run-receipt/v1', work_package='R.02', gate='Gate 1 (no LLM)', route='C',
            requirements=['FR-009', 'FR-010', 'FR-011', 'FR-012', 'NFR-001', 'NFR-002', 'NFR-003', 'NFR-004',
                          'NFR-006', 'NFR-007', 'NFR-008'],
            models=['governed-execution-activity.puml', 'exact-scope-sequence.puml'],
            result='RUNNING', started_at=_text(_now()), options=options,
            steps=[], checks={}, produced_by={}, time_budget={}, limitations=limitations)
        if identities is not None:
            options.update(identities=True, keep_api=keep_api)
            limitations.extend(DEMO_LIMITATIONS + ((KEEP_API_LIMITATION,) if keep_api else ()))
            self.data['demo_mode'] = dict(enabled=True, evidence=False, identities_source='returnops_api.demo provision',
                                          keep_api=keep_api, api_port=api_port)

    # -- recording -----------------------------------------------------------------
    def locate(self, placeholder, path):
        for value in dict.fromkeys((str(path), str(Path(path).resolve()))):
            if len(value) >= 4:  # never a bare root such as '/'
                self.locations.append((placeholder, value))

    def forbidden(self):
        return self.secrets + [value for _, value in self.locations]

    def record(self, step, name, status, **details):
        self.step_number = step
        self.data['steps'].append(dict(step=step, name=name, status=status, at=_text(_now()), **details))

    def check(self, name, value):
        self.data['checks'][name] = bool(value)
        return bool(value)

    def result(self, step, name, value, **details):
        fields = {field: getattr(value, field) for field in RESULT_FIELDS if getattr(value, field, None) is not None}
        self.record(step, name, value.status, **fields, **details)

    def call(self, step, name, action, recover=None, *, ok, replayed=False, unknown=None, **details):
        """The primary call accepts only `ok`. UNKNOWN gets exactly one same-key
        recover/reconcile, whose answer may also be REPLAYED when `replayed`.
        DENIED and a remaining UNKNOWN stop; produced_by records the path."""
        value, path, accepted = action(), 'primary', set(ok)
        self.result(step, name, value, path=path, **details)
        if value.status == 'UNKNOWN' and recover is not None:
            value, path = recover(), 'recover'
            self.result(step, name + '_recover', value, path=path)
            accepted |= {'REPLAYED'} if replayed else set()
        if value.status == 'DENIED':
            raise Stop('DENIED', name=name, path=path, safe_code=getattr(value, 'safe_code', None))
        if value.status == 'UNKNOWN':
            raise Stop('UNKNOWN', name=name, path=path, **(unknown() if unknown else {}))
        if value.status not in accepted:
            raise Stop('UNEXPECTED_STATUS', name=name, path=path, status=value.status)
        self.data['produced_by'][name] = path
        return value

    def expect(self, step, name, response, status, *, error=None, label='OK', **details):
        body = None
        try:
            body = response.json()
        except ValueError:
            pass
        failure = body.get('error') if isinstance(body, dict) and isinstance(body.get('error'), dict) else {}
        code = failure.get('code')
        entry = dict(http_status=response.status_code, expected_http_status=status,
                     correlation_id=response.headers.get('x-correlation-id'))
        if code is not None:
            entry['error_code'] = code
        ok = response.status_code == status and (error is None or code == error)
        self.record(step, name, label if ok else 'UNEXPECTED', **entry, **details)
        if not ok:
            raise Stop('HTTP_UNEXPECTED_STATUS', name=name, http_status=response.status_code, error_code=code)
        return body

    # -- private helpers -----------------------------------------------------------
    def bearer(self, name):
        return {'Authorization': 'Bearer ' + self.tokens[name]}

    def head(self):
        with self.engine.connect() as connection:
            return dict(connection.execute(select(old.case_heads).where(
                old.case_heads.c.case_id == self.case)).mappings().one())

    def rows(self, table, *where):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(select(table).where(*where)).mappings()]

    def count(self, table, *where):
        with self.engine.connect() as connection:
            return connection.execute(select(func.count()).select_from(table).where(*where)).scalar_one()

    def audit_types(self):
        with self.engine.connect() as connection:
            bodies = connection.execute(select(old.audit.c.body).where(old.audit.c.case_id == self.case)
                                        .order_by(old.audit.c.sequence)).scalars().all()
        return [decode_document(bytes(body))['event_type'] for body in bodies]

    def decision_history(self):
        return self.count(old.history, old.history.c.case_id == self.case,
                          old.history.c.kind.in_(('DECISION', 'APPROVAL')))

    def grant(self, step, name, function):
        self.record(step, 'grant_' + name, 'INSERTED', rows=function(self.engine, self.store))

    def founder_case(self, step):
        return self.expect(step, 'founder_case_read', self.http.get('/v1/founder/cases/' + self.case,
                           headers=self.bearer('founder')), 200)

    def pages(self, path, query):
        items, cursor = [], None
        for page in range(1, MAX_PAGES + 1):
            params = dict(query, limit=100, **({'cursor': cursor} if cursor else {}))
            response = self.http.get(path, params=params, headers=self.bearer('founder'))
            if response.status_code != 200:
                self.expect(8, 'founder_page_read', response, 200, query=dict(query))
            body = response.json()
            items.extend(body['items'])
            cursor = body.get('next_cursor')
            if not cursor:
                return items, page
        raise Stop('PAGINATION_UNBOUNDED', query=dict(query))

    def notification_state(self):
        """Read-only diagnostic as notification_helpers.ready() reads it."""
        try:
            controls = self.rows(notification_controls, notification_controls.c.case_id == self.case)
            state = self.rows(life.state, life.state.c.case_id == self.case)
        except SQLAlchemyError:
            return dict(notification_diagnostic='UNAVAILABLE')
        return dict(notification_controls=[{name: row[name] for name in ('notification_work_id', 'state', 'outcome')}
                                           for row in controls],
                    lifecycle_notification_work_id=state[0]['notification_work_id'] if state else None)

    def only_this_case(self, table):
        foreign = self.count(table, table.c.case_id != self.case, table.c.state.in_(('PENDING', 'RUNNING')))
        if foreign:
            raise Stop('FOREIGN_PENDING_WORK', table=table.name, rows=foreign)

    def require_session(self, seconds=0):
        if (self.session_expires - _now()).total_seconds() <= seconds:
            raise Stop('SESSION_BUDGET_EXHAUSTED', needed_seconds=seconds)

    def require_preview(self, name):
        if _now() >= self.preview_expires:
            raise Stop('PREVIEW_WINDOW_EXPIRED', before=name)

    # -- steps ---------------------------------------------------------------------
    def load_identities(self):
        """Demo mode: the demo.py provision files; their secrets are screened from here on."""
        try:
            ids = demo_identities.load(self.identities_dir)
        except demo_identities.IdentitiesError as error:
            raise Refused(error.code) from None
        self.secrets.extend(ids.secret_values())
        self.ids, self.store, self.people = ids, ids.store_id, dict(ids.people)
        self.data['identities'] = dict(store_id=self.store, **self.people)

    def registered(self):
        """Demo mode, read-only: the files' principals and sessions are the registered rows."""
        ids = self.ids
        principal_ids = tuple(ids.people.values())
        session_ids = tuple(row['session_id'] for row in ids.sessions.values())
        principals = {row['principal_id']: row for row in self.rows(old.principals,
                      old.principals.c.principal_id.in_(principal_ids))}
        sessions = {row['session_id']: row for row in self.rows(old.sessions, old.sessions.c.session_id.in_(session_ids))}
        expected = {row['principal_id']: row for row in ids.principals.values()}
        if set(principals) != set(principal_ids) or set(sessions) != set(session_ids) or any(
                principals[key][name] != row[name] for key, row in expected.items()
                for name in ('role', 'store_id', 'enabled')) or any(
                sessions[row['session_id']][name] != row[name] for row in ids.sessions.values()
                for name in ('principal_id', 'issued_at', 'not_before', 'expires_at', 'revoked')):
            raise Refused('IDENTITIES_NOT_REGISTERED')

    def environment(self):
        if self.identities_dir is not None:
            self.load_identities()
        try:
            raw = Settings.from_environment().database_url.get_secret_value()
        except ConfigurationError:
            raise Refused('DATABASE_URL_REJECTED') from None
        self.secrets.extend(value for value in (raw, make_url(raw).password) if value)
        try:
            require_environment_database(raw)
        except ConfigurationError:
            raise Refused('DATABASE_URL_REJECTED') from None
        self.engine = create_engine(raw, hide_parameters=True, echo=False, pool_size=4, max_overflow=4,
            connect_args={'connect_timeout': 3, 'options': '-c statement_timeout=10000'})
        env = dict(python_version=platform.python_version(), python_implementation=platform.python_implementation(),
                   platform=platform.platform(terse=True), expected_schema_revision=EXPECTED_SCHEMA_REVISION,
                   source_trees=source_trees())
        commit = os.environ.get('GITHUB_SHA', '')
        if re.fullmatch(r'[0-9a-f]{40}', commit):
            env['ci_commit'] = commit
        self.data['environment'] = env
        try:
            with self.engine.connect() as connection:
                env['server_version_num'] = int(connection.execute(text('SHOW server_version_num')).scalar_one())
                env['server_version'] = str(connection.execute(text('SHOW server_version')).scalar_one())
        except SQLAlchemyError:
            raise Refused('DATABASE_UNAVAILABLE') from None
        if not 170000 <= env['server_version_num'] < 180000:
            raise Refused('POSTGRESQL_17_REQUIRED')
        try:
            with self.engine.connect() as connection:
                heads = connection.execute(text('SELECT version_num FROM alembic_version ORDER BY version_num')).scalars().all()
        except SQLAlchemyError:
            raise Refused('ALEMBIC_VERSION_UNAVAILABLE') from None
        env['alembic_heads'] = list(heads)
        if list(heads) != [EXPECTED_SCHEMA_REVISION]:
            raise Refused('ALEMBIC_HEAD_MISMATCH')
        cases = self.count(old.case_heads)
        known = self.count(old.principals, old.principals.c.principal_id.in_(tuple(PEOPLE.values())))
        clean = self.data['clean_environment'] = dict(case_rows_before=cases, driver_principals_before=known,
                                                      allow_existing_data=self.allow_existing_data)
        if self.ids is not None:
            busy = ('PENDING', 'RUNNING')
            clean.update(
                store_case_rows_before=self.count(old.case_heads, old.case_heads.c.store_id == self.store),
                store_investigation_services_before=self.count(inv.services, inv.services.c.store_id == self.store),
                store_lifecycle_authorities_before=self.count(life.authorities, life.authorities.c.store_id == self.store),
                pending_work_before=self.count(old.intake_work, old.intake_work.c.state.in_(busy))
                + self.count(inv.work, inv.work.c.state.in_(busy)),
                session_seconds_remaining=int(self.ids.expires_at - time.time()))
        code = clean_refusal(clean, demo=self.ids is not None)
        if code:
            raise Refused(code)
        if self.ids is not None:
            self.registered()
            if clean['session_seconds_remaining'] <= PROFILE['ttl_seconds'] + DEMO_SESSION_MARGIN_SECONDS:
                raise Refused('IDENTITY_SESSION_WINDOW_TOO_SHORT')
        self.record(0, 'environment', 'OK')

    def provision(self):
        self.step_number = 1
        if self.ids is None:
            now = int(time.time())
            principals = [dict(principal_id=principal, role='FOUNDER' if name == 'founder' else 'CUSTOMER',
                               store_id=STORE, enabled=True) for name, principal in PEOPLE.items()]
            sessions = {name: dict(session_id=identifier('session'), principal_id=principal, issued_at=now - 1,
                                   not_before=now - 1, expires_at=now + SESSION_SECONDS, revoked=False)
                        for name, principal in PEOPLE.items()}
            key = secrets.token_bytes(48)
            self.auth = AuthConfig(ISSUER, AUDIENCE, key, leeway_seconds=0)
            self.tokens = {name: jwt.encode(dict(iss=ISSUER, aud=AUDIENCE, sub=row['principal_id'],
                           jti=row['session_id'], iat=row['issued_at'], nbf=row['not_before'], exp=row['expires_at']),
                           key, algorithm='HS256') for name, row in sessions.items()}
            self.secrets.extend([*self.tokens.values(), base64.b64encode(key).decode('ascii'), key.hex()])
            issued, expires = now - 1, now + SESSION_SECONDS
        else:
            # Demo mode: the registered demo.py identities; nothing is provisioned here.
            ids = self.ids
            self.auth = AuthConfig(ids.issuer, ids.audience, ids.signing_key, leeway_seconds=0)
            self.tokens = dict(ids.tokens)
            issued, expires = ids.issued_at, ids.expires_at
        self.founder_bearer = 'Bearer ' + self.tokens['founder']
        self.session_expires = datetime.fromtimestamp(expires, timezone.utc)
        self.data['time_budget'].update(session_issued_at=_text(datetime.fromtimestamp(issued, timezone.utc)),
                                        session_expires_at=_text(self.session_expires))
        self.private = api_child.private_directory()  # demo mode: only the API child log lives here
        self.locate('<private>', self.private)
        if self.ids is None:
            # Credentials are written before registration, as demo.py does.
            self.auth_file = api_child.write_auth_file(self.private, ISSUER, AUDIENCE, key)
            TrustedRegistry(self.engine).provision(principals, list(sessions.values()))
        else:
            self.auth_file = self.ids.auth_file  # read by the API child's load_private_auth_config()
        owner = self.people['customer_one']
        self.cups = catalogue.load(self.store, owner)
        (self.output / CATALOGUE_FILE).write_bytes(catalogue.document_bytes(self.store, owner))
        metadata = self.cups.metadata
        self.data['identities'] = dict(store_id=self.store, **self.people)
        self.data['catalogue'] = dict(file=CATALOGUE_FILE, provider_id=metadata.provider_id,
            dataset_version=metadata.dataset_version, provider_version=metadata.provider_version,
            dataset_sha256=metadata.dataset_sha256)
        rows = (grants.order_investigation(self.engine, self.store, self.cups)
                + grants.fixed_proposal(self.engine, self.store))
        self.record(1, 'provision', 'OK', grants=rows)

    def customer_create(self):
        self.step_number = 3
        key = 'r02-upload-' + secrets.token_hex(8)
        evidence = self.expect(3, 'stage_evidence', self.http.post('/v1/evidence',
            files={'file': ('synthetic-cups.pdf', scenario.evidence_pdf(), 'application/pdf')},
            headers={**self.bearer('customer_one'), 'Idempotency-Key': key}), 201, idempotency_key=key)
        validate('EvidenceAttachment', evidence)
        key = 'r02-create-' + secrets.token_hex(8)
        request = dict(original_message=MESSAGE, requested_outcome='RETURN', order_reference=catalogue.ORDER_REFERENCE,
                       evidence_ids=[evidence['evidence_id']])
        view = self.expect(3, 'create_case', self.http.post('/v1/cases', json=request,
            headers={**self.bearer('customer_one'), 'Idempotency-Key': key}), 201, idempotency_key=key,
            evidence_sha256=evidence['sha256'], evidence_size_bytes=evidence['size_bytes'])
        self.case = view['case_id']
        self.data['case_id'] = self.case
        # Observed, not asserted: with no API worker the case waits untouched.
        status = self.head()['status']
        intake = [row['state'] for row in self.rows(old.intake_work, old.intake_work.c.case_id == self.case)]
        untouched = status == 'SUBMITTED' and intake == ['PENDING']
        self.record(3, 'api_process_ran_no_worker', 'OK' if untouched else 'UNEXPECTED', case_status=status,
                    intake_work_states=intake)
        if not self.check('api_process_ran_no_worker', untouched):
            raise Stop('API_WORKER_SUSPECTED', case_status=status, intake_work_states=intake)

    def processors(self):
        self.step_number = 4
        self.only_this_case(old.intake_work)
        progressed = IntakeProcessor(self.engine).run_once()
        self.record(4, 'intake', 'PROGRESSED' if progressed else 'NO_PROGRESS', case_status=self.head()['status'])
        if not progressed:
            raise Stop('INTAKE_NO_PROGRESS')
        self.only_this_case(inv.work)
        progressed = InvestigationProcessor(self.engine, catalogue=self.cups).run_once()
        status = self.head()['status']
        self.record(4, 'investigation', 'PROGRESSED' if progressed else 'NO_PROGRESS', case_status=status)
        if not progressed or status != 'POLICY_ASSESSMENT':
            raise Stop('INVESTIGATION_INCOMPLETE', case_status=status)
        processor = FixedProposalProcessor(self.engine, build=scenario.build_positive)
        intent = processor.prepare(self.case)
        if type(intent) is not Intent:
            self.result(4, 'fixed_proposal_prepare', intent)
            raise Stop('PROPOSAL_NOT_PREPARED', status=intent.status)
        # process(prepare(case)) for this case only; resolve() keeps the original work identity.
        self.call(4, 'fixed_proposal', lambda: processor.process(intent), lambda: processor.resolve(intent),
                  ok={'ACCEPTED'})
        view = self.founder_case(4)
        if view['status'] != 'RISK_REVIEW' or 'current_proposal' not in view:
            raise Stop('RISK_REVIEW_NOT_VISIBLE', case_status=view['status'])
        run = view['current_proposal']['model_run']
        self.check('proposal_no_live_model', run['model_id'] == 'fixture-no-live-model'
                   and run['input_tokens'] == run['output_tokens'] == 0)

    def review_and_preview(self):
        self.step_number = 5
        version = self.head()['case_version']
        self.grant(5, 'review', grants.review)
        reviewer = scenario.ControlledPassReviewer()
        receiver = compose_private_pass_review(self.engine, reviewer)
        key, correlation = 'r02-review-' + secrets.token_hex(8), identifier('r02_review')
        self.call(5, 'controlled_pass_review', lambda: receiver.accept(self.case, version, key, correlation),
                  lambda: receiver.recover(self.case, version, key), ok={'ACCEPTED'},
                  idempotency_key=key, correlation_id=correlation)
        self.check('controlled_reviewer_called_once', len(reviewer.calls) == 1)
        self.grant(5, 'preview_and_approval', grants.preview_and_approval)
        self.require_session(PROFILE['ttl_seconds'])
        preview = compose_private_preview(self.engine)
        key, correlation = 'r02-preview-' + secrets.token_hex(8), identifier('r02_preview')
        accepted = self.call(5, 'action_preview', lambda: preview.accept(self.case, version + 1, key, correlation),
                             lambda: preview.recover(self.case, version + 1, key), ok={'ACCEPTED'},
                             idempotency_key=key, correlation_id=correlation)
        action = accepted.receipt['action_preview']
        self.preview_expires = datetime.fromisoformat(action['scope']['expires_at'])
        self.data['time_budget'].update(preview_ttl_seconds=PROFILE['ttl_seconds'], preview_accepted_at=_text(_now()),
                                        preview_expires_at=action['scope']['expires_at'])
        view = self.founder_case(5)
        if view.get('action_preview') != action:
            raise Stop('PREVIEW_NOT_VISIBLE', case_status=view['status'])
        self.view = view
        for name, value in preview_checks(action).items():
            self.check(name, value)
        run = view['current_review']['model_run']
        self.check('review_no_live_model', run['provider_id'] == REVIEW_PROVIDER and run['model_id'] == REVIEW_MODEL
                   and run['input_tokens'] == run['output_tokens'] == 0)
        self.record(5, 'awaiting_approval', 'OK', case_version=view['case_version'],
                    preview_id=action['preview_id'], scope_fingerprint=action['scope_fingerprint'])

    def decide(self, body, key, name='founder'):
        return self.http.post('/v1/founder/cases/' + self.case + '/decisions', json=body,
                              headers={**self.bearer(name), 'Idempotency-Key': key})

    def decisions(self):
        self.step_number = 6
        body = approve_request(self.view)
        self.data['approve_request'] = {k: body[k] for k in ('expected_case_version', 'proposal_id', 'proposal_version',
                                                             'preview_id', 'scope_fingerprint')}
        # Negative first: a customer bearer is refused before any Domain service.
        before, audits = self.head(), self.audit_types()
        key = 'r02-negative-customer-' + secrets.token_hex(8)
        self.expect(6, 'negative_customer_token', self.decide(body, key, 'customer_one'), 403, error='FORBIDDEN',
                    idempotency_key=key)
        self.check('negative_customer_token_no_write', self.head() == before and self.audit_types() == audits)
        # A wrong fingerprint under another key: no business change, one denial audit.
        self.require_preview('negative_wrong_fingerprint')
        key = 'r02-negative-scope-' + secrets.token_hex(8)
        self.expect(6, 'negative_wrong_fingerprint', self.decide(wrong_fingerprint(body), key), 409,
                    error='INVALID_STATE', idempotency_key=key)
        after = self.head()
        self.check('negative_wrong_fingerprint_no_business_change', self.decision_history() == 0 and all(
            after[name] == before[name] for name in ('case_version', 'input_version', 'status', 'history_sequence')))
        self.check('negative_wrong_fingerprint_one_denial_audit',
                   self.audit_types()[len(audits):] == ['FOUNDER_APPROVE_DENIED'])
        # The real approval; its key is the original_approval_key for every later service.
        self.approval_key = key = 'r02-approve-' + secrets.token_hex(8)
        self.require_preview('approve')
        response, path = self.decide(body, key), 'primary'
        if response.status_code == 503:  # retryable INTERNAL_ERROR: one re-POST, same key and body
            self.expect(6, 'approve', response, 503, error='INTERNAL_ERROR', label='UNKNOWN', path=path,
                        idempotency_key=key)
            self.require_preview('approve_retry')
            response, path = self.decide(body, key), 'recover'
        receipt = validate('DecisionReceipt', self.expect(6, 'approve' if path == 'primary' else 'approve_recover',
                                                          response, 202, path=path, idempotency_key=key))
        self.data['produced_by']['approve'] = path
        replay = self.expect(6, 'approve_replay', self.decide(body, key), 202, idempotency_key=key)
        self.check('approve_replay_identical_receipt', replay == receipt)
        self.receipt_version = receipt['case_version']
        head = self.head()
        work = self.rows(life.work, life.work.c.case_id == self.case, life.work.c.purpose == 'EXECUTION')
        self.check('approved_once', head['status'] == 'APPROVED' and receipt['case_version'] == head['case_version']
                   == body['expected_case_version'] + 1 and 'approval_id' in receipt)
        self.check('execution_work_pending_after_approval', len(work) == 1 and work[0]['state'] == 'PENDING'
                   and work[0]['epoch'] == 0 and all(work[0][name] is None for name in
                   ('claim_id', 'claimed_case_version', 'lease_expires_at', 'authority_revision')))
        self.check('zero_effects_after_approval', self.count(life.effects, life.effects.c.case_id == self.case) == 0)
        self.check('no_execution_grant_after_approval', self.count(life.authorities, life.authorities.c.store_id == self.store,
                   life.authorities.c.purpose == 'EXECUTION', life.authorities.c.enabled.is_(True)) == 0)
        if not work:
            raise Stop('EXECUTION_WORK_MISSING')
        self.execution_work_id = work[0]['work_id']
        self.record(6, 'approval_snapshot', 'OK', case_version=head['case_version'], approval_id=receipt['approval_id'],
                    decision_id=receipt['decision_id'])

    def execution_chain(self):
        self.step_number = 7
        case, work, key, bearer = self.case, self.execution_work_id, self.approval_key, self.founder_bearer
        command, version = candidate_command(self.view), self.receipt_version
        self.grant(7, 'execution', grants.execution)
        self.require_preview('admission')
        self.require_session()
        checked = compose_private_approval_admission(self.engine, self.auth, bearer).check(
            case, version, work, key, command)
        self.result(7, 'approval_admission', checked)  # read-only diagnostic; prepare re-proves everything
        if checked.status == 'DENIED':
            raise Stop('DENIED', name='approval_admission', safe_code=checked.safe_code)
        self.require_preview('prepare')
        preparation = compose_private_execution_preparation(self.engine, self.auth, bearer)
        correlation = identifier('r02_preparation')
        self.call(7, 'prepare', lambda: preparation.prepare(case, version, work, key, command, correlation),
                  lambda: preparation.recover_preparation(case, version, work, key, command),
                  ok={'PREPARED'}, replayed=True, correlation_id=correlation)
        self.grant(7, 'create_return', grants.create_return)
        self.check('prepare_keeps_case_version', self.head()['case_version'] == version)
        self.require_preview('create_return')
        returns = compose_private_return_execution(self.engine, self.auth, bearer)
        correlation = identifier('r02_return')
        created = self.call(7, 'create_return',
            lambda: returns.execute_prepared_create_return(case, version, work, key, command, correlation),
            lambda: returns.reconcile_create_return(case, work, key, correlation),
            ok={'COMMITTED'}, replayed=True, correlation_id=correlation)
        if created.operation_state != 'SUCCEEDED':
            raise Stop('RETURN_NOT_SUCCEEDED', operation_state=created.operation_state)
        self.require_preview('return_source')
        bridge = compose_private_return_label_bridge(self.engine, self.auth, bearer)
        version, correlation = self.head()['case_version'], identifier('r02_bridge')
        self.call(7, 'return_source', lambda: bridge.accept_return_source(case, version, work, key, correlation),
                  lambda: bridge.recover_return_source(case, work, key, correlation),
                  ok={'ACCEPTED'}, replayed=True, correlation_id=correlation, case_version_before=version)
        self.grant(7, 'generate_label', grants.generate_label)
        self.require_preview('generate_label')
        labels = compose_private_label_execution(self.engine, self.auth, bearer)
        version, correlation = self.head()['case_version'], identifier('r02_label')
        label = self.call(7, 'generate_label',
            lambda: labels.execute_accepted_label(case, version, work, key, correlation),
            lambda: labels.reconcile_label(case, work, key, correlation),
            ok={'COMMITTED'}, replayed=True, correlation_id=correlation, case_version_before=version)
        if label.operation_state != 'EXECUTING' or not label.artifact_work_id:
            raise Stop('LABEL_NOT_CONFIRMED', operation_state=label.operation_state)
        self.grant(7, 'label_artifact', grants.label_artifact)
        self.require_preview('label_artifact')
        artifacts = compose_private_label_artifact(self.engine, self.auth, bearer)
        correlation = identifier('r02_artifact')
        artifact = self.call(7, 'label_artifact',
            lambda: artifacts.complete_label_artifact(case, label.artifact_work_id, key, correlation),
            lambda: artifacts.recover_label_artifact(case, label.artifact_work_id, key, correlation),
            ok={'COMMITTED'}, replayed=True, correlation_id=correlation)
        completed = _now()
        budget = self.data['time_budget']
        budget.update(artifact_completed_at=_text(completed), preview_to_artifact_seconds=round(
            (completed - self.preview_expires).total_seconds() + PROFILE['ttl_seconds'], 3))
        if not self.check('within_preview_window', completed < self.preview_expires):
            raise Stop('PREVIEW_WINDOW_EXPIRED', before='notification')
        if artifact.operation_state != 'SUCCEEDED':
            raise Stop('LABEL_ARTIFACT_NOT_SUCCEEDED', operation_state=artifact.operation_state)
        self.grant(7, 'notification', grants.notification)
        notifications = compose_private_notification(self.engine, self.auth, bearer)
        version = self.head()['case_version']
        # produce_return has no recover method: UNKNOWN stops with a read-only view of the
        # control and lifecycle pointer (no second producer call, no send).
        produced = self.call(7, 'notification_produce', lambda: notifications.produce_return(case, version),
                             ok={'READY'}, unknown=self.notification_state, case_version_before=version)
        self.call(7, 'notification_send', lambda: notifications.send(produced.notification_work_id),
                  lambda: notifications.reconcile(produced.notification_work_id), ok={'SENT'})
        finished = _now()
        budget.update(chain_finished_at=_text(finished))
        self.check('within_session', finished < self.session_expires)

    def read_back(self):
        self.step_number = 8
        view = self.founder_case(8)
        root = '/v1/founder/cases/' + self.case
        records, pages = {}, {}
        for kind in HISTORY_ORDER:
            records[kind], pages[kind] = self.pages(root + '/history', {'kind': kind})
        events, pages['AUDIT'] = self.pages(root + '/audit', {})
        types = [event['event_type'] for event in events]
        firsts = history_firsts(records)
        self.record(8, 'read_back', 'OK', case_status=view['status'], case_version=view['case_version'],
                    history_counts={kind: len(rows) for kind, rows in records.items()},
                    history_first_sequence=dict(zip(HISTORY_ORDER, firsts)), pages=pages,
                    audit_events=len(events), audit_event_types=types)
        self.check('final_status_completed', view['status'] == 'COMPLETED')
        self.check('history_order_decision_approval_operation_notification', history_ordered(firsts))
        self.check('audit_chain_linked', audit_links(events))
        self.check('audit_chain_hashes_recomputed', audit_hashes(events))
        self.check('audit_one_approve_denial', types.count('FOUNDER_APPROVE_DENIED') == 1)
        mock = {RETURN_CONFIG['provider_id'], LABEL_CONFIG['provider_id']}
        operations = [row['content'] for row in records['OPERATION'] if 'content' in row]
        self.check('operations_mock_providers', operations and all(item['provider_id'] in mock for item in operations))
        latest = max(records['NOTIFICATION'], key=lambda row: row['recorded_sequence'], default={}).get('content', {})
        self.check('notification_sent_return_created', latest.get('status') == 'SENT'
                   and latest.get('outcome') == 'RETURN_CREATED')
        returned = self.rows(return_ledger, return_ledger.c.store_id == self.store)
        self.check('return_ledger_mock_provider', len(returned) == 1 and returned[0]['status'] == 'SUCCEEDED'
                   and returned[0]['provider_id'] == RETURN_CONFIG['provider_id']
                   and returned[0]['config_id'] == RETURN_CONFIG['config_id'])
        labelled = self.rows(label_ledger, label_ledger.c.case_id == self.case)
        self.check('label_ledger_mock_provider', len(labelled) == 1 and labelled[0]['status'] == 'SUCCEEDED'
                   and labelled[0]['provider_id'] == LABEL_CONFIG['provider_id']
                   and labelled[0]['config_id'] == LABEL_CONFIG['config_id'])
        controls = self.rows(notification_controls, notification_controls.c.case_id == self.case)
        facts = self.rows(notification_facts, notification_facts.c.case_id == self.case)
        self.check('notification_channel_core_mock', CHANNEL == 'CORE_MOCK' and len(controls) == 1
                   and controls[0]['channel'] == CHANNEL and len(facts) == 1 and facts[0]['channel'] == CHANNEL
                   and facts[0]['status'] == 'SENT')

    # -- run -----------------------------------------------------------------------
    def execute(self):
        try:
            self.environment()
            self.provision()
            self.step_number = 2
            log = self.private / API_LOG  # raw child output stays private until finish() screens it
            with api_child.api_process(self.auth_file, log, **self.port_option()) as api:
                self.record(2, 'api_child', 'READY', loopback=api.url.startswith('http://127.0.0.1:'),
                            composition=api.composition, environment_names=list(api.environment_names))
                try:
                    with httpx.Client(base_url=api.url, timeout=30, trust_env=False) as http:
                        self.http = http
                        self.customer_create()
                        self.processors()
                        self.review_and_preview()
                        self.decisions()
                        self.execution_chain()
                        self.read_back()
                    checks = self.data['checks']
                    self.data['result'] = 'PASSED' if checks and all(checks.values()) else 'FAILED'
                except Exception as error:
                    if not self.keep_api:
                        raise  # default: the child is stopped before the failure is recorded, as before
                    self.conclude(error)
                if self.keep_api:  # demo mode: receipt first, then keep the child until Ctrl+C
                    self.data['finished_at'] = _text(_now())
                    self.publish()
                    if not self.receipt_withheld:  # no demo hold without a published receipt
                        self.hold(api)
        except KeyboardInterrupt as error:
            self.conclude(error)
        except Exception as error:
            self.conclude(error)
        finally:
            self.finish()
        # R02-C-03: without a written (or deliberately withheld) receipt the run is not evidence.
        return self.data['result'] if self.receipt_written else 'FAILED'

    def port_option(self):
        return {} if self.api_port is None else dict(port=self.api_port)

    def conclude(self, error):
        """Record a failure: Refused, Stop, ApiChildError or an unexpected exception."""
        if isinstance(error, Refused):
            self.data.update(result='REFUSED', stop=dict(code=error.code, step=self.step_number))
        elif isinstance(error, Stop):
            self.data.update(result='FAILED', stop=dict(code=error.code, step=self.step_number, **error.detail))
        elif isinstance(error, api_child.ApiChildError):
            self.data.update(result='FAILED', stop=dict(code=str(error), step=self.step_number))
        elif isinstance(error, KeyboardInterrupt):
            self.data.update(result='FAILED', stop=dict(code='INTERRUPTED', step=self.step_number))
        else:  # no message or local value: they may carry SQL or connection detail
            self.data.update(result='FAILED', stop=dict(code='UNEXPECTED_ERROR', step=self.step_number,
                                                        error_type=type(error).__name__,
                                                        error_frames=error_frames(error)))

    def hold(self, api):
        """Demo mode --keep-api: the receipt is written; print how to reach and stop the API."""
        print('R.02 demo mode: driver result ' + self.data['result'] + ' (see ' + RECEIPT + ').')
        if self.case:
            print('Case ID: ' + self.case)
        print('The API child keeps running at ' + api.url + ' (loopback only; no worker; Founder decision route on).')
        print('Open the web frontend against it (tools/r02/README.md, "Demo mode"). Press Ctrl+C to stop the API.')
        sys.stdout.flush()
        reason = api_child.hold(api)
        print('R.02 demo mode: stopping the API child (' + ('Ctrl+C' if reason == 'INTERRUPTED' else
                                                          'it exited by itself') + ').')

    def finish(self):
        """Each cleanup stage runs on its own: a failure is recorded as a code and the later stages
        (log screening, private removal, receipt) still run. Codes, never messages, reach the receipt."""
        failures = []

        def stage(code, function):
            try:
                function()
            except Exception:
                failures.append(code)

        if not self.receipt_written:
            self.data['finished_at'] = _text(_now())
        if self.engine is not None:
            stage('ENGINE_DISPOSE_FAILED', self.engine.dispose)
        if self.keep_api_log:
            stage('API_LOG_SCREEN_FAILED', self.publish_api_log)
        removed = None
        if self.private is not None:
            def remove():
                nonlocal removed
                shutil.rmtree(self.private, ignore_errors=True)
                removed = not self.private.exists()
            stage('PRIVATE_DIRECTORY_REMOVE_FAILED', remove)
        # C's review of #116: a business PASSED is not an all-clean run, so the CLI line reports these too.
        self.cleanup_failures = list(failures)
        self.private_left = self.private is not None and removed is not True
        if self.receipt_written:  # --keep-api: the receipt was written before the API stopped
            if self.private is not None and removed is not True:
                print('R.02 demo mode: the private temporary directory could not be removed.', file=sys.stderr)
            if failures:
                print('R.02 demo mode: cleanup stages failed after the receipt: ' + ', '.join(failures) + '.',
                      file=sys.stderr)
            return
        if self.private is not None:
            self.data['private_directory_removed'] = removed is True
        if failures:
            self.data['cleanup_failures'] = failures
        if self.private_left:
            held = 'signing key, tokens and raw API log' if self.ids is None else 'raw API log'
            print('R.02: the private temporary directory (r02-private-* in the system temporary directory) could not '
                  'be removed; it may still hold the ' + held + ' of this run. Delete it by hand.', file=sys.stderr)
        try:
            self.publish()
        except Exception:
            print('R.02: the run receipt could not be written.', file=sys.stderr)

    def cleanup_note(self):
        """Suffix for the CLI result line: cleanup that did not finish is never reported as an all-clean run."""
        parts = list(self.cleanup_failures)
        if self.private_left:
            parts.append('the private temporary directory was not removed')
        return '; cleanup did not finish: ' + ', '.join(parts) if parts else ''

    def publish_api_log(self):
        """--keep-api-log: screen the private raw log and publish only the screened copy or a note."""
        raw = None if self.private is None else self.private / API_LOG
        if raw is None or not raw.exists():
            return
        target = self.output / API_LOG
        try:
            screened, replaced = screen_log(raw.read_bytes(), self.secrets, self.locations)
        except Exception:
            self.data['api_log'] = 'WITHHELD'
            target.write_bytes(LOG_UNSCREENED)
            raise
        if screened is None:
            target.write_bytes(LOG_WITHHELD)
            self.data['api_log'] = 'WITHHELD'
        else:
            target.write_bytes(screened)
            self.data.update(api_log=API_LOG, api_log_directories_replaced=replaced)

    def publish(self):
        """Write run-receipt.json once; a form that would contain a forbidden value is replaced by a smaller one.
        receipt_written becomes true only after the file is written (or every form was withheld on purpose,
        which also sets receipt_withheld: no file exists); any other write failure propagates and leaves it false."""
        stop = self.data.get('stop', {}).get('code')
        reduced = dict(format='r02-run-receipt/v1', work_package='R.02', result='FAILED',
                       stop=dict(code='RECEIPT_REDACTION_FAILED', original_result=self.data['result'],
                                 original_stop=stop), finished_at=self.data['finished_at'])
        bare = dict(format='r02-run-receipt/v1', result='FAILED', stop=dict(code='RECEIPT_REDACTION_FAILED'))
        for index, candidate in enumerate((self.data, reduced, bare)):
            try:
                write_receipt(self.output / RECEIPT, candidate, self.forbidden())
            except ReceiptLeak:
                continue
            self.receipt_written = True
            if index:
                self.data = candidate
            return
        self.receipt_written = True
        self.receipt_withheld = True
        self.data = bare
        print('R.02: the run receipt was withheld because every form contained private material.', file=sys.stderr)


def parser():
    value = argparse.ArgumentParser(description='R.02 private end-to-end driver: one synthetic cups case, no LLM, '
        'mock effects only. Reads DATABASE_URL (a returnops_f02* database already at alembic head).')
    value.add_argument('--output', required=True, help='Directory for run-receipt.json and cups-catalogue.json.')
    value.add_argument('--keep-api-log', action='store_true', help='Keep the API child log in the output directory.')
    value.add_argument('--allow-existing-data', action='store_true',
                       help='Run even if case rows already exist (the default requires a clean database).')
    demo = value.add_argument_group('demo mode (live demo only, not CI evidence)')
    demo.add_argument('--identities', metavar='DIR',
                      help='Reuse auth.json and sessions.json written by "python -m returnops_api.demo provision '
                           '--private-dir DIR" instead of provisioning r02_* identities. The store must have no case, '
                           'investigation service or lifecycle authority yet (provision it without '
                           '--order-investigation and --fixed-proposal); other stores\' cases need '
                           '--allow-existing-data.')
    demo.add_argument('--api-port', type=int, metavar='N',
                      help='Start the API child on 127.0.0.1:N (1024-65535) instead of an ephemeral port.')
    demo.add_argument('--keep-api', action='store_true',
                      help='After the chain completes or fails, write the receipt and keep the API child running '
                           'until Ctrl+C. Requires --identities; not combinable with --keep-api-log.')
    return value


def parse_args(argv=None):
    value = parser()
    args = value.parse_args(argv)
    if args.api_port is not None and not 1024 <= args.api_port <= 65535:
        value.error('--api-port must be an unprivileged port between 1024 and 65535.')
    if args.keep_api and args.identities is None:
        value.error('--keep-api requires --identities (the default identities are never shown, so no one could '
                    'sign in to a kept API).')
    if args.keep_api and args.keep_api_log:
        value.error('--keep-api and --keep-api-log cannot be combined: the receipt is written before the API stops.')
    return args


def main(argv=None):
    args = parse_args(argv)
    output = Path(args.output).resolve()
    identities = None if args.identities is None else Path(args.identities).resolve()
    if identities is not None and (output == identities or identities in output.parents
                                   or output in identities.parents):
        print('Refusing an output directory that contains, or is inside, the private identities directory.',
              file=sys.stderr)
        return 2
    output.mkdir(parents=True, exist_ok=True)
    if (output / RECEIPT).exists():
        print('Refusing to overwrite an earlier run receipt; choose a new output directory.', file=sys.stderr)
        return 2
    run = Run(output, keep_api_log=args.keep_api_log, allow_existing_data=args.allow_existing_data,
              identities=identities, api_port=args.api_port, keep_api=args.keep_api)
    result = run.execute()
    if run.receipt_withheld:
        line = 'R.02 driver result: FAILED (the run receipt was withheld because it contained private material)'
    elif run.receipt_written:
        line = 'R.02 driver result: ' + result + ' (see ' + RECEIPT + ')'
    else:
        line = 'R.02 driver result: FAILED (the run receipt could not be written)'
    print(line + run.cleanup_note() + '.')
    return {'PASSED': 0, 'REFUSED': 2}.get(result, 1)


if __name__ == '__main__':
    raise SystemExit(main())
