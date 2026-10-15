import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  isMockMode,
  setMockMode,
  getStoredToken,
  setStoredToken,
  createCase,
  getCustomerCase,
  submitClarification,
  listFounderCases,
  getFounderCase,
  listFounderCaseAudit,
  recordFounderDecision,
  getFounderAnalytics,
  stageEvidence,
  downloadEvidence,
  ApiError,
} from './client';

describe('client', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('mock mode and authentication preferences', () => {
    it('defaults to mock mode when localStorage is empty', () => {
      expect(isMockMode()).toBe(true);
    });

    it('persists mock mode changes to localStorage', () => {
      setMockMode(false);
      expect(isMockMode()).toBe(false);
      expect(localStorage.getItem('returnops_mock_mode')).toBe('false');

      setMockMode(true);
      expect(isMockMode()).toBe(true);
      expect(localStorage.getItem('returnops_mock_mode')).toBe('true');
    });

    it('stores and retrieves JWT bearer tokens', () => {
      expect(getStoredToken()).toBe('');
      setStoredToken('test.jwt.token');
      expect(getStoredToken()).toBe('test.jwt.token');
      expect(localStorage.getItem('returnops_auth_token')).toBe('test.jwt.token');

      setStoredToken('');
      expect(getStoredToken()).toBe('');
      expect(localStorage.getItem('returnops_auth_token')).toBeNull();
    });
  });

  describe('mock data operations (offline demonstration)', () => {
    beforeEach(() => {
      setMockMode(true);
    });

    it('creates a new customer intake case in mock mode', async () => {
      const receipt = await createCase({
        original_message: 'The coffee maker was defective upon arrival.',
        requested_outcome: 'REPLACEMENT',
        order_reference: 'ORD-AU-9999',
        evidence_ids: [],
      });

      expect(receipt.case_id).toBeDefined();
      expect(receipt.status).toBe('SUBMITTED');
      expect(receipt.statements[0].raw_text).toBe('The coffee maker was defective upon arrival.');
    });

    it('fetches existing customer case by ID in mock mode', async () => {
      const caseView = await getCustomerCase('case_demo_001');
      expect(caseView.case_id).toBe('case_demo_001');
      expect(caseView.status).toBe('AWAITING_INFORMATION');
      expect(caseView.statements[0].raw_text).toContain('wrong item');
    });

    it('throws ApiError for non-existent case in mock mode', async () => {
      await expect(getCustomerCase('case_non_existent')).rejects.toThrow(ApiError);
    });

    it('submits customer clarification and increments case_version in mock mode', async () => {
      const res = await submitClarification('case_demo_002', {
        question_set_id: 'qset_demo_002',
        answers: [
          {
            question_id: 'q_packaging_01',
            text: 'Yes, original box is undamaged and included.',
          },
        ],
        evidence_ids: [],
        expected_case_version: 3,
      });

      expect(res.case_id).toBe('case_demo_002');
      expect(res.case_version).toBe(4);
    });

    it('lists founder case summaries in mock mode', async () => {
      const summaries = await listFounderCases();
      expect(summaries.items.length).toBeGreaterThanOrEqual(3);
      expect(summaries.items.some((c) => c.case_id === 'case_demo_001')).toBe(true);
      expect(summaries.items.some((c) => c.case_id === 'case_demo_002')).toBe(true);
      expect(summaries.items.some((c) => c.case_id === 'case_demo_003')).toBe(true);
    });

    it('retrieves detailed founder case view with contract-shaped order, proposal and review', async () => {
      const detail = await getFounderCase('case_demo_002');
      expect(detail.case_id).toBe('case_demo_002');
      expect(detail.order_snapshot).toBeDefined();
      expect(detail.order_snapshot?.order_id).toBe('ord_8819');
      expect(detail.order_snapshot?.purchased_at).toBe('2026-10-04T14:30:00Z');
      expect(detail.order_snapshot?.line_items[0].unit_price_minor).toBe(8900);
      // The legacy aliases the reviewer flagged must be gone from the fixtures.
      expect(detail.order_snapshot).not.toHaveProperty('order_number');
      expect(detail.order_snapshot).not.toHaveProperty('items');
      expect(detail.order_snapshot).not.toHaveProperty('total_amount_cents');
      expect(detail.current_proposal).toBeDefined();
      expect(detail.current_proposal?.recommended_action).toBe('PROPOSE_REFUND');
      expect(detail.current_proposal?.confidence).toBe(0.94);
      expect(detail.current_proposal).not.toHaveProperty('confidence_score');
      expect(detail.current_review).toBeDefined();
      expect(detail.current_review?.outcome).toBe('PASS_WITH_WARNING');
      expect(detail.current_review?.reviewed_at).toBeDefined();
      expect(detail.current_review?.findings?.[0].severity).toBe('INFO');
      expect(detail.current_review).not.toHaveProperty('risk_outcome');
    });

    it('retrieves tamper-evident audit trail for a case', async () => {
      const audit = await listFounderCaseAudit('case_demo_001');
      expect(audit.length).toBeGreaterThan(0);
      expect(audit[0].event_hash).toBeDefined();
      expect(audit[0].event_type).toBe('CASE_CREATED');
      expect(audit[0].occurred_at).toBeDefined();
    });

    it('records founder APPROVE decision and returns decision receipt', async () => {
      const receipt = await recordFounderDecision('case_demo_003', {
        expected_case_version: 4,
        decision: 'APPROVE',
        reason: 'Valid claim under store policy.',
        preview_id: 'prev_demo_003',
        scope_fingerprint: 'fp_scope_98124',
      });

      expect(receipt.case_id).toBe('case_demo_003');
      expect(receipt.decision).toBe('APPROVE');
      expect(receipt.processing_status).toBe('ACCEPTED');
      expect(receipt.approval_id).toBeDefined();
    });

    it('records founder REJECT decision without approval guard parameters', async () => {
      const receipt = await recordFounderDecision('case_demo_002', {
        expected_case_version: 3,
        decision: 'REJECT',
        reason: 'Change of mind outside store policy window.',
      });

      expect(receipt.case_id).toBe('case_demo_002');
      expect(receipt.decision).toBe('REJECT');
      expect(receipt.processing_status).toBe('ACCEPTED');
    });

    it('fetches operations analytics snapshot with throughput and latency', async () => {
      const analytics = await getFounderAnalytics();
      expect(analytics.case_count).toBeGreaterThan(0);
      expect(analytics.proposal_latency?.p50_ms).toBeGreaterThan(0);
      expect(analytics.proposal_latency?.p95_ms).toBeGreaterThan(0);
      expect(analytics.cases_by_status.length).toBeGreaterThan(0);
      expect(analytics.current_risk_counts.length).toBeGreaterThan(0);
    });

    it('stages evidence file mock successfully', async () => {
      const fakeFile = new File(['fake image content'], 'receipt.png', { type: 'image/png' });
      const staged = await stageEvidence(fakeFile, 'Invoice receipt');
      expect(staged.evidence_id).toBeDefined();
      expect(staged.status).toBe('STAGED');
      expect(staged.filename).toBe('receipt.png');
    });
  });

  describe('founder queue pagination contract (Finding 6)', () => {
    beforeEach(() => {
      localStorage.clear();
      setMockMode(true);
    });

    it('exposes next_cursor and makes the 21st case reachable on the next page', async () => {
      const firstPage = await listFounderCases(undefined, 20);
      expect(firstPage.items).toHaveLength(20);
      expect(firstPage.next_cursor).toBe('20');
      expect(firstPage.items.some((c) => c.case_id === 'case_demo_021')).toBe(false);

      const secondPage = await listFounderCases(firstPage.next_cursor, 20);
      expect(secondPage.items).toHaveLength(5);
      expect(secondPage.items.some((c) => c.case_id === 'case_demo_021')).toBe(true);
      expect(secondPage.next_cursor).toBeUndefined();
    });
  });

  describe('live wire behaviours with mocked fetch (Findings 1, 2, 4 & 5)', () => {
    const jsonResponse = (status: number, payload: unknown) =>
      ({
        ok: status >= 200 && status < 300,
        status,
        statusText: String(status),
        headers: { get: () => null },
        json: async () => payload,
        blob: async () => new Blob([JSON.stringify(payload)]),
      }) as unknown as Response;

    beforeEach(() => {
      localStorage.clear();
      setMockMode(false);
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      vi.restoreAllMocks();
      localStorage.clear();
    });

    it('sends the caller-supplied idempotency key and reuses it on a lost-response retry', async () => {
      const seenKeys: Array<string | null> = [];
      vi.stubGlobal(
        'fetch',
        vi.fn(async (_url: string, init: RequestInit = {}) => {
          seenKeys.push(new Headers(init.headers).get('Idempotency-Key'));
          throw new TypeError('socket closed before the response was read');
        })
      );

      const payload = { original_message: 'Refund request retried after a lost response.' };
      await expect(createCase(payload, 'case_idem_lostresponse_01')).rejects.toBeInstanceOf(ApiError);
      await expect(createCase(payload, 'case_idem_lostresponse_01')).rejects.toBeInstanceOf(ApiError);

      expect(seenKeys).toEqual(['case_idem_lostresponse_01', 'case_idem_lostresponse_01']);
    });

    it('surfaces an idempotency-key conflict instead of silently succeeding', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          jsonResponse(409, {
            error: { code: 'IDEMPOTENCY_KEY_REUSED', message: 'Key reused with a different payload' },
          })
        )
      );

      await expect(
        createCase({ original_message: 'changed payload' }, 'case_idem_lostresponse_01')
      ).rejects.toMatchObject({ status: 409, code: 'IDEMPOTENCY_KEY_REUSED' });
    });

    it('downloads protected evidence with the bearer header and never in the URL', async () => {
      setStoredToken('secret.bearer.token');
      let observedUrl = '';
      let observedAuth: string | null = null;
      vi.stubGlobal(
        'fetch',
        vi.fn(async (url: string, init: RequestInit = {}) => {
          observedUrl = String(url);
          observedAuth = new Headers(init.headers).get('Authorization');
          return jsonResponse(403, { error: { code: 'FORBIDDEN', message: 'not your evidence' } });
        })
      );

      await expect(downloadEvidence('ev_401_check', 'receipt.png')).rejects.toMatchObject({
        status: 403,
        code: 'FORBIDDEN',
      });
      expect(observedAuth).toBe('Bearer secret.bearer.token');
      expect(observedUrl).toContain('/v1/evidence/ev_401_check/content');
      expect(observedUrl).not.toContain('secret.bearer.token');
    });

    it('carries staged evidence_ids through the clarification wire payload', async () => {
      const sentBodies: Array<Record<string, unknown>> = [];
      vi.stubGlobal(
        'fetch',
        vi.fn(async (_url: string, init: RequestInit = {}) => {
          sentBodies.push(JSON.parse(String(init.body)));
          return jsonResponse(202, { case_id: 'case_demo_001' });
        })
      );

      await submitClarification(
        'case_demo_001',
        {
          expected_case_version: 2,
          question_set_id: 'qset_demo_001',
          answers: [{ question_id: 'q_01', text: 'Barcode 9312345678901' }],
          evidence_ids: ['ev_clarify_receipt'],
        },
        'clarify_idem_evidence_01'
      );

      expect(sentBodies[0]?.evidence_ids).toEqual(['ev_clarify_receipt']);
    });

    it('treats a 202 clarification admission as success and surfaces a 409 version conflict (Finding 12)', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => jsonResponse(202, { case_id: 'case_demo_001', case_version: 3 }))
      );

      await expect(
        submitClarification('case_demo_001', {
          expected_case_version: 2,
          question_set_id: 'qset_demo_001',
          answers: [{ question_id: 'q_01', text: 'Box arrived crushed.' }],
          evidence_ids: [],
        })
      ).resolves.toMatchObject({ case_id: 'case_demo_001', case_version: 3 });

      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          jsonResponse(409, {
            error: { code: 'VERSION_CONFLICT', message: 'expected_case_version is stale' },
          })
        )
      );

      await expect(
        submitClarification('case_demo_001', {
          expected_case_version: 2,
          question_set_id: 'qset_demo_001',
          answers: [{ question_id: 'q_01', text: 'Box arrived crushed.' }],
          evidence_ids: [],
        })
      ).rejects.toMatchObject({ status: 409, code: 'VERSION_CONFLICT' });
    });

    it('sends the caller-supplied idempotency key on evidence uploads as well as intake (Finding 1)', async () => {
      const seen: Array<{ url: string; key: string | null }> = [];
      vi.stubGlobal(
        'fetch',
        vi.fn(async (url: string, init: RequestInit = {}) => {
          seen.push({ url: String(url), key: new Headers(init.headers).get('Idempotency-Key') });
          return jsonResponse(201, {
            evidence_id: 'ev_upload_01',
            filename: 'receipt.png',
            media_type: 'image/png',
            size_bytes: 12,
            sha256: 'sha256_upload_01',
            created_at: '2026-10-09T12:00:00Z',
            status: 'STAGED',
          });
        })
      );

      const file = new File(['fake image content'], 'receipt.png', { type: 'image/png' });
      await stageEvidence(file, 'Invoice receipt', 'ev_idem_upload_01');
      await createCase({ original_message: 'Lost response retry' }, 'ev_idem_upload_01');

      expect(seen.map((call) => call.key)).toEqual(['ev_idem_upload_01', 'ev_idem_upload_01']);
      expect(seen[0]?.url).toContain('/v1/evidence');
      expect(seen[1]?.url).toContain('/v1/cases');
    });

    it('gates undeployed Founder decision and analytics endpoints with an explicit 501', async () => {
      await expect(
        recordFounderDecision('case_demo_001', {
          expected_case_version: 2,
          decision: 'APPROVE',
          reason: 'x',
        })
      ).rejects.toMatchObject({ status: 501, code: 'NOT_IMPLEMENTED' });

      await expect(getFounderAnalytics()).rejects.toMatchObject({ status: 501, code: 'NOT_IMPLEMENTED' });
    });
  });

  describe('ApiError', () => {
    it('correctly constructs ApiError with status, message, code and correlationId', () => {
      const err = new ApiError(409, 'Version conflict', 'VERSION_CONFLICT', 'corr_123');
      expect(err.status).toBe(409);
      expect(err.message).toBe('Version conflict');
      expect(err.code).toBe('VERSION_CONFLICT');
      expect(err.correlationId).toBe('corr_123');
      expect(err.name).toBe('ApiError');
    });
  });
});
