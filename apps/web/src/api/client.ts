import {
  CreateCaseRequest,
  ClarificationRequest,
  CustomerCaseView,
  CaseSummary,
  CaseList,
  CaseView,
  FounderDecisionRequest,
  DecisionReceipt,
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

  constructor(status: number, message: string, code?: string, correlationId?: string, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
    this.details = details;
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

async function request<T>(
  path: string,
  options: RequestInit = {},
  requireIdempotency = false,
  idempotencyKey?: string
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
      throw new ApiError(response.status, msg, code, correlationId, errEnvelope?.error?.details);
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
      byte_size: file.size,
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
      correlationId
    );
  }

  const data = await res.json();
  return {
    ...data,
    byte_size: data.size_bytes,
  };
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
        byte_size: 245000,
        status: 'BOUND' as const,
        created_at: new Date().toISOString(),
        content_path: `/v1/evidence/${id}/content`,
      })),
      clarification: {
        question_set_id: 'qset_' + Date.now().toString(36),
        input_version: 1,
        questions: [
          {
            question_id: 'q_auto_1',
            text: 'Could you confirm the condition of the shipping packaging upon arrival?',
            reason: 'Intake assessment checking logistics transit integrity.',
          },
        ],
      },
    };
    MOCK_CUSTOMER_CASES[newCaseId] = newCase;
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
    const all = MOCK_FOUNDER_SUMMARIES;
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
    if (view) return view;
    const cust = MOCK_CUSTOMER_CASES[caseId];
    if (cust) {
      return {
        ...cust,
        facts: { raw_note: 'Synthesized from customer case view' },
      };
    }
    throw new ApiError(404, `Founder case ${caseId} not found`, 'NOT_FOUND');
  }
  return request<CaseView>(`/v1/founder/cases/${encodeURIComponent(caseId)}`);
}

export async function listFounderCaseAudit(
  caseId: string,
  cursor?: string,
  limit = 50
): Promise<AuditEvent[]> {
  if (isMockMode()) {
    return MOCK_AUDIT_EVENTS[caseId] || [];
  }
  const params = new URLSearchParams();
  if (cursor) params.set('cursor', cursor);
  params.set('limit', limit.toString());
  const res = await request<AuditPage | AuditEvent[]>(
    `/v1/founder/cases/${encodeURIComponent(caseId)}/audit?${params.toString()}`
  );
  if (Array.isArray(res)) return res;
  return res.items || [];
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
  req: FounderDecisionRequest
): Promise<DecisionReceipt> {
  if (isMockMode()) {
    const c = MOCK_FOUNDER_CASE_VIEWS[caseId];
    if (c) {
      if (req.decision === 'APPROVE') c.status = 'APPROVED';
      else if (req.decision === 'REJECT') c.status = 'REJECTED';
      else if (req.decision === 'REQUEST_REVISION') c.status = 'POLICY_ASSESSMENT';
      else if (req.decision === 'MANUAL_HANDLING') c.status = 'MANUAL_HANDLED';
      c.case_version += 1;
      c.updated_at = new Date().toISOString();
    }
    return {
      case_id: caseId,
      case_version: c ? c.case_version : 1,
      decision_id: 'dec_' + Date.now().toString(36),
      decision: req.decision,
      accepted_at: new Date().toISOString(),
      processing_status: 'ACCEPTED',
      approval_id: req.decision === 'APPROVE' ? 'appr_' + Date.now().toString(36) : undefined,
    };
  }

  // Gate Founder capabilities that have no runtime endpoint on current backend main
  throw new ApiError(
    501,
    'Founder decision recording (POST /v1/founder/cases/{id}/decisions) is a planned contract not yet registered in current live backend. Please switch to Mock Mode in the top navbar to interactively demonstrate governed decisions.',
    'NOT_IMPLEMENTED'
  );
}

export async function getFounderAnalytics(): Promise<AnalyticsSnapshot> {
  if (isMockMode()) {
    return MOCK_ANALYTICS;
  }
  // Gate Founder capabilities that have no runtime endpoint on current backend main
  throw new ApiError(
    501,
    'Founder analytics aggregation (GET /v1/founder/analytics) is a planned contract not yet registered in current live backend. Please switch to Mock Mode in the top navbar to view simulated analytics.',
    'NOT_IMPLEMENTED'
  );
}
