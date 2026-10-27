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
import { MOCK_AUDIT_EVENTS, MOCK_CUSTOMER_CASES, MOCK_FOUNDER_CASE_VIEWS } from './mockData';
import type { AnalyticsSnapshot, CaseStatus, RiskOutcome } from '../types/domain';

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
        // No reference: this is the case that must be asked for one.
        evidence_ids: [],
      });

      expect(receipt.case_id).toBeDefined();
      // The server's receipt is SUBMITTED version 1 and nothing else
      // (customer_service.py:258); the intake worker adds the questions afterwards.
      expect(receipt.status).toBe('SUBMITTED');
      expect(receipt.case_version).toBe(1);
      expect(receipt.clarification).toBeUndefined();
      expect(receipt.statements[0].raw_text).toBe('The coffee maker was defective upon arrival.');

      // The first read runs the intake: no usable reference asks for one plus the
      // alternative question, and any non-empty reference up to 120 characters
      // (the server's own test) goes straight to the investigation.
      const firstRead = await getCustomerCase(receipt.case_id);
      expect(firstRead.status).toBe('AWAITING_INFORMATION');
      expect(firstRead.clarification?.questions.map((q) => q.question_id)).toEqual(['q_auto_ref', 'q_auto_alt']);

      const withReference = await createCase({
        original_message: 'The coffee maker was defective upon arrival.',
        requested_outcome: 'REPLACEMENT',
        order_reference: 'A12345',
        evidence_ids: [],
      });
      expect(withReference.status).toBe('SUBMITTED');
      const referenceRead = await getCustomerCase(withReference.case_id);
      expect(referenceRead.status).toBe('UNDER_INVESTIGATION');
      expect(referenceRead.clarification).toBeUndefined();
    });

    it('writes an audit event for a mock decision, as the server does', async () => {
      // The mock store is shared, so this test restores the case and its chain.
      const viewBefore = structuredClone(MOCK_FOUNDER_CASE_VIEWS['case_demo_003']);
      const auditBefore = structuredClone(MOCK_AUDIT_EVENTS['case_demo_003']);
      try {
      const before = await listFounderCaseAudit('case_demo_003');
      await recordFounderDecision('case_demo_003', {
        expected_case_version: 4,
        decision: 'REJECT',
        reason: 'Mock audit event coverage.',
        proposal_id: 'prop_demo_003',
        proposal_version: 1,
      });
      const after = await listFounderCaseAudit('case_demo_003');

      expect(after).toHaveLength(before.length + 1);
      const added = after[after.length - 1];
      expect(added.event_type).toBe('FOUNDER_DECISION_ACCEPTED');
      expect(added.previous_event_hash).toBe(before[before.length - 1]?.event_hash ?? '0'.repeat(64));
      expect(added.event_hash).toMatch(/^[0-9a-f]{64}$/);
      } finally {
        MOCK_FOUNDER_CASE_VIEWS['case_demo_003'] = viewBefore;
        MOCK_AUDIT_EVENTS['case_demo_003'] = auditBefore;
      }
    });

    it('treats bound evidence as material, so no reference question is asked', async () => {
      const receipt = await createCase({
        original_message: 'Photo attached, no order number.',
        requested_outcome: 'REFUND',
        evidence_ids: ['ev_material_1'],
      });
      const read = await getCustomerCase(receipt.case_id);

      expect(read.status).toBe('UNDER_INVESTIGATION');
      expect(read.clarification).toBeUndefined();
    });

    it('hands out copies, so the receipt a customer is reading cannot change under it', async () => {
      const receipt = await createCase({ original_message: 'Two cups arrived chipped.' });
      expect(receipt.status).toBe('SUBMITTED');

      const firstRead = await getCustomerCase(receipt.case_id);

      expect(firstRead.status).toBe('AWAITING_INFORMATION');
      expect(receipt.status).toBe('SUBMITTED');
      expect(firstRead).not.toBe(receipt);
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

    it('adds no facts when a founder view falls back to a mock customer case (Issue #95)', async () => {
      const created = await createCase({
        original_message: 'The toaster arrived with a cracked casing.',
        requested_outcome: 'REFUND',
        evidence_ids: [],
      });

      const detail = await getFounderCase(created.case_id);
      expect(detail.case_id).toBe(created.case_id);
      expect(detail).not.toHaveProperty('facts');
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

      // The mock view now carries the decision and the approval of the preview's
      // exact scope, which the Outcome tab shows (#122 item 4).
      const view = MOCK_FOUNDER_CASE_VIEWS.case_demo_003;
      const decisions = view.decisions ?? [];
      const approvals = view.approvals ?? [];
      expect(decisions[decisions.length - 1]).toMatchObject({
        decision_id: receipt.decision_id,
        decision: 'APPROVE',
        reason: 'Valid claim under store policy.',
        principal_id: 'founder_demo',
        approval_id: receipt.approval_id,
      });
      expect(approvals[approvals.length - 1]).toMatchObject({
        approval_id: receipt.approval_id,
        decision_id: receipt.decision_id,
        preview_id: view.action_preview?.preview_id,
        scope_fingerprint: view.action_preview?.scope_fingerprint,
      });
    });

    it('records founder REJECT decision without approval guard parameters', async () => {
      // case_demo_003 is approved by the test above, so a copy still awaiting approval is used.
      MOCK_FOUNDER_CASE_VIEWS.case_reject_check = {
        ...structuredClone(MOCK_FOUNDER_CASE_VIEWS.case_demo_003),
        case_id: 'case_reject_check',
        status: 'AWAITING_APPROVAL',
        decisions: [],
        approvals: [],
      };
      try {
        const receipt = await recordFounderDecision('case_reject_check', {
          expected_case_version: MOCK_FOUNDER_CASE_VIEWS.case_reject_check.case_version,
          decision: 'REJECT',
          reason: 'Change of mind outside store policy window.',
          proposal_id: 'prop_demo_003',
          proposal_version: 1,
        });

        expect(receipt.case_id).toBe('case_reject_check');
        expect(receipt.decision).toBe('REJECT');
        expect(receipt.processing_status).toBe('ACCEPTED');
        // Only a governed APPROVE may mint an approval record, so a REJECT
        // receipt must not carry one at all.
        expect(receipt).not.toHaveProperty('approval_id');
        const view = MOCK_FOUNDER_CASE_VIEWS.case_reject_check;
        expect(view.decisions).toHaveLength(1);
        expect(view.decisions?.[0]).toMatchObject({ decision: 'REJECT', proposal_id: 'prop_demo_003' });
        expect(view.decisions?.[0]).not.toHaveProperty('approval_id');
        expect(view.approvals).toEqual([]);
      } finally {
        delete MOCK_FOUNDER_CASE_VIEWS.case_reject_check;
      }
    });

    it('refuses a decision the server would refuse in the case state and leaves the case unchanged (#104 item 1)', async () => {
      // case_demo_002 is in RISK_REVIEW, where the server accepts no Founder decision.
      const view = MOCK_FOUNDER_CASE_VIEWS.case_demo_002;
      const before = { status: view.status, case_version: view.case_version, decisions: view.decisions };
      expect(view.status).toBe('RISK_REVIEW');
      for (const decision of ['APPROVE', 'REJECT', 'REQUEST_REVISION', 'MANUAL_HANDLING'] as const) {
        await expect(
          recordFounderDecision('case_demo_002', {
            expected_case_version: view.case_version,
            decision,
            reason: 'Should be refused in this state.',
          })
        ).rejects.toMatchObject({ status: 409, code: 'INVALID_STATE' });
      }
      expect({ status: view.status, case_version: view.case_version, decisions: view.decisions }).toEqual(before);
    });

    it('serves a mock analytics snapshot that keeps the contract invariants', async () => {
      const analytics = await getFounderAnalytics();
      const total = (buckets: Array<{ count: number }>) => buckets.reduce((sum, b) => sum + b.count, 0);
      const latency = analytics.proposal_latency;

      expect(analytics.filters).toEqual({});
      expect(analytics.case_count).toBe(128);
      expect(total(analytics.cases_by_status)).toBe(analytics.case_count);
      expect(total(analytics.current_risk_counts) + analytics.cases_without_current_review).toBe(
        analytics.case_count
      );
      expect(latency.sample_count + latency.failed_count + latency.unmeasured_count).toBe(analytics.case_count);
      // Percentiles are present because there are samples, and p50 <= p95.
      expect(latency.sample_count).toBeGreaterThan(0);
      expect(latency.p50_ms).toBeGreaterThan(0);
      expect(latency.p95_ms).toBeGreaterThanOrEqual(latency.p50_ms ?? Infinity);

      // No zero buckets, no repeats, and buckets in contract enum order.
      const statusOrder: CaseStatus[] = [
        'SUBMITTED', 'AWAITING_INFORMATION', 'UNDER_INVESTIGATION', 'POLICY_ASSESSMENT',
        'RISK_REVIEW', 'AWAITING_APPROVAL', 'APPROVED', 'ACTION_IN_PROGRESS', 'ACTION_FAILED',
        'RECONCILING', 'ESCALATED', 'NOTIFICATION_PENDING', 'NOTIFICATION_FAILED', 'COMPLETED',
        'REJECTED', 'MANUAL_HANDLED',
      ];
      const riskOrder: RiskOutcome[] = ['PASS', 'PASS_WITH_WARNING', 'REVISE', 'NEEDS_INFORMATION', 'ESCALATE'];
      const statuses = analytics.cases_by_status.map((b) => b.status);
      const outcomes = analytics.current_risk_counts.map((b) => b.outcome);
      expect(statuses).toEqual(statusOrder.filter((s) => statuses.includes(s)));
      expect(outcomes).toEqual(riskOrder.filter((o) => outcomes.includes(o)));
      expect([...analytics.cases_by_status, ...analytics.current_risk_counts].every((b) => b.count > 0)).toBe(true);
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
      // A case lodged by an earlier test is a founder queue row now, so it is
      // removed here to keep the page-size boundary deterministic.
      for (const caseId of Object.keys(MOCK_CUSTOMER_CASES)) {
        if (!/^case_demo_0\d\d$/.test(caseId)) delete MOCK_CUSTOMER_CASES[caseId];
      }
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
            error: { code: 'IDEMPOTENCY_CONFLICT', message: 'Key reused with a different payload' },
          })
        )
      );

      await expect(
        createCase({ original_message: 'changed payload' }, 'case_idem_lostresponse_01')
      ).rejects.toMatchObject({ status: 409, code: 'IDEMPOTENCY_CONFLICT' });
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
            error: { code: 'STALE_CASE_VERSION', message: 'expected_case_version is stale' },
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
      ).rejects.toMatchObject({ status: 409, code: 'STALE_CASE_VERSION' });
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

    // Latency tier 0, as the server reports today: no samples and no percentiles.
    const TIER0_SNAPSHOT: AnalyticsSnapshot = {
      as_of: '2026-10-22T09:30:00.123456Z',
      filters: {},
      case_count: 3,
      cases_by_status: [
        { status: 'SUBMITTED', count: 2 },
        { status: 'REJECTED', count: 1 },
      ],
      current_risk_counts: [{ outcome: 'PASS', count: 1 }],
      cases_without_current_review: 2,
      proposal_latency: {
        metric_version: 'proposal-latency-v1',
        sample_count: 0,
        failed_count: 1,
        unmeasured_count: 2,
      },
    };

    it('reads live analytics with the Bearer token and sends only the contract filters that are set', async () => {
      setStoredToken('founder.bearer.token');
      const calls: Array<{ url: URL; auth: string | null }> = [];
      vi.stubGlobal(
        'fetch',
        vi.fn(async (url: string, init: RequestInit = {}) => {
          calls.push({
            url: new URL(String(url), 'http://localhost'),
            auth: new Headers(init.headers).get('Authorization'),
          });
          return jsonResponse(200, TIER0_SNAPSHOT);
        })
      );

      await expect(getFounderAnalytics()).resolves.toEqual(TIER0_SNAPSHOT);
      await getFounderAnalytics({
        created_from: '2026-10-01T00:00:00Z',
        created_before: '2026-10-08T00:00:00Z',
        status: 'REJECTED',
      });
      await getFounderAnalytics({ status: 'AWAITING_APPROVAL' });

      expect(calls.map((call) => call.url.pathname)).toEqual([
        '/v1/founder/analytics',
        '/v1/founder/analytics',
        '/v1/founder/analytics',
      ]);
      expect(calls[0].url.search).toBe('');
      expect([...calls[1].url.searchParams.entries()]).toEqual([
        ['created_from', '2026-10-01T00:00:00Z'],
        ['created_before', '2026-10-08T00:00:00Z'],
        ['status', 'REJECTED'],
      ]);
      expect([...calls[2].url.searchParams.entries()]).toEqual([['status', 'AWAITING_APPROVAL']]);
      expect(calls.every((call) => call.auth === 'Bearer founder.bearer.token')).toBe(true);
    });

    it('passes an analytics error response through as an ApiError (stubbed 422, query not validated here)', async () => {
      // The stub answers 422 whatever the query is; only the pass-through is checked.
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          jsonResponse(422, { error: { code: 'VALIDATION_ERROR', message: 'Request fields are invalid.' } })
        )
      );

      await expect(getFounderAnalytics({ created_from: '2026-10-08T00:00:00Z' })).rejects.toMatchObject({
        status: 422,
        code: 'VALIDATION_ERROR',
      });
    });

    it('posts a contract-exact Founder decision with the Bearer token and an Idempotency-Key', async () => {
      setStoredToken('founder.bearer.token');
      const seen: Array<{ url: URL; method?: string; headers: Headers; body: unknown }> = [];
      const receipt = {
        case_id: 'case_live_01',
        case_version: 5,
        decision_id: 'dec_live_01',
        decision: 'REJECT',
        accepted_at: '2026-10-22T10:00:00Z',
        processing_status: 'ACCEPTED',
      };
      vi.stubGlobal(
        'fetch',
        vi.fn(async (url: string, init: RequestInit = {}) => {
          seen.push({
            url: new URL(String(url), 'http://localhost'),
            method: init.method,
            headers: new Headers(init.headers),
            body: JSON.parse(String(init.body)),
          });
          return jsonResponse(202, receipt);
        })
      );

      const body = {
        expected_case_version: 4,
        decision: 'REJECT' as const,
        reason: 'Outside the change-of-mind window.',
        proposal_id: 'prop_live_01',
        proposal_version: 2,
      };
      await expect(recordFounderDecision('case_live_01', body, 'decision_idem_live_01')).resolves.toEqual(receipt);
      // Without a caller key the client still sends a contract-shaped one.
      await recordFounderDecision('case_live_01', body);

      expect(seen[0].url.pathname).toBe('/v1/founder/cases/case_live_01/decisions');
      expect(seen[0].method).toBe('POST');
      expect(seen[0].headers.get('Authorization')).toBe('Bearer founder.bearer.token');
      expect(seen[0].headers.get('Content-Type')).toBe('application/json');
      expect(seen[0].headers.get('Idempotency-Key')).toBe('decision_idem_live_01');
      // Exactly the request fields: the client adds nothing to the body.
      expect(seen[0].body).toStrictEqual(body);
      expect(seen[1].headers.get('Idempotency-Key')).toMatch(/^[A-Za-z0-9._:-]{8,128}$/);
    });

    it('reports a server without the decision route and keeps contract refusals unchanged', async () => {
      const body = {
        expected_case_version: 2,
        decision: 'MANUAL_HANDLING' as const,
        reason: 'Take the case over manually.',
        processing_failure_id: 'fail_live_01',
      };

      // Flag off: the framework's 404 carries no contract error envelope. A wrong
      // base URL or proxy gives the same reply, so the message names both (#104 item 5).
      vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(404, { detail: 'Not Found' })));
      await expect(recordFounderDecision('case_live_01', body)).rejects.toMatchObject({
        status: 404,
        code: 'DECISION_ROUTE_NOT_SERVED',
        message: expect.stringMatching(/without --founder-decisions, or VITE_API_BASE_URL or a proxy points at the wrong server\. Nothing was recorded\.$/),
      });

      // Refusals from the route itself keep their contract status and code.
      const refusals: Array<[number, string]> = [
        [403, 'FORBIDDEN'],
        [404, 'NOT_FOUND'],
        [409, 'STALE_CASE_VERSION'],
        [422, 'VALIDATION_ERROR'],
        [503, 'INTERNAL_ERROR'],
      ];
      for (const [status, code] of refusals) {
        vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(status, { error: { code, message: 'Refused.' } })));
        await expect(recordFounderDecision('case_live_01', body)).rejects.toMatchObject({ status, code });
      }
    });

    it('treats a 2xx reply that is not a matching accepted receipt as an unknown outcome', async () => {
      const body = {
        expected_case_version: 4,
        decision: 'REJECT' as const,
        reason: 'Outside the change-of-mind window.',
        proposal_id: 'prop_live_01',
        proposal_version: 2,
      };
      const receipt = {
        case_id: 'case_live_01',
        case_version: 5,
        decision_id: 'dec_live_01',
        decision: 'REJECT',
        accepted_at: '2026-10-22T10:00:00Z',
        processing_status: 'ACCEPTED',
      };
      const replies = [
        { ...receipt, case_id: 'case_other_01' },
        { ...receipt, decision: 'APPROVE', approval_id: 'appr_live_01' },
        { ...receipt, processing_status: 'PENDING' },
        {},
      ];

      for (const reply of replies) {
        vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(202, reply)));
        await expect(recordFounderDecision('case_live_01', body)).rejects.toMatchObject({
          status: 0,
          code: 'RECEIPT_MISMATCH',
        });
      }
    });
  });

  describe('retryable (#122 item 7)', () => {
    beforeEach(() => {
      localStorage.clear();
      setMockMode(false); // these cases are about the live wire, not the fixture store
    });
    afterEach(() => {
      localStorage.clear();
      setMockMode(true);
    });

    const reply = (status: number, body: unknown) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      });

    it('carries the envelope flag so a permanent refusal is not presented as retryable', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          reply(409, {
            error: { code: 'IDEMPOTENCY_CONFLICT', message: 'Key already used.', retryable: false },
          })
        )
      );

      await expect(createCase({ original_message: 'x' }, 'case_key_1')).rejects.toMatchObject({
        status: 409,
        code: 'IDEMPOTENCY_CONFLICT',
        retryable: false,
      });
    });

    it('leaves the flag undefined when the reply carries no envelope', async () => {
      vi.stubGlobal('fetch', vi.fn(async () => reply(500, { detail: 'Not Found' })));

      const error = await createCase({ original_message: 'x' }, 'case_key_2').catch((err) => err);

      expect(error).toBeInstanceOf(ApiError);
      expect(error.retryable).toBeUndefined();
    });
  });

  describe('ApiError', () => {
    it('correctly constructs ApiError with status, message, code and correlationId', () => {
      const err = new ApiError(409, 'Version conflict', 'STALE_CASE_VERSION', 'corr_123');
      expect(err.status).toBe(409);
      expect(err.message).toBe('Version conflict');
      expect(err.code).toBe('STALE_CASE_VERSION');
      expect(err.correlationId).toBe('corr_123');
      expect(err.name).toBe('ApiError');
    });
  });
});
