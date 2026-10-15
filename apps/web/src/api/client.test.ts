import { describe, it, expect, beforeEach, afterEach } from 'vitest';
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

    it('retrieves detailed founder case view with facts and proposals', async () => {
      const detail = await getFounderCase('case_demo_002');
      expect(detail.case_id).toBe('case_demo_002');
      expect(detail.order_snapshot).toBeDefined();
      expect(detail.order_snapshot?.order_number).toBe('ORD-2026-8819');
      expect(detail.current_proposal).toBeDefined();
      expect(detail.current_proposal?.outcome).toBe('REFUND');
      expect(detail.current_review).toBeDefined();
      expect(detail.current_review?.risk_outcome).toBe('PASS_WITH_WARNING');
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
