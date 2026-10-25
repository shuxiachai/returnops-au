import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { FounderConsole } from './FounderConsole';
import type { AnalyticsSnapshot, CaseView } from '../types/domain';
import { formatDate } from '../utils/formatters';

// Keep the real ApiError, but take deterministic control of the API surface so
// the failure and live-mode branches of the console can be exercised (Findings
// 2, 4 & 9).
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    isMockMode: vi.fn(() => true),
    listFounderCases: vi.fn(),
    getFounderCase: vi.fn(),
    listFounderCaseAudit: vi.fn(),
    recordFounderDecision: vi.fn(),
    getFounderAnalytics: vi.fn(),
  };
});

import {
  ApiError,
  isMockMode,
  listFounderCases,
  getFounderCase,
  listFounderCaseAudit,
  recordFounderDecision,
  getFounderAnalytics,
} from '../api/client';

// A contract Hash: 64 lowercase hexadecimal characters.
const CONTRACT_FINGERPRINT = '3f'.repeat(32);

/**
 * A strictly contract-shaped CaseView: it uses only the field names defined in
 * contracts/v1/schemas.json (OrderSnapshot.line_items/unit_price_minor,
 * DecisionPacket.recommended_action/confidence, RiskReview.outcome/findings/
 * reviewed_at) and carries none of the legacy aliases.
 */
const CONTRACT_SHAPED_VIEW: CaseView = {
  case_id: 'case_contract_shape',
  case_version: 1,
  input_version: 1,
  status: 'AWAITING_APPROVAL',
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  statements: [
    {
      statement_id: 'stmt_contract',
      kind: 'ORIGINAL',
      raw_text: 'Contract-shaped fixture statement.',
      submitted_at: '2026-10-01T00:00:00Z',
    },
  ],
  evidence: [],
  order_snapshot: {
    snapshot_id: 'snap_contract',
    order_id: 'ord_contract_1',
    provider_id: 'provider_demo_au',
    snapshot_version: 1,
    purchased_at: '2026-09-30T00:00:00Z',
    currency: 'AUD',
    line_items: [
      {
        line_item_id: 'li_1',
        sku: 'SKU-CONTRACT',
        description: 'Contract Shaped Widget',
        quantity: 2,
        unit_price_minor: 1250,
      },
    ],
    retrieved_at: '2026-09-30T00:01:00Z',
  },
  current_proposal: {
    proposal_id: 'prop_contract',
    proposal_version: 1,
    recommended_action: 'PROPOSE_REFUND',
    confidence: 0.5,
    model_run: { model_id: 'model-contract-test', prompt_version: 'contract-v1' },
    rationale: 'Contract-shaped rationale.',
    created_at: '2026-10-01T00:00:00Z',
  },
  current_review: {
    review_id: 'rev_contract',
    outcome: 'PASS',
    reviewed_at: '2026-10-01T00:00:00Z',
    findings: [
      {
        finding_id: 'f_contract_1',
        category: 'SUPPORT',
        severity: 'INFO',
        message: 'Contract-shaped finding.',
      },
    ],
  },
  // The v1 ActionPreview carries only preview_id / scope / scope_fingerprint,
  // so a contract-shaped preview has no operation_type or details.
  action_preview: {
    preview_id: 'prev_contract',
    scope_fingerprint: CONTRACT_FINGERPRINT,
    scope: {
      case_id: 'case_contract_shape',
      input_version: 1,
      proposal_id: 'prop_contract',
      proposal_version: 1,
      review_id: 'rev_contract',
      parcel_id: 'parcel_contract',
      commands: [
        {
          command_id: 'cmd_contract_return',
          type: 'CREATE_RETURN',
          provider_id: 'provider_demo_au',
          parameters: {
            order_id: 'ord_contract_1',
            line_items: [{ line_item_id: 'li_1', quantity: 2 }],
            parcel_id: 'parcel_contract',
          },
        },
        {
          command_id: 'cmd_contract_label',
          type: 'GENERATE_LABEL',
          provider_id: 'provider_demo_au',
          parameters: {
            parcel_id: 'parcel_contract',
            return_command_id: 'cmd_contract_return',
            label_format: 'PDF',
            chargeable: false,
          },
        },
      ],
      currency: 'AUD',
      amount_ceiling_minor: 0,
      expires_at: '2026-10-01T00:05:00Z',
      allowlist_version: 'allowlist-contract-v1',
      environment: 'SIMULATED',
    },
  },
};

