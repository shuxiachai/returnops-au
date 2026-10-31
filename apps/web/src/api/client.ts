import {
  CreateCaseRequest,
  ClarificationRequest,
  CustomerCaseView,
  CustomerCaseSummary,
  CustomerCaseSummaryList,
  CaseSummary,
  CaseList,
  CaseView,
  FounderDecisionRequest,
  DecisionReceipt,
  AnalyticsQuery,
  AnalyticsSnapshot,
  AiReplyDraft,
  AiTriage,
  AiWeeklySummary,
  AuditEvent,
  AuditPage,
  HistoryRecord,
  SessionPrincipal,
  EvidenceAttachment,
  CustomerHistoryKind,
  FounderHistoryKind,
  ErrorEnvelope,
} from '../types/domain';
import { generateIdempotencyKey } from '../utils/idempotency';
import { decisionStateRefusal } from './decisionStates';
import {
  MOCK_CUSTOMER_CASES,
  MOCK_FOUNDER_SUMMARIES,
  MOCK_FOUNDER_CASE_VIEWS,
  MOCK_AUDIT_EVENTS,
  MOCK_ANALYTICS,
} from './mockData';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export class ApiError extends Error {
  public status: number;
  public code?: string;
  public correlationId?: string;
  public details?: unknown;
  // The contract's ErrorEnvelope.retryable (#122 item 7). It was never read, so the
  // customer was told to retry requests the server had already marked permanent.
  // Undefined means the reply carried no envelope (a lost response or a proxy 500).
  public retryable?: boolean;

  constructor(
    status: number,
    message: string,
    code?: string,
    correlationId?: string,
    details?: unknown,
    retryable?: boolean
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
    this.details = details;
    this.retryable = retryable;
  }
}

// "[CODE] message", or the message alone when the error has no code, so no
// screen ever shows "[undefined]".
export function formatApiError(err: ApiError): string {
  return err.code ? `[${err.code}] ${err.message}` : err.message;
}

// A request that got no usable reply (offline, connection refused, an unreadable
// body) carries this code, so it never reaches the page as "undefined".
export const NETWORK_ERROR = 'NETWORK_ERROR';

function networkError(err: unknown, fallback: string): ApiError {
  return new ApiError(0, err instanceof Error ? err.message : fallback, NETWORK_ERROR);
}

// Storage keys
const TOKEN_KEY = 'returnops_auth_token';
const MOCK_MODE_KEY = 'returnops_mock_mode';
// Shared by every tab of this browser; App follows a change made in another tab.
export const SHARED_STORAGE_KEYS = { token: TOKEN_KEY, sampleData: MOCK_MODE_KEY } as const;
const ACTIVE_ROLE_KEY = 'returnops_active_role';

