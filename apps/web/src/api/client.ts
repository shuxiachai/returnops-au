import {
  CreateCaseRequest,
  ClarificationRequest,
  CustomerCaseView,
  CaseSummary,
  CaseList,
  CaseView,
  FounderDecisionRequest,
  DecisionReceipt,
  AnalyticsQuery,
  AnalyticsSnapshot,
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

// Storage keys
const TOKEN_KEY = 'returnops_auth_token';
const MOCK_MODE_KEY = 'returnops_mock_mode';
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
        if (response.status === 500) {
          msg = `HTTP 500: Backend server unavailable at http://127.0.0.1:8000. Start the backend or switch to Mock Mode in the top navbar.`;
        } else {
          msg = `HTTP ${response.status}: ${response.statusText}`;
        }
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
    throw new ApiError(0, err instanceof Error ? err.message : 'Network error or backend unavailable');
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

  const res = await fetch(`${BASE_URL}/v1/evidence`, {
    method: 'POST',
    headers,
    body: formData,
  });
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
      errEnv?.error?.code,
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

  const res = await fetch(`${BASE_URL}/v1/evidence/${encodeURIComponent(evidenceId)}/content`, {
    headers,
  });
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

function runMockIntake(c: CustomerCaseView): void {
  if (!MOCK_PENDING_INTAKE.delete(c.case_id)) return;
  const reference = c.statements.find((statement) => statement.kind === 'ORIGINAL')?.order_reference;
  if (hasUsableOrderReference(reference)) {
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

// The server's only test on a reference (investigation_admission.py:53): non-empty,
// trimmed, at most 120 characters. It is not restricted to the synthetic SYN-#### form.
function hasUsableOrderReference(reference?: string): boolean {
  const trimmed = (reference ?? '').trim();
  return trimmed.length > 0 && trimmed.length <= 120;
}

export async function createCase(req: CreateCaseRequest, idempotencyKey?: string): Promise<CustomerCaseView> {
  if (isMockMode()) {
    const newCaseId = 'case_demo_' + Math.floor(100 + Math.random() * 900);
    const newCase: CustomerCaseView = {
      case_id: newCaseId,
      case_version: 1,
      input_version: 1,
      status: 'SUBMITTED',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      statements: [
        {
          statement_id: 'stmt_' + Date.now().toString(36),
          kind: 'ORIGINAL',
          raw_text: req.original_message,
          submitted_at: new Date().toISOString(),
          order_reference: req.order_reference,
          requested_outcome: req.requested_outcome,
          evidence_ids: req.evidence_ids,
        },
      ],
      evidence: (req.evidence_ids || []).map((id, idx) => ({
        evidence_id: id,
        filename: `uploaded_evidence_${idx + 1}.png`,
        media_type: 'image/png',
        size_bytes: 245000,
        status: 'BOUND' as const,
        created_at: new Date().toISOString(),
        content_path: `/v1/evidence/${id}/content`,
      })),
    };
    // The receipt is always SUBMITTED version 1 -- the server asserts exactly that
    // (customer_service.py:258, raising INTERNAL_ERROR otherwise). The intake worker
    // adds the question set afterwards, so the first read after creation attaches it.
    newCase.status = 'SUBMITTED';
    MOCK_CUSTOMER_CASES[newCaseId] = newCase;
    MOCK_PENDING_INTAKE.add(newCaseId);
    return newCase;
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
    return c;
  }
  return request<CustomerCaseView>(`/v1/cases/${encodeURIComponent(caseId)}`);
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
    MOCK_AUDIT_EVENTS[caseId] = [
      ...previous,
      {
        event_id: 'evt_' + Date.now().toString(36),
        case_id: caseId,
        sequence: previous.length + 1,
        event_type: eventType,
        actor: { kind: 'HUMAN', role: 'FOUNDER', principal_id: 'founder_demo' },
        occurred_at: decidedAt,
        previous_event_hash: previousHash,
        event_hash: fixtureHash(body),
        payload: { decision: req.decision, reason: req.reason },
      },
    ];
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