const CONTRACT_SUMMARY = {
  case_id: 'case_contract_shape',
  case_version: 1,
  input_version: 1,
  status: 'AWAITING_APPROVAL' as const,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  issue_category: 'CHANGE_OF_MIND' as const,
  current_risk_outcome: 'PASS' as const,
};

describe('FounderConsole failure and live-mode paths', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(isMockMode).mockReturnValue(true);
    vi.mocked(listFounderCases).mockResolvedValue({ items: [CONTRACT_SUMMARY], next_cursor: undefined });
    vi.mocked(getFounderCase).mockResolvedValue(CONTRACT_SHAPED_VIEW);
    vi.mocked(listFounderCaseAudit).mockResolvedValue([]);
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('labels the fixed rule-based proposal as such and shows no model confidence (#111 item 4)', async () => {
    vi.mocked(getFounderCase).mockResolvedValue({
      ...CONTRACT_SHAPED_VIEW,
      current_proposal: {
        ...CONTRACT_SHAPED_VIEW.current_proposal!,
        confidence: 0,
        model_run: { model_id: 'fixture-no-live-model', prompt_version: 'fixed-synthetic-no-model-v1' },
      },
    });
    render(<FounderConsole />);

    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    expect(await screen.findByText('Fixed rule-based proposal (no model)')).toBeInTheDocument();
    expect(screen.getByText('Assessment Proposal')).toBeInTheDocument();
    expect(screen.queryByText('Model Confidence')).not.toBeInTheDocument();
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
    expect(screen.queryByText(/AI Proposal|AI Confidence|Autonomous|Member [AC]/)).not.toBeInTheDocument();
  });

  it('shows no mock store label in Live API mode (#111 item 3)', async () => {
    vi.mocked(isMockMode).mockReturnValue(false);
    render(<FounderConsole />);

    expect(await screen.findByText('case_contract_shape')).toBeInTheDocument();
    expect(screen.queryByText(/store_demo/)).not.toBeInTheDocument();
    expect(screen.queryByText(/UC-0|OF-006/)).not.toBeInTheDocument();
  });

  it('renders a contract-shaped order, proposal and review without crashing or showing NaN', async () => {
    render(<FounderConsole />);

    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    // Proposal uses recommended_action / confidence.
    expect(await screen.findByText('PROPOSE_REFUND')).toBeInTheDocument();
    expect(screen.getByText('50%')).toBeInTheDocument();

    // Review uses outcome / findings.
    expect(screen.getAllByText('PASS').length).toBeGreaterThan(0);
    expect(screen.getByText('Contract-shaped finding.')).toBeInTheDocument();

    // The demo-only extension fields are absent from a contract-shaped response,
    // so their tiles are not shown at all (#111 item 3) instead of fabricating a
    // value or showing a placeholder: no refund amount, return-label or risk-score
    // tile and no "Australia Post"/"Waived" claim. The proposal names its model
    // and keeps its real 50% confidence; there is no summary or citation block.
    expect(screen.queryByText('Refund Amount')).not.toBeInTheDocument();
    expect(screen.queryByText('Return Label Required')).not.toBeInTheDocument();
    expect(screen.queryByText('Risk Score')).not.toBeInTheDocument();
    expect(screen.queryByText(/Waived|Australia Post/)).not.toBeInTheDocument();
    expect(screen.getByText('Model model-contract-test (prompt contract-v1)')).toBeInTheDocument();
    expect(screen.queryByText(/Reviewer Summary/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Statutory & Policy Citations/)).not.toBeInTheDocument();

    // The contract-shaped Action Preview renders its real scope, and shows no
    // empty demo-only "Operation Type:" / "Parameters:" rows.
    expect(screen.getByText(/Execution Preview \(Operations Service\)/)).toBeInTheDocument();
    expect(screen.getByText('prev_contract')).toBeInTheDocument();
    expect(screen.getByText(CONTRACT_FINGERPRINT)).toBeInTheDocument();
    expect(screen.getByText('CREATE_RETURN')).toBeInTheDocument();
    expect(screen.getByText('GENERATE_LABEL')).toBeInTheDocument();
    expect(screen.queryByText('Operation Type:')).not.toBeInTheDocument();
    expect(screen.queryByText('Parameters:')).not.toBeInTheDocument();
    expect(screen.queryByText(/GENERATE_RETURN_CONSIGNMENT/)).not.toBeInTheDocument();

    // Order uses line_items / unit_price_minor and computes the total.
    fireEvent.click(screen.getByRole('button', { name: /Order & Facts Projection/i }));
    expect(await screen.findByText('ord_contract_1')).toBeInTheDocument();
    expect(screen.getByText('Contract Shaped Widget')).toBeInTheDocument();
    expect(screen.getByText(/Total:\s*\$25\.00/)).toBeInTheDocument();

    expect(document.body.textContent).not.toMatch(/NaN/);
  });

  it('shows an audit failure and never renders the recorded-events banner', async () => {
    vi.mocked(listFounderCaseAudit).mockRejectedValue(
      new ApiError(503, 'audit store unavailable', 'AUDIT_UNAVAILABLE')
    );

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Tamper-Evident Audit Chain/i }));

    expect(await screen.findByText(/Audit chain retrieval failed/i)).toBeInTheDocument();
    expect(screen.queryByText(/Recorded Audit Events:/i)).not.toBeInTheDocument();
  });

  it('live mode: sends an APPROVE bound to the proposal and preview from the server case view', async () => {
    vi.mocked(isMockMode).mockReturnValue(false);
    vi.mocked(recordFounderDecision).mockResolvedValue({
      case_id: 'case_contract_shape',
      case_version: 2,
      decision_id: 'dec_live',
      decision: 'APPROVE',
      accepted_at: '2026-10-22T00:00:00Z',
      processing_status: 'ACCEPTED',
      approval_id: 'appr_live',
    });

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    expect(await screen.findByText(/Live Mode: decisions are sent to the server/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Approve Return/i }));

    // Before confirming, the dialog shows the preview identity and the exact scope.
    const dialog = await screen.findByRole('dialog', { name: /Confirm Founder Decision: APPROVE/i });
    const field = (label: string) => {
      const value = within(dialog).getByText(label).nextElementSibling;
      if (!value) throw new Error(`no value for ${label}`);
      return value;
    };
    expect(field('Preview ID')).toHaveTextContent('prev_contract');
    expect(field('Scope fingerprint')).toHaveTextContent(CONTRACT_FINGERPRINT);
    expect(field('Case / input')).toHaveTextContent('case_contract_shape · input v1');
    expect(field('Proposal / review')).toHaveTextContent('prop_contract v1 · rev_contract');
    expect(field('Parcel')).toHaveTextContent('parcel_contract');
    expect(field('Commands (2)')).toHaveTextContent(
      'CREATE_RETURN · id cmd_contract_return · via provider_demo_au (order_id: ord_contract_1, line_items: [{"line_item_id":"li_1","quantity":2}], parcel_id: parcel_contract)'
    );
    expect(field('Commands (2)')).toHaveTextContent(
      'GENERATE_LABEL · id cmd_contract_label · via provider_demo_au (parcel_id: parcel_contract, return_command_id: cmd_contract_return, label_format: PDF, chargeable: false)'
    );
    expect(field('Amount ceiling')).toHaveTextContent('$0.00 AUD');
    expect(field('Expires')).toHaveTextContent(formatDate('2026-10-01T00:05:00Z'));
    expect(field('Expires')).toHaveAttribute('title', '2026-10-01T00:05:00Z');
    expect(field('Environment')).toHaveTextContent('SIMULATED · allowlist allowlist-contract-v1');

    fireEvent.change(within(dialog).getByPlaceholderText(/Record justification for statutory audit/i), {
      target: { value: '  Exact scope reviewed.  ' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /Record decision/i }));

    await waitFor(() => expect(recordFounderDecision).toHaveBeenCalledTimes(1));
    const [caseId, body, key] = vi.mocked(recordFounderDecision).mock.calls[0];
    expect(caseId).toBe('case_contract_shape');
    // Every binding value is copied from the case view; nothing is invented.
    expect(body).toStrictEqual({
      expected_case_version: 1,
      decision: 'APPROVE',
      reason: 'Exact scope reviewed.',
      proposal_id: 'prop_contract',
      proposal_version: 1,
      preview_id: 'prev_contract',
      scope_fingerprint: CONTRACT_FINGERPRINT,
    });
    expect(key).toMatch(/^[A-Za-z0-9._:-]{8,128}$/);
    await waitFor(() => {
      expect(screen.queryByText(/Confirm Founder Decision: APPROVE/i)).not.toBeInTheDocument();
    });
  });

  it('live mode: keeps Approve disabled with a reason when the server sent no action preview', async () => {
    vi.mocked(isMockMode).mockReturnValue(false);
    vi.mocked(getFounderCase).mockResolvedValue({ ...CONTRACT_SHAPED_VIEW, action_preview: undefined });

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    expect(await screen.findByText(/This case view has none, so approval is unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve Return/i })).toBeDisabled();
    // Decisions that need only the proposal stay available.
    expect(screen.getByRole('button', { name: /^Reject$/i })).toBeEnabled();
  });

  it('live mode: shows a server refusal in the dialog and does not treat it as success', async () => {
    vi.mocked(isMockMode).mockReturnValue(false);
    vi.mocked(recordFounderDecision).mockRejectedValue(
      new ApiError(409, 'The request is not available in the current state.', 'INVALID_STATE')
    );

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('button', { name: /^Reject$/i }));
    fireEvent.change(await screen.findByPlaceholderText(/Record justification for statutory audit/i), {
      target: { value: 'Outside the policy window.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Record decision/i }));

    expect(
      await screen.findByText('[INVALID_STATE] The request is not available in the current state.')
    ).toBeInTheDocument();
    expect(screen.getByText(/Confirm Founder Decision: REJECT/i)).toBeInTheDocument();
    expect(vi.mocked(recordFounderDecision).mock.calls[0][1]).toStrictEqual({
      expected_case_version: 1,
      decision: 'REJECT',
      reason: 'Outside the policy window.',
      proposal_id: 'prop_contract',
      proposal_version: 1,
    });
    // No reload of the case as if the decision had been accepted.
    expect(getFounderCase).toHaveBeenCalledTimes(1);
  });

  it('live mode: a 409 STALE_CASE_VERSION reloads the case behind the dialog (#122 item 2)', async () => {
    vi.mocked(isMockMode).mockReturnValue(false);
    const newer: CaseView = { ...CONTRACT_SHAPED_VIEW, case_version: 2, updated_at: '2026-10-01T00:10:00Z' };
    vi.mocked(getFounderCase).mockResolvedValueOnce(CONTRACT_SHAPED_VIEW).mockResolvedValue(newer);
    vi.mocked(recordFounderDecision)
      .mockRejectedValueOnce(new ApiError(409, 'The case version has changed.', 'STALE_CASE_VERSION'))
      .mockResolvedValue({
        case_id: 'case_contract_shape',
        case_version: 3,
        decision_id: 'dec_after_reload',
        decision: 'REJECT',
        accepted_at: '2026-10-22T00:00:00Z',
        processing_status: 'ACCEPTED',
      });

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('button', { name: /^Reject$/i }));
    fireEvent.change(await screen.findByPlaceholderText(/Record justification for statutory audit/i), {
      target: { value: 'Outside the policy window.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Record decision/i }));

    // docs/09: reload, then confirm the current version. The server's message stays.
    expect(
      await screen.findByText(
        '[STALE_CASE_VERSION] The case version has changed. The case changed; the view was reloaded. Check it and decide again.'
      )
    ).toBeInTheDocument();
    const dialog = screen.getByRole('dialog', { name: /Confirm Founder Decision: REJECT/i });
    expect(getFounderCase).toHaveBeenCalledTimes(2);
    expect(listFounderCaseAudit).toHaveBeenCalledTimes(2);
    expect(within(dialog).getByText(/\(v2\)/)).toBeInTheDocument();
    expect(vi.mocked(recordFounderDecision).mock.calls[0][1]).toMatchObject({ expected_case_version: 1 });

    // Deciding again sends the reloaded version under a new request key.
    fireEvent.click(within(dialog).getByRole('button', { name: /Record decision/i }));
    await waitFor(() => expect(recordFounderDecision).toHaveBeenCalledTimes(2));
    const [first, second] = vi.mocked(recordFounderDecision).mock.calls;
    expect(second[1]).toMatchObject({ expected_case_version: 2, decision: 'REJECT' });
    expect(second[2]).not.toBe(first[2]);
  });

  it('shows a case that cannot be opened on the page, not in a browser alert (#122 item 1)', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    vi.mocked(getFounderCase).mockRejectedValue(new ApiError(404, 'Case not found.', 'NOT_FOUND'));

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not open case_contract_shape: [NOT_FOUND] Case not found.'
    );
    expect(screen.queryByText(/Loading case details/i)).not.toBeInTheDocument();
    expect(alertSpy).not.toHaveBeenCalled();
    alertSpy.mockRestore();
  });

  describe('auto-refresh (#111 item 2)', () => {
    const setVisibility = (state: DocumentVisibilityState) => {
      Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
    };

    beforeEach(() => {
      // Only the interval is faked, so Testing Library's own timers keep running.
      vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
      setVisibility('visible');
    });

    afterEach(() => {
      vi.useRealTimers();
      setVisibility('visible');
    });

    it('re-reads the open case every 5 s, pauses while a decision is confirmed and stops at a final status', async () => {
      const completed: CaseView = {
        ...CONTRACT_SHAPED_VIEW,
        case_version: 3,
        status: 'COMPLETED',
        action_preview: undefined,
      };
      vi.mocked(getFounderCase)
        .mockResolvedValueOnce(CONTRACT_SHAPED_VIEW)
        .mockResolvedValueOnce(CONTRACT_SHAPED_VIEW)
        .mockResolvedValue(completed);

      render(<FounderConsole />);
      fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
      expect(await screen.findByText('Updates every 5 seconds')).toBeInTheDocument();
      expect(getFounderCase).toHaveBeenCalledTimes(1);

      // Nothing is read while the Founder confirms a decision.
      fireEvent.click(screen.getByRole('button', { name: /^Reject$/i }));
      expect(await screen.findByText(/Confirm Founder Decision: REJECT/i)).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(15000);
      });
      expect(getFounderCase).toHaveBeenCalledTimes(1);
      fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));

      // Nothing is read while the tab is hidden.
      setVisibility('hidden');
      act(() => {
        vi.advanceTimersByTime(15000);
      });
      expect(getFounderCase).toHaveBeenCalledTimes(1);
      setVisibility('visible');

      act(() => {
        vi.advanceTimersByTime(5000);
      });
      await waitFor(() => expect(getFounderCase).toHaveBeenCalledTimes(2));
      act(() => {
        vi.advanceTimersByTime(5000);
      });
      await waitFor(() => expect(getFounderCase).toHaveBeenCalledTimes(3));

      // The third read is COMPLETED, a final status, so polling stops.
      expect(await screen.findByText('COMPLETED')).toBeInTheDocument();
      expect(screen.queryByText('Updates every 5 seconds')).not.toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(30000);
      });
      expect(getFounderCase).toHaveBeenCalledTimes(3);
    });

    it('reloads the queue when the window regains focus, so a case lodged meanwhile appears', async () => {
      vi.mocked(listFounderCases)
        .mockResolvedValueOnce({ items: [CONTRACT_SUMMARY], next_cursor: undefined })
        .mockResolvedValue({
          items: [CONTRACT_SUMMARY, { ...CONTRACT_SUMMARY, case_id: 'case_lodged_meanwhile', status: 'SUBMITTED' }],
          next_cursor: undefined,
        });

      render(<FounderConsole />);
      expect(await screen.findByText('case_contract_shape')).toBeInTheDocument();
      expect(screen.queryByText('case_lodged_meanwhile')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^Refresh$/ })).toBeInTheDocument();

      fireEvent.focus(window);

      expect(await screen.findByText('case_lodged_meanwhile')).toBeInTheDocument();
      expect(listFounderCases).toHaveBeenLastCalledWith(undefined, 20);
    });
  });

  it('live mode: reuses the request key after a 503 and mints a new one when the rationale changes', async () => {
    vi.mocked(isMockMode).mockReturnValue(false);
    vi.mocked(recordFounderDecision).mockRejectedValue(
      new ApiError(503, 'The service is temporarily unavailable; keep the original request key.', 'INTERNAL_ERROR')
    );

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('button', { name: /^Reject$/i }));
    const rationale = await screen.findByPlaceholderText(/Record justification for statutory audit/i);
    const confirm = screen.getByRole('button', { name: /Record decision/i });

    fireEvent.change(rationale, { target: { value: 'First rationale.' } });
    fireEvent.click(confirm);
    expect(await screen.findByText(/The outcome is unknown/i)).toBeInTheDocument();

    await waitFor(() => expect(confirm).toBeEnabled());
    fireEvent.click(confirm);
    await waitFor(() => expect(recordFounderDecision).toHaveBeenCalledTimes(2));

    await waitFor(() => expect(confirm).toBeEnabled());
    fireEvent.change(rationale, { target: { value: 'Second rationale.' } });
    fireEvent.click(confirm);
    await waitFor(() => expect(recordFounderDecision).toHaveBeenCalledTimes(3));

    const keys = vi.mocked(recordFounderDecision).mock.calls.map((call) => call[2]);
    expect(keys[1]).toBe(keys[0]);
    expect(keys[2]).not.toBe(keys[0]);
  });

  describe('live analytics', () => {
    // Latency tier 0, as the server reports today: no samples, so no p50/p95.
    // Zero buckets are omitted, so only two statuses and one risk outcome arrive.
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

    // An empty cohort: every bucket omitted and the applied filters echoed.
    const EMPTY_FILTERED_SNAPSHOT: AnalyticsSnapshot = {
      as_of: '2026-10-22T09:31:00Z',
      filters: {
        created_from: '2026-10-01T00:00:00Z',
        created_before: '2026-10-08T00:00:00Z',
        status: 'MANUAL_HANDLED',
      },
      case_count: 0,
      cases_by_status: [],
      current_risk_counts: [],
      cases_without_current_review: 0,
      proposal_latency: {
        metric_version: 'proposal-latency-v1',
        sample_count: 0,
        failed_count: 0,
        unmeasured_count: 0,
      },
    };

    // The element that holds a label and its value, so each assertion is
    // anchored to one tile or count.
    const holder = (label: string) => {
      const element = screen.getByText(label).parentElement;
      if (!element) throw new Error(`no element for ${label}`);
      return element;
    };
    const panel = (heading: string) => {
      const element = screen.getByText(heading).closest('h3')?.parentElement;
      if (!element) throw new Error(`no panel for ${heading}`);
      return element;
    };

    it('renders omitted buckets, absent percentiles and the four latency count fields', async () => {
      vi.mocked(isMockMode).mockReturnValue(false);
      vi.mocked(getFounderAnalytics).mockResolvedValue(TIER0_SNAPSHOT);

      render(<FounderConsole />);
      fireEvent.click(screen.getByRole('button', { name: /Analytics Dashboard/i }));

      expect(await screen.findByText('Total Case Volume')).toBeInTheDocument();
      expect(getFounderAnalytics).toHaveBeenCalledWith({});

      expect(holder('p50 Median Latency')).toHaveTextContent('—');
      expect(holder('p50 Median Latency')).toHaveTextContent('Not measured (no samples)');
      expect(holder('p95 Latency SLA')).toHaveTextContent('—');
      expect(holder('p95 Latency SLA')).toHaveTextContent('Not measured (no samples)');

      expect(holder('Measured:')).toHaveTextContent('Measured: 0');
      expect(holder('Failed:')).toHaveTextContent('Failed: 1');
      expect(holder('Unmeasured:')).toHaveTextContent('Unmeasured: 2');
      expect(holder('As of:')).toHaveTextContent(`As of: ${formatDate(TIER0_SNAPSHOT.as_of)}`);
      expect(holder('Filters applied:')).toHaveTextContent('Filters applied: none');

      // Only the buckets the server sent are drawn, in the order it sent them.
      const statusPanel = panel('Case Status Distribution');
      expect(within(statusPanel).getAllByText(/^[A-Z_]+$/).map((el) => el.textContent)).toEqual([
        'SUBMITTED',
        'REJECTED',
      ]);
      expect(within(statusPanel).getByText('2 (67%)')).toBeInTheDocument();
      const riskPanel = panel('Risk Review Outcome Distribution');
      expect(within(riskPanel).getAllByText(/^[A-Z_]+$/).map((el) => el.textContent)).toEqual(['PASS']);

      expect(document.body.textContent).not.toMatch(/NaN/);
    });

    it('sends the contract filters from the form and shows the echoed filters and empty cohort', async () => {
      vi.mocked(isMockMode).mockReturnValue(false);
      vi.mocked(getFounderAnalytics)
        .mockResolvedValueOnce(TIER0_SNAPSHOT)
        .mockResolvedValueOnce(EMPTY_FILTERED_SNAPSHOT)
        .mockResolvedValue(TIER0_SNAPSHOT);

      render(<FounderConsole />);
      fireEvent.click(screen.getByRole('button', { name: /Analytics Dashboard/i }));
      expect(await screen.findByText('Total Case Volume')).toBeInTheDocument();

      fireEvent.change(screen.getByLabelText(/Created from/i), { target: { value: '2026-10-01' } });
      fireEvent.change(screen.getByLabelText(/Created before/i), { target: { value: '2026-10-08' } });
      fireEvent.change(screen.getByLabelText(/Current status/i), { target: { value: 'MANUAL_HANDLED' } });
      fireEvent.click(screen.getByRole('button', { name: /Apply Filters/i }));

      await waitFor(() => expect(getFounderAnalytics).toHaveBeenCalledTimes(2));
      expect(vi.mocked(getFounderAnalytics).mock.calls[1][0]).toStrictEqual({
        created_from: '2026-10-01T00:00:00Z',
        created_before: '2026-10-08T00:00:00Z',
        status: 'MANUAL_HANDLED',
      });

      expect(await screen.findByText('No cases in this snapshot.')).toBeInTheDocument();
      expect(screen.getByText('No case has a current risk review in this snapshot.')).toBeInTheDocument();
      expect(holder('Filters applied:')).toHaveTextContent(
        'created_from=2026-10-01T00:00:00Z, created_before=2026-10-08T00:00:00Z, status=MANUAL_HANDLED'
      );
      expect(document.body.textContent).not.toMatch(/NaN/);

      // A reversed window is stopped in the browser instead of being sent for a 422.
      fireEvent.change(screen.getByLabelText(/Created from/i), { target: { value: '2026-10-09' } });
      fireEvent.click(screen.getByRole('button', { name: /Apply Filters/i }));
      expect(await screen.findByText(/"Created from" must be earlier than "Created before"/)).toBeInTheDocument();
      expect(getFounderAnalytics).toHaveBeenCalledTimes(2);

      fireEvent.click(screen.getByRole('button', { name: /^Clear$/i }));
      await waitFor(() => expect(getFounderAnalytics).toHaveBeenCalledTimes(3));
      expect(vi.mocked(getFounderAnalytics).mock.calls[2][0]).toStrictEqual({});
    });
  });
});