export function getStoredToken(): string {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setStoredToken(token: string) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function isMockMode(): boolean {
  const item = localStorage.getItem(MOCK_MODE_KEY);
  if (item === null) return true; // Default to Mock Mode on first load for zero-setup demo
  return item === 'true';
}

// True only once the sample data was chosen on purpose. The app opens the sign-in
// page otherwise, including on a first visit with nothing stored (31 October 2026).
export function sampleDataChosen(): boolean {
  return localStorage.getItem(MOCK_MODE_KEY) === 'true';
}

export function setMockMode(enabled: boolean) {
  localStorage.setItem(MOCK_MODE_KEY, enabled ? 'true' : 'false');
}

export function getActiveRole(): 'CUSTOMER' | 'FOUNDER' {
  return (localStorage.getItem(ACTIVE_ROLE_KEY) as 'CUSTOMER' | 'FOUNDER') || 'CUSTOMER';
}

export function setActiveRole(role: 'CUSTOMER' | 'FOUNDER') {
  localStorage.setItem(ACTIVE_ROLE_KEY, role);
}

// Session state (#111 item 1). Demo sessions last 15 minutes, so a 401 can arrive
// on any page; every request reports it here and the header and banner follow.
export type SessionState = 'ok' | 'rejected';
let sessionState: SessionState = 'ok';
const sessionListeners = new Set<(state: SessionState) => void>();

export function getSessionState(): SessionState {
  return sessionState;
}

export function subscribeSessionState(listener: (state: SessionState) => void): () => void {
  sessionListeners.add(listener);
  return () => {
    sessionListeners.delete(listener);
  };
}

function setSessionState(next: SessionState) {
  if (next === sessionState) return;
  sessionState = next;
  sessionListeners.forEach((listener) => listener(next));
}

export function clearSessionRejection() {
  setSessionState('ok');
}

function trackResponseStatus(status: number) {
  if (status === 401) setSessionState('rejected');
  else if (status >= 200 && status < 300) setSessionState('ok');
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  requireIdempotency = false,
  idempotencyKey?: string,
  trackSession = true
): Promise<T> {
  const headers = new Headers(options.headers || {});
  const token = getStoredToken();

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  if (idempotencyKey) {
    headers.set('Idempotency-Key', idempotencyKey);
  } else if (requireIdempotency && !headers.has('Idempotency-Key')) {
    headers.set('Idempotency-Key', generateIdempotencyKey());
  }

  const url = `${BASE_URL}${path}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    const correlationId = response.headers.get('X-Correlation-ID') || undefined;
    if (trackSession) trackResponseStatus(response.status);

    if (!response.ok) {
      let errEnvelope: ErrorEnvelope | null = null;
      try {
        errEnvelope = await response.json();
      } catch {
        // Not a JSON error (e.g. Vite proxy 500 when backend is offline)
      }

      let msg = errEnvelope?.error?.message;
      if (!msg) {
        // No error envelope, so the reply came from a proxy (Vite, Caddy), not from the
        // API. No address is named: on the one-origin deployment the API sits behind this
        // page's own address. An HTTP/2 reply carries no status text.
        msg =
          response.status >= 500
            ? `The service is not answering right now (HTTP ${response.status}). Try again in a moment.`
            : `HTTP ${response.status}${response.statusText ? `: ${response.statusText}` : ''}`;
      }
      const code = errEnvelope?.error?.code || `HTTP_${response.status}`;
      throw new ApiError(
        response.status,
        msg,
        code,
        correlationId,
        errEnvelope?.error?.details,
        errEnvelope?.error?.retryable
      );
    }

    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    // Network failure / server offline
    throw networkError(err, 'Network error or backend unavailable');
  }
}

// -------------------------------------------------------------
// Customer API (UC-01 & UC-01E)
// -------------------------------------------------------------

export async function getSession(): Promise<SessionPrincipal> {
  if (isMockMode()) {
    const role = getActiveRole();
    return {
      principal_id: role === 'FOUNDER' ? 'founder_demo' : 'customer_demo_one',
      role,
      store_id: 'store_demo',
      enabled: true,
      session_id: 'session_mock_live',
    };
  }
  return request<SessionPrincipal>('/v1/session');
}

/**
 * Checks a pasted token against the live server before it is saved (#111 item 1):
 * the token is sent only in this request's Authorization header, nothing is
 * stored, and a refusal does not change the current session state.
 */
export async function verifySessionToken(token: string): Promise<SessionPrincipal> {
  return request<SessionPrincipal>(
    '/v1/session',
    { headers: { Authorization: `Bearer ${token}` } },
    false,
    undefined,
    false
  );
}

// Customer self-registration and password sign-in (31 October 2026). Served only by an
// API started with `demo.py serve --accounts`; neither route is in contract v1, and the
// access key stays the fallback. The answer carries a new session token; nothing is
// stored here, and a refusal does not change the current session state.
export interface PasswordSession {
  access_token: string;
  token_type: 'Bearer';
  expires_in: number;
  principal_id: string;
  role: SessionPrincipal['role'];
}

function postCredentials(path: string, username: string, password: string): Promise<PasswordSession> {
  return request<PasswordSession>(
    path,
    {
      method: 'POST',
      // An explicit empty value keeps a saved token from being sent along.
      headers: { 'Content-Type': 'application/json', Authorization: '' },
      body: JSON.stringify({ username, password }),
    },
    false,
    undefined,
    false
  );
}

export function signInWithPassword(username: string, password: string): Promise<PasswordSession> {
  return postCredentials('/v1/auth/login', username, password);
}

export function registerCustomerAccount(username: string, password: string): Promise<PasswordSession> {
  return postCredentials('/v1/auth/register', username, password);
}

export async function stageEvidence(
  file: File,
  description?: string,
  idempotencyKey?: string
): Promise<EvidenceAttachment> {
  if (isMockMode()) {
    const evidenceId = 'ev_' + Date.now().toString(36);
    return {
      evidence_id: evidenceId,
      filename: file.name,
      media_type: file.type || 'application/octet-stream',
      size_bytes: file.size,
      sha256: 'mock_sha256_' + Date.now(),
      status: 'STAGED',
      description: description || undefined,
      created_at: new Date().toISOString(),
      content_path: `/v1/evidence/${evidenceId}/content`,
    };
  }

  const formData = new FormData();
  formData.append('file', file);
  if (description) {
    formData.append('description', description);
  }

  const headers = new Headers();
  headers.set('Idempotency-Key', idempotencyKey || generateIdempotencyKey('ev_idem'));
  const token = getStoredToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/v1/evidence`, {
      method: 'POST',
      headers,
      body: formData,
    });
  } catch (err: unknown) {
    throw networkError(err, 'Network error or backend unavailable');
  }
  trackResponseStatus(res.status);

  if (!res.ok) {
    const correlationId = res.headers.get('X-Correlation-ID') || undefined;
    let errEnv: ErrorEnvelope | null = null;
    try {
      errEnv = await res.json();
    } catch {
      // ignore
    }
    throw new ApiError(
      res.status,
      errEnv?.error?.message || 'Failed to upload evidence',
      errEnv?.error?.code || `HTTP_${res.status}`,
      correlationId,
      undefined,
      errEnv?.error?.retryable
    );
  }

  const data = await res.json();
  return data;
}

export function getEvidenceContentUrl(evidenceId: string): string {
  return `${BASE_URL}/v1/evidence/${encodeURIComponent(evidenceId)}/content`;
}

export async function downloadEvidence(evidenceId: string, fallbackFilename = 'evidence.bin'): Promise<void> {
  if (isMockMode()) {
    const blob = new Blob([`Mock evidence binary content for ${evidenceId}`], { type: 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fallbackFilename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return;
  }

  const token = getStoredToken();
  const headers = new Headers();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/v1/evidence/${encodeURIComponent(evidenceId)}/content`, {
      headers,
    });
  } catch (err: unknown) {
    throw networkError(err, 'Network error or backend unavailable');
  }
  trackResponseStatus(res.status);

  if (!res.ok) {
    let errEnv: ErrorEnvelope | null = null;
    try {
      errEnv = await res.json();
    } catch {
      // ignore
    }
    const code = errEnv?.error?.code || `HTTP_${res.status}`;
    const msg = errEnv?.error?.message || `Failed to download evidence (HTTP ${res.status}: ${res.statusText})`;
    throw new ApiError(res.status, msg, code);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fallbackFilename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Fixture hashes for Mock Mode: a 64-hex value derived from the event body. It is
// not a SHA-256 digest and nothing in the UI claims it is (the audit panel says the
// view does not recompute or verify the chain).
const ZERO_HASH = '0'.repeat(64);

function fixtureHash(input: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  const word = (hash >>> 0).toString(16).padStart(8, '0');
  return word.repeat(8).slice(0, 64);
}

// Case ids in the order they were first paged, so an index cursor stays stable.
let MOCK_QUEUE_ORDER: string[] = [];

// Mock Mode's stand-in for the intake worker: the first read after a lodgement decides
// whether the purchase context is missing and, if so, attaches the question set the
// server's investigation_admission.issue_questions would issue.
const MOCK_PENDING_INTAKE = new Set<string>();
// The lodgement's order reference, kept beside the case as the server keeps it.
const MOCK_LODGED_REFERENCES = new Map<string, string | undefined>();

function runMockIntake(c: CustomerCaseView): void {
  if (!MOCK_PENDING_INTAKE.delete(c.case_id)) return;
  const reference = MOCK_LODGED_REFERENCES.get(c.case_id);
  // intake_processor.py:57: purchase context is needed only when the case has neither a
  // usable reference nor any bound material.
  const hasMaterial = c.evidence.length > 0;
  if (hasMaterial || hasAnyReference(reference)) {
    c.status = 'UNDER_INVESTIGATION';
    return;
  }
  c.status = 'AWAITING_INFORMATION';
  c.case_version += 1;
  c.updated_at = new Date().toISOString();
  c.clarification = {
    question_set_id: 'qset_' + Date.now().toString(36),
    input_version: c.input_version,
    questions: [
      {
        question_id: 'q_auto_ref',
        text: 'Provide an order reference (at most 120 characters), or use the alternative purchase-context question.',
        reason: 'No order is verified. Either an order reference or alternative purchase material can continue the investigation.',
      },
      {
        question_id: 'q_auto_alt',
        text: 'Alternatively, describe the purchase or attach supporting evidence; you do not also need an order reference.',
        reason: 'Alternative material will be retained for further verification; it does not itself verify an order.',
      },
    ],
  };
}

// The intake worker's own test (intake_processor.py:92) is emptiness only; the 120
// character cap belongs to answer admission (investigation_admission.py:53).
function hasAnyReference(reference?: string): boolean {
  return (reference ?? '').trim().length > 0;
}

export async function createCase(req: CreateCaseRequest, idempotencyKey?: string): Promise<CustomerCaseView> {
  if (isMockMode()) {
    const newCaseId = 'case_demo_' + Math.floor(100 + Math.random() * 900);
    const snapshotId = 'snap_' + Date.now().toString(36);
    const newCase: CustomerCaseView = {
      case_id: newCaseId,
      case_version: 1,
      input_version: 1,
      status: 'SUBMITTED',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      // The contract's CustomerStatement carries no order_reference and no evidence_ids;
      // the reference is kept in MOCK_LODGED_REFERENCES, as the server keeps it.
      statements: [
        {
          statement_id: 'stmt_' + Date.now().toString(36),
          kind: 'ORIGINAL',
          raw_text: req.original_message,
          submitted_at: new Date().toISOString(),
          requested_outcome: req.requested_outcome,
        },
      ],
      evidence: (req.evidence_ids || []).map((id, idx) => ({
        evidence_id: id,
        filename: `uploaded_evidence_${idx + 1}.png`,
        media_type: 'image/png',
        size_bytes: 245000,
        // The contract requires both of these on a BOUND attachment.
        sha256: 'a'.repeat(64),
        case_id: newCaseId,
        status: 'BOUND' as const,
        created_at: new Date().toISOString(),
        content_path: `/v1/evidence/${id}/content`,
      })),
      // The server always sends both windows with a case view, and the contract allows
      // no others. One snapshot id for the pair, as history.py mints one per snapshot.
      collection_windows: {
        statements: {
          kind: 'STATEMENT' as const,
          snapshot_id: snapshotId,
          snapshot_case_version: 1,
          total_records: 1,
          preview_count: 1,
          unavailable_count: 0,
          truncated: false,
          start_cursor: 'cur_' + snapshotId,
        },
        evidence: {
          kind: 'EVIDENCE' as const,
          snapshot_id: snapshotId,
          snapshot_case_version: 1,
          total_records: (req.evidence_ids || []).length,
          preview_count: (req.evidence_ids || []).length,
          unavailable_count: 0,
          truncated: false,
          start_cursor: 'cur_' + snapshotId,
        },
      },
    };
    // The receipt is always SUBMITTED version 1 -- the server asserts exactly that
    // (customer_service.py:258, raising INTERNAL_ERROR otherwise). The intake worker
    // adds the question set afterwards, so the first read after creation attaches it.
    newCase.status = 'SUBMITTED';
    MOCK_CUSTOMER_CASES[newCaseId] = newCase;
    MOCK_PENDING_INTAKE.add(newCaseId);
    MOCK_LODGED_REFERENCES.set(newCaseId, req.order_reference);
    // A copy: the store object is mutated by the intake on the next read.
    return { ...newCase };
  }

  return request<CustomerCaseView>(
    '/v1/cases',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    },
    true,
    idempotencyKey
  );
}

export async function getCustomerCase(caseId: string): Promise<CustomerCaseView> {
  if (isMockMode()) {
    const c = MOCK_CUSTOMER_CASES[caseId];
    if (!c) {
      throw new ApiError(404, `Case ${caseId} not found in mock store`, 'NOT_FOUND');
    }
    runMockIntake(c);
    // A copy, so the receipt object the page already holds does not change under it.
    return { ...c };
  }
  return request<CustomerCaseView>(`/v1/cases/${encodeURIComponent(caseId)}`);
}

// The signed-in customer's own cases, newest first (31 October 2026; outside contract v1).
// The server offers it only with password sign-in; without that it answers 404 or 405.
export const MY_CASES_LIMIT = 20;
const EXCERPT_CHARACTERS = 120;

export async function listMyCases(): Promise<CustomerCaseSummaryList> {
  if (isMockMode()) {
    // The same summary the server builds: the start of the customer's own first words.
    const items = Object.values(MOCK_CUSTOMER_CASES)
      .map((c): CustomerCaseSummary => {
        const original = c.statements.find((s) => s.kind === 'ORIGINAL');
        const text = original ? original.raw_text.split(/\s+/).filter(Boolean).join(' ') : '';
        return {
          case_id: c.case_id,
          status: c.status,
          created_at: c.created_at,
          updated_at: c.updated_at,
          awaiting_answer: Boolean(c.clarification),
          ...(original?.requested_outcome ? { requested_outcome: original.requested_outcome } : {}),
          ...(text
            ? { excerpt: text.length > EXCERPT_CHARACTERS ? text.slice(0, EXCERPT_CHARACTERS).trimEnd() + '...' : text }
            : {}),
        };
      })
      .sort((a, b) => (a.created_at < b.created_at ? 1 : a.created_at > b.created_at ? -1 : 0))
      .slice(0, MY_CASES_LIMIT);
    return { items, limit: MY_CASES_LIMIT };
  }
  return request<CustomerCaseSummaryList>('/v1/cases');
}

export async function listCustomerCaseHistory(
  caseId: string,
  kind: CustomerHistoryKind = 'STATEMENT',
  cursor?: string,
  limit = 20
): Promise<HistoryRecord[]> {
  if (isMockMode()) {
    const c = MOCK_CUSTOMER_CASES[caseId];
    if (!c) return [];
    return c.statements.map((stmt, idx) => ({
      record_id: `rec_hist_${idx + 1}`,
      case_id: caseId,
      kind: 'STATEMENT',
      object_id: stmt.statement_id,
      object_version: idx + 1,
      case_version: idx + 1,
      recorded_sequence: idx + 1,
      recorded_at: stmt.submitted_at,
      retention_state: 'AVAILABLE',
      body: stmt,
    }));
  }

  const params = new URLSearchParams();
  params.set('kind', kind);
  if (cursor) params.set('cursor', cursor);
  params.set('limit', limit.toString());
  const res = await request<any>(`/v1/cases/${encodeURIComponent(caseId)}/history?${params.toString()}`);
  return Array.isArray(res) ? res : res.items || [];
}

export async function submitClarification(
  caseId: string,
  req: ClarificationRequest,
  idempotencyKey?: string
): Promise<CustomerCaseView> {
  const wirePayload: ClarificationRequest = {
    expected_case_version: req.expected_case_version,
    question_set_id: req.question_set_id,
    answers: req.answers,
    evidence_ids: req.evidence_ids ?? [],
  };

  if (isMockMode()) {
    const c = MOCK_CUSTOMER_CASES[caseId];
    if (c) {
      c.status = 'UNDER_INVESTIGATION';
      c.case_version += 1;
      c.input_version += 1;
      c.updated_at = new Date().toISOString();
      const newStmt = {
        statement_id: 'stmt_clarify_' + Date.now().toString(36),
        kind: 'CLARIFICATION' as const,
        raw_text: req.answers.map((a) => `[Q-${a.question_id}]: ${a.text}`).join('\n'),
        submitted_at: new Date().toISOString(),
        evidence_ids: wirePayload.evidence_ids,
      };
      c.statements.push(newStmt);
      delete c.clarification;
      // A case that waited for this answer moves on for the Founder too, as both read one
      // case on the server; a fixture further along keeps its own status.
      const founderView = MOCK_FOUNDER_CASE_VIEWS[caseId];
      if (founderView?.status === 'AWAITING_INFORMATION') Object.assign(founderView, { status: c.status, updated_at: c.updated_at });
      const row = MOCK_FOUNDER_SUMMARIES.find((summary) => summary.case_id === caseId);
      if (row?.status === 'AWAITING_INFORMATION') Object.assign(row, { status: c.status, updated_at: c.updated_at });
      return { ...c };
    }
    throw new ApiError(404, `Case ${caseId} not found`, 'NOT_FOUND');
  }

  return request<CustomerCaseView>(
    `/v1/cases/${encodeURIComponent(caseId)}/clarifications`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(wirePayload),
    },
    true,
    idempotencyKey
  );
}

// -------------------------------------------------------------
// Founder API (UC-04, UC-03, UC-05 & OF-006)
// -------------------------------------------------------------

export async function listFounderCases(cursor?: string, limit = 20): Promise<CaseList> {
  if (isMockMode()) {
    // A case lodged in the Customer Portal is in the mock store but not in the fixed
    // fixture summaries, so the Founder could never see what the customer had just
    // lodged. Derive a summary for anything the fixtures do not cover.
    const lodged: CaseSummary[] = Object.values(MOCK_CUSTOMER_CASES)
      .filter((c) => !MOCK_FOUNDER_SUMMARIES.some((summary) => summary.case_id === c.case_id))
      .map((c) => ({
        case_id: c.case_id,
        case_version: c.case_version,
        input_version: c.input_version,
        status: c.status,
        created_at: c.created_at,
        updated_at: c.updated_at,
        issue_category: 'UNCLEAR' as const,
      }));
    // An index cursor is only stable against a fixed list, and this list gains a row
    // whenever a case is lodged. The order is frozen for the duration of one
    // pagination, so page 2 cannot repeat or skip a row (#122 review, finding 8).
    if (!cursor) MOCK_QUEUE_ORDER = [...lodged, ...MOCK_FOUNDER_SUMMARIES].map((summary) => summary.case_id);
    const byId = new Map([...lodged, ...MOCK_FOUNDER_SUMMARIES].map((summary) => [summary.case_id, summary]));
    const all = MOCK_QUEUE_ORDER.map((caseId) => byId.get(caseId)).filter((summary): summary is CaseSummary => Boolean(summary));
    const startIdx = cursor ? parseInt(cursor, 10) || 0 : 0;
    const items = all.slice(startIdx, startIdx + limit);
    const next_cursor = startIdx + limit < all.length ? String(startIdx + limit) : undefined;
    return {
      items,
      next_cursor,
    };
  }
  const params = new URLSearchParams();
  if (cursor) params.set('cursor', cursor);
  params.set('limit', limit.toString());
  const res = await request<CaseList | CaseSummary[]>(`/v1/founder/cases?${params.toString()}`);
  if (Array.isArray(res)) {
    return { items: res, next_cursor: undefined };
  }
  return {
    items: res.items || [],
    next_cursor: res.next_cursor || undefined,
  };
}

export async function getFounderCase(caseId: string): Promise<CaseView> {
  if (isMockMode()) {
    const view = MOCK_FOUNDER_CASE_VIEWS[caseId];
    if (view?.action_preview) {
      // An expiry fixed when the module loaded could already have passed by the
      // time the demo reaches the approval, so each read gets a fresh five-minute
      // window, like a newly issued server preview.
      return {
        ...view,
        action_preview: {
          ...view.action_preview,
          scope: { ...view.action_preview.scope, expires_at: new Date(Date.now() + 300000).toISOString() },
        },
      };
    }
    if (view) return view;
    const cust = MOCK_CUSTOMER_CASES[caseId];
    if (cust) return cust;
    throw new ApiError(404, `Founder case ${caseId} not found`, 'NOT_FOUND');
  }
  return request<CaseView>(`/v1/founder/cases/${encodeURIComponent(caseId)}`);
}

export async function listFounderCaseAudit(
  caseId: string,
  cursor?: string,
  limit = 50
): Promise<AuditEvent[]> {
  const page = await listFounderCaseAuditPage(caseId, cursor, limit);
  return page.items;
}

// One page of the audit chain (#122 item 13). The console used to call the
// single-page read and drop `next_cursor`, so a case with more than 50 events
// showed only its first page as if that were the whole chain.
export async function listFounderCaseAuditPage(
  caseId: string,
  cursor?: string,
  limit = 50
): Promise<{ items: AuditEvent[]; next_cursor?: string }> {
  if (isMockMode()) {
    return { items: MOCK_AUDIT_EVENTS[caseId] || [], next_cursor: undefined };
  }
  const params = new URLSearchParams();
  if (cursor) params.set('cursor', cursor);
  params.set('limit', limit.toString());
  const res = await request<AuditPage | AuditEvent[]>(
    `/v1/founder/cases/${encodeURIComponent(caseId)}/audit?${params.toString()}`
  );
  if (Array.isArray(res)) return { items: res, next_cursor: undefined };
  return { items: res.items || [], next_cursor: res.next_cursor || undefined };
}

export async function listFounderCaseHistory(
  caseId: string,
  kind: FounderHistoryKind,
  cursor?: string,
  limit = 20
): Promise<HistoryRecord[]> {
  if (isMockMode()) {
    return [];
  }
  const params = new URLSearchParams();
  params.set('kind', kind);
  if (cursor) params.set('cursor', cursor);
  params.set('limit', limit.toString());
  const res = await request<any>(
    `/v1/founder/cases/${encodeURIComponent(caseId)}/history?${params.toString()}`
  );
  return Array.isArray(res) ? res : res.items || [];
}

export async function recordFounderDecision(
  caseId: string,
  req: FounderDecisionRequest,
  idempotencyKey?: string
): Promise<DecisionReceipt> {
  if (isMockMode()) {
    const c = MOCK_FOUNDER_CASE_VIEWS[caseId];
    // Same state rules as the server (decisionStates.ts, #104 item 1): a refused
    // mock decision leaves the case unchanged.
    if (c && decisionStateRefusal(c.status, req.decision) !== null) {
      throw new ApiError(409, 'The request is not available in the current state.', 'INVALID_STATE');
    }
    const decidedAt = new Date().toISOString();
    const decisionId = 'dec_' + Date.now().toString(36);
    // The v1 DecisionReceipt declares approval_id as optional and only a
    // governed APPROVE mints an approval record, so the key is absent rather
    // than present-but-undefined for every other decision.
    const approvalId = req.decision === 'APPROVE' ? 'appr_' + Date.now().toString(36) : undefined;
    if (c) {
      if (req.decision === 'APPROVE') c.status = 'APPROVED';
      else if (req.decision === 'REJECT') c.status = 'REJECTED';
      else if (req.decision === 'REQUEST_REVISION') c.status = 'POLICY_ASSESSMENT';
      else if (req.decision === 'MANUAL_HANDLING') c.status = 'MANUAL_HANDLED';
      c.case_version += 1;
      c.updated_at = decidedAt;
      // The queue row and the customer's copy follow the decision, as they read one case on
      // the server (runtime review, 31 October 2026).
      const row = MOCK_FOUNDER_SUMMARIES.find((summary) => summary.case_id === caseId);
      if (row) Object.assign(row, { status: c.status, case_version: c.case_version, updated_at: decidedAt });
      const customerCopy = MOCK_CUSTOMER_CASES[caseId];
      if (customerCopy) Object.assign(customerCopy, { status: c.status, updated_at: decidedAt });
      // The Outcome tab reads these records, as it does from a live case view.
      const target = Object.fromEntries(
        (['proposal_id', 'proposal_version', 'processing_failure_id', 'order_lookup_block_id'] as const)
          .filter((key) => req[key] !== undefined)
          .map((key) => [key, req[key]])
      );
      c.decisions = [
        ...(c.decisions ?? []),
        {
          decision_id: decisionId,
          case_id: caseId,
          ...target,
          decision: req.decision,
          principal_id: 'founder_demo',
          reason: req.reason,
          decided_at: decidedAt,
          ...(approvalId ? { approval_id: approvalId } : {}),
        },
      ];
      if (approvalId && c.action_preview) {
        c.approvals = [
          ...(c.approvals ?? []),
          {
            approval_id: approvalId,
            decision_id: decisionId,
            principal_id: 'founder_demo',
            issued_at: decidedAt,
            preview_id: c.action_preview.preview_id,
            scope: c.action_preview.scope,
            scope_fingerprint: c.action_preview.scope_fingerprint,
          },
        ];
      }
    }
    // The server writes an audit event for every accepted decision; the mock store
    // did not, so the chain after a decision looked untouched. The hashes are
    // fixture values derived from the event body, not a real SHA-256 digest — the
    // audit panel states that this view does not recompute or verify the chain.
    const previous = (MOCK_AUDIT_EVENTS[caseId] ?? []);
    const previousHash = previous.length > 0
      ? previous[previous.length - 1].event_hash ?? ZERO_HASH
      : ZERO_HASH;
    // Every accepted decision writes FOUNDER_DECISION_ACCEPTED on the server
    // (approve_decision.py:112 and the reject, revision and manual paths alike).
    const eventType = 'FOUNDER_DECISION_ACCEPTED';
    const body = JSON.stringify({ caseId, decision: req.decision, reason: req.reason, decidedAt, previousHash });
    const decisionHash = fixtureHash(body);
    const appended: AuditEvent[] = [
      {
        event_id: 'evt_' + Date.now().toString(36),
        case_id: caseId,
        sequence: previous.length + 1,
        event_type: eventType,
        actor: { kind: 'HUMAN', role: 'FOUNDER', principal_id: 'founder_demo' },
        occurred_at: decidedAt,
        previous_event_hash: previousHash,
        event_hash: decisionHash,
        payload: { decision: req.decision, reason: req.reason },
      },
    ];
    // An APPROVE writes the decision and the approval that follows it
    // (approve_decision.py writes FOUNDER_DECISION_ACCEPTED, then FOUNDER_APPROVAL_ISSUED);
    // the other decisions write only the decision event.
    if (req.decision === 'APPROVE') {
      appended.push({
        event_id: 'evt_' + Date.now().toString(36) + '_appr',
        case_id: caseId,
        sequence: previous.length + 2,
        event_type: 'FOUNDER_APPROVAL_ISSUED',
        actor: { kind: 'HUMAN', role: 'FOUNDER', principal_id: 'founder_demo' },
        occurred_at: decidedAt,
        previous_event_hash: decisionHash,
        event_hash: fixtureHash(body + ':approval'),
        payload: { decision: req.decision },
      });
    }
    MOCK_AUDIT_EVENTS[caseId] = [...previous, ...appended];
    return {
      case_id: caseId,
      case_version: c ? c.case_version : 1,
      decision_id: decisionId,
      decision: req.decision,
      accepted_at: decidedAt,
      processing_status: 'ACCEPTED',
      ...(approvalId ? { approval_id: approvalId } : {}),
    };
  }

  let receipt: DecisionReceipt;
  try {
    receipt = await request<DecisionReceipt>(
      `/v1/founder/cases/${encodeURIComponent(caseId)}/decisions`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      },
      true,
      idempotencyKey
    );
  } catch (err: unknown) {
    // The server registers this route only when started with the decision flag
    // (`demo.py serve --founder-decisions` or RETURNOPS_FOUNDER_DECISIONS=1).
    // Without it the framework answers 404 with no contract error envelope, so
    // request() falls back to the code HTTP_404. A refusal from the route itself
    // always carries a contract code such as NOT_FOUND.
    if (err instanceof ApiError && err.code === 'HTTP_404') {
      throw new ApiError(
        err.status,
        'The server did not serve the Founder decision route (POST /v1/founder/cases/{id}/decisions): either the API was started without --founder-decisions, or VITE_API_BASE_URL or a proxy points at the wrong server. Nothing was recorded.',
        'DECISION_ROUTE_NOT_SERVED',
        err.correlationId
      );
    }
    throw err;
  }

  // A 2xx body that is not an accepted receipt for this case and decision proves
  // nothing, so it is reported with status 0, like a lost response: outcome unknown.
  if (
    receipt?.case_id !== caseId ||
    receipt.decision !== req.decision ||
    receipt.processing_status !== 'ACCEPTED'
  ) {
    throw new ApiError(
      0,
      'The server replied without an accepted receipt for this case and decision.',
      'RECEIPT_MISMATCH'
    );
  }
  return receipt;
}

export async function getFounderAnalytics(query: AnalyticsQuery = {}): Promise<AnalyticsSnapshot> {
  if (isMockMode()) {
    return MOCK_ANALYTICS;
  }
  // Only the contract's three keys, each at most once and only when set: the
  // server answers 422 to unknown or repeated keys.
  const params = new URLSearchParams();
  if (query.created_from) params.set('created_from', query.created_from);
  if (query.created_before) params.set('created_before', query.created_before);
  if (query.status) params.set('status', query.status);
  const qs = params.toString();
  return request<AnalyticsSnapshot>(`/v1/founder/analytics${qs ? `?${qs}` : ''}`);
}

// -------------------------------------------------------------
// Founder AI assistant (31 October 2026), outside contract v1
// -------------------------------------------------------------
// Advisory answers on request: a reply draft, a queue triage and a weekly summary. The
// server offers them only with password sign-in and the model on, and answers 404 or 405
// otherwise. Nothing is sent to a customer or written to a case.

const MOCK_AI = { model_id: 'sample-data', prompt_version: 'founder-assistant-v1' };

export async function draftCustomerReply(caseId: string): Promise<AiReplyDraft> {
  if (isMockMode()) {
    const original = MOCK_CUSTOMER_CASES[caseId]?.statements.find((s) => s.kind === 'ORIGINAL')?.raw_text ?? '';
    const chinese = /[\u4e00-\u9fff]/.test(original);
    const english =
      'Hello, thank you for getting in touch. We have received your request and the shop is looking at it. We will let you know the next step soon.';
    return {
      ...MOCK_AI,
      generated_at: new Date().toISOString(),
      case_id: caseId,
      customer_language: chinese ? 'zh' : 'en',
      reply: chinese ? '您好，感谢您的来信。我们已收到您的请求，店铺正在查看，稍后会告诉您下一步。' : english,
      reply_english: english,
    };
  }
  return request<AiReplyDraft>(`/v1/founder/cases/${encodeURIComponent(caseId)}/assistant/reply`, { method: 'POST' });
}

export async function triageQueue(): Promise<AiTriage> {
  if (isMockMode()) {
    const open = MOCK_FOUNDER_SUMMARIES.filter((c) => !['COMPLETED', 'REJECTED', 'MANUAL_HANDLED'].includes(c.status));
    const urgency = (status: string) => (status === 'ESCALATED' ? 'HIGH' : status === 'AWAITING_APPROVAL' ? 'MEDIUM' : 'LOW');
    return {
      ...MOCK_AI,
      generated_at: new Date().toISOString(),
      considered: open.length,
      cases: open.map((c) => ({
        case_id: c.case_id,
        urgency: urgency(c.status),
        reason: 'Sample data: urgency follows the case status.',
      })),
      groups: open.length >= 2 ? [{ label: 'Sample group', case_ids: open.slice(0, 2).map((c) => c.case_id) }] : [],
    };
  }
  return request<AiTriage>('/v1/founder/assistant/triage', { method: 'POST' });
}

export async function summariseRecentCases(): Promise<AiWeeklySummary> {
  if (isMockMode()) {
    return {
      ...MOCK_AI,
      generated_at: new Date().toISOString(),
      period_days: 7,
      case_count: MOCK_ANALYTICS.case_count,
      model_called: true,
      summary: `Sample data: ${MOCK_ANALYTICS.case_count} cases in the last seven days; read the escalated and waiting cases first.`,
      highlights: ['Sample data only; no model was called.'],
    };
  }
  return request<AiWeeklySummary>('/v1/founder/assistant/summary', { method: 'POST' });
}
