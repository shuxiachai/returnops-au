import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { FounderConsole } from './FounderConsole';
import type { AnalyticsSnapshot, AuditEvent, CaseView } from '../types/domain';
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
    listFounderCaseAuditPage: vi.fn(),
    recordFounderDecision: vi.fn(),
    getFounderAnalytics: vi.fn(),
  };
});

import {
  ApiError,
  isMockMode,
  listFounderCases,
  getFounderCase,
  listFounderCaseAuditPage,
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
      expires_at: new Date(Date.now() + 300000).toISOString(),
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
    vi.mocked(listFounderCaseAuditPage).mockResolvedValue({ items: [], next_cursor: undefined });
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

    // Proposal uses recommended_action / confidence. The outcome is shown in words,
    // with the contract value on hover, and the tiles wrap long words.
    const outcome = await screen.findByText('Refund');
    expect(outcome).toHaveAttribute('title', 'PROPOSE_REFUND');
    expect(outcome.closest('.grid')).toHaveClass('break-words');
    expect(screen.queryByText('PROPOSE_REFUND')).not.toBeInTheDocument();
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
    expect(screen.getByText('What an approval would allow')).toBeInTheDocument();
    expect(screen.getByText('prev_contract')).toBeInTheDocument();
    expect(screen.getByText(CONTRACT_FINGERPRINT)).toBeInTheDocument();
    expect(screen.getByText('CREATE_RETURN')).toBeInTheDocument();
    expect(screen.getByText('GENERATE_LABEL')).toBeInTheDocument();
    expect(screen.queryByText('Operation Type:')).not.toBeInTheDocument();
    expect(screen.queryByText('Parameters:')).not.toBeInTheDocument();
    expect(screen.queryByText(/GENERATE_RETURN_CONSIGNMENT/)).not.toBeInTheDocument();

    // Order uses line_items / unit_price_minor and computes the total.
    fireEvent.click(screen.getByRole('tab', { name: /Order & Facts/i }));
    expect(await screen.findByText('ord_contract_1')).toBeInTheDocument();
    expect(screen.getByText('Contract Shaped Widget')).toBeInTheDocument();
    expect(screen.getByText(/Total:\s*\$25\.00/)).toBeInTheDocument();

    expect(document.body.textContent).not.toMatch(/NaN/);
  });

  it('shows an audit failure and never renders the recorded-events banner', async () => {
    vi.mocked(listFounderCaseAuditPage).mockRejectedValue(
      new ApiError(503, 'audit store unavailable', 'AUDIT_UNAVAILABLE')
    );

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('tab', { name: /Audit History/i }));

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
    expect(await screen.findByText(/The server checks every decision again/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Approve Return/i }));

    // Before confirming, the dialog shows the preview identity and the exact scope.
    const dialog = await screen.findByRole('dialog', { name: /Confirm: Approve return/i });
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
    // The preview's own expiry, not a fixed date: an expired preview correctly
    // disables Approve (#122 item 12).
    expect(field('Expires')).toHaveTextContent(formatDate(CONTRACT_SHAPED_VIEW.action_preview!.scope.expires_at));
    expect(field('Expires')).toHaveAttribute('title', CONTRACT_SHAPED_VIEW.action_preview!.scope.expires_at);
    expect(field('Environment')).toHaveTextContent('SIMULATED · allowlist allowlist-contract-v1');

    fireEvent.change(within(dialog).getByPlaceholderText(/Why are you making this decision/i), {
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
      expect(screen.queryByText(/Confirm: Approve return/i)).not.toBeInTheDocument();
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
    fireEvent.change(await screen.findByPlaceholderText(/Why are you making this decision/i), {
      target: { value: 'Outside the policy window.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Record decision/i }));

    expect(
      await screen.findByText('[INVALID_STATE] The request is not available in the current state.')
    ).toBeInTheDocument();
    expect(screen.getByText(/Confirm: Reject/i)).toBeInTheDocument();
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
    fireEvent.change(await screen.findByPlaceholderText(/Why are you making this decision/i), {
      target: { value: 'Outside the policy window.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Record decision/i }));

    // docs/09: reload, then confirm the current version. The server's message stays.
    expect(
      await screen.findByText(
        '[STALE_CASE_VERSION] The case version has changed. The case changed; the view was reloaded. Check it and decide again.'
      )
    ).toBeInTheDocument();
    const dialog = screen.getByRole('dialog', { name: /Confirm: Reject/i });
    expect(getFounderCase).toHaveBeenCalledTimes(2);
    expect(listFounderCaseAuditPage).toHaveBeenCalledTimes(2);
    expect(within(dialog).getByText(/\(version 2\)/)).toBeInTheDocument();
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

  it('shows a review without an outcome in neutral colours, not as a pass (C review of #130)', async () => {
    vi.mocked(getFounderCase).mockResolvedValue({
      ...CONTRACT_SHAPED_VIEW,
      current_review: { ...CONTRACT_SHAPED_VIEW.current_review!, outcome: undefined },
    } as unknown as CaseView);

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    const header = (await screen.findByRole('heading', { name: 'Risk Review' })).parentElement?.parentElement;
    if (!header) throw new Error('no Risk Review header');
    const badge = within(header).getByText('—');
    expect(badge.className).toMatch(/bg-gray-100/);
    expect(badge.className).not.toMatch(/emerald/);
  });

  describe('escalated case without a proposal (S3 live manual handling)', () => {
    // A SYN-CONFLICT case after order investigation: contract OrderLookupBlock, no proposal.
    const BLOCKED_VIEW: CaseView = {
      ...CONTRACT_SHAPED_VIEW,
      case_version: 4,
      status: 'ESCALATED',
      current_proposal: undefined,
      current_review: undefined,
      action_preview: undefined,
      order_snapshot: undefined,
      order_lookup_block: {
        block_id: 'block_conflict',
        case_id: 'case_contract_shape',
        input_version: 1,
        status: 'CONFLICT',
        message: 'The authorized order reference is ambiguous.',
        occurred_at: '2026-10-25T00:00:00Z',
      },
    };

    it('shows why the case is blocked and sends MANUAL_HANDLING bound to the block only', async () => {
      vi.mocked(isMockMode).mockReturnValue(false);
      // After the accepted decision the server's view still carries the block, now NOTIFICATION_PENDING,
      // with the decision record and the queued notice (manual_decision.py; no worker has sent it).
      vi.mocked(getFounderCase)
        .mockResolvedValueOnce(BLOCKED_VIEW)
        .mockResolvedValue({
          ...BLOCKED_VIEW,
          status: 'NOTIFICATION_PENDING',
          case_version: 5,
          decisions: [
            {
              decision_id: 'dec_manual_live',
              case_id: 'case_contract_shape',
              order_lookup_block_id: 'block_conflict',
              decision: 'MANUAL_HANDLING',
              principal_id: 'demo_founder',
              reason: 'The order reference is ambiguous; I will contact the customer.',
              decided_at: '2026-10-25T00:01:00Z',
            },
          ],
          notifications: [
            {
              notification_id: 'note_manual_live',
              case_id: 'case_contract_shape',
              case_version: 5,
              status: 'PENDING',
              outcome: 'MANUAL_HANDLED',
              message: 'The store operator recorded a manual-handling outcome.',
              next_steps: ['Next step: ask the store operator to confirm the contact channel and any further arrangements.'],
              attempt_count: 0,
              updated_at: '2026-10-25T00:01:00Z',
            },
          ],
        });
      vi.mocked(recordFounderDecision).mockResolvedValue({
        case_id: 'case_contract_shape',
        case_version: 5,
        decision_id: 'dec_manual_live',
        decision: 'MANUAL_HANDLING',
        accepted_at: '2026-10-25T00:01:00Z',
        processing_status: 'ACCEPTED',
      });

      render(<FounderConsole />);
      fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

      expect(
        await screen.findByText(/Order lookup blocked: the order reference matches more than one order/)
      ).toBeInTheDocument();
      expect(screen.getByText('The authorized order reference is ambiguous.')).toBeInTheDocument();
      expect(screen.getByText('No active proposal generated for this case yet.')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Approve Return/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /^Reject$/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /^Request Revision$/i })).toBeDisabled();

      fireEvent.click(screen.getByRole('button', { name: /^Manual Takeover$/i }));
      const dialog = await screen.findByRole('dialog', { name: /Confirm: Manual takeover/i });
      expect(within(dialog).getByText('block_conflict')).toBeInTheDocument();
      fireEvent.change(within(dialog).getByPlaceholderText(/Why are you making this decision/i), {
        target: { value: 'The order reference is ambiguous; I will contact the customer.' },
      });
      fireEvent.click(within(dialog).getByRole('button', { name: /Record decision/i }));

      await waitFor(() => expect(recordFounderDecision).toHaveBeenCalledTimes(1));
      const [caseId, body] = vi.mocked(recordFounderDecision).mock.calls[0];
      expect(caseId).toBe('case_contract_shape');
      expect(body).toStrictEqual({
        expected_case_version: 4,
        decision: 'MANUAL_HANDLING',
        reason: 'The order reference is ambiguous; I will contact the customer.',
        order_lookup_block_id: 'block_conflict',
      });

      // The reloaded case opens on what the decision produced (#122 item 4): the
      // manual takeover on the block and the queued notice, not yet sent.
      expect(await screen.findByTitle('NOTIFICATION_PENDING')).toHaveTextContent('Notification Pending');
      expect(screen.getByText('Manual takeover')).toBeInTheDocument();
      expect(screen.getByText(/on order-lookup block block_conflict/)).toBeInTheDocument();
      expect(screen.getByText('Handled manually')).toBeInTheDocument();
      expect(screen.getByText('PENDING')).toBeInTheDocument();
      expect(screen.getByText(/not sent yet/)).toBeInTheDocument();

      // The block reason stays on the proposal tab, but no second manual takeover is offered.
      fireEvent.click(screen.getByRole('tab', { name: /Proposal & Risk Review/i }));
      expect(screen.getByText('The authorized order reference is ambiguous.')).toBeInTheDocument();
      expect(screen.queryByText(/Only the Founder can decide it/)).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^Manual Takeover$/i })).toBeDisabled();
    });

    it('shows the stage and message of a processing failure', async () => {
      vi.mocked(getFounderCase).mockResolvedValue({
        ...BLOCKED_VIEW,
        order_lookup_block: undefined,
        processing_failure: {
          failure_id: 'failure_lookup',
          case_id: 'case_contract_shape',
          input_version: 1,
          stage: 'ORDER_LOOKUP',
          error: {
            error: { code: 'PROVIDER_UNAVAILABLE', message: 'The order service did not answer.', retryable: false },
          },
          occurred_at: '2026-10-25T00:00:00Z',
        },
      });

      render(<FounderConsole />);
      fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

      expect(await screen.findByText('Processing failed at stage ORDER_LOOKUP')).toBeInTheDocument();
      expect(screen.getByText('The order service did not answer.')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^Manual Takeover$/i })).toBeEnabled();
    });

    it('keeps the long target IDs of the confirmation inside a phone screen', async () => {
      vi.mocked(getFounderCase).mockResolvedValue(BLOCKED_VIEW);
      render(<FounderConsole />);
      fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
      fireEvent.click(await screen.findByRole('button', { name: /^Manual Takeover$/i }));

      const dialog = await screen.findByRole('dialog', { name: /Confirm: Manual takeover/i });
      expect(dialog).toHaveClass('min-w-0');
      expect(within(dialog).getByText('block_conflict')).toHaveClass('break-all');
      expect(within(dialog).getByText('case_contract_shape')).toHaveClass('break-all');
    });

    it('reports an accepted decision as recorded when the case cannot be read again afterwards', async () => {
      vi.mocked(isMockMode).mockReturnValue(false);
      vi.mocked(getFounderCase)
        .mockResolvedValueOnce(BLOCKED_VIEW)
        .mockRejectedValue(
          new ApiError(503, 'The service is temporarily unavailable; keep the original request key.', 'INTERNAL_ERROR', undefined, undefined, true)
        );
      vi.mocked(recordFounderDecision).mockResolvedValue({
        case_id: 'case_contract_shape',
        case_version: 5,
        decision_id: 'dec_manual_live',
        decision: 'MANUAL_HANDLING',
        accepted_at: '2026-10-25T00:01:00Z',
        processing_status: 'ACCEPTED',
      });

      render(<FounderConsole />);
      fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
      fireEvent.click(await screen.findByRole('button', { name: /^Manual Takeover$/i }));
      const dialog = await screen.findByRole('dialog', { name: /Confirm: Manual takeover/i });
      fireEvent.change(within(dialog).getByPlaceholderText(/Why are you making this decision/i), {
        target: { value: 'The order reference is ambiguous; I will contact the customer.' },
      });
      fireEvent.click(within(dialog).getByRole('button', { name: /Record decision/i }));

      // The receipt decides what the Founder is told; the failed read only explains the stale view.
      const notice = await screen.findByRole('status');
      expect(notice).toHaveTextContent(
        'Decision recorded: the server accepted MANUAL_HANDLING on case_contract_shape (decision dec_manual_live).'
      );
      expect(notice).toHaveTextContent(
        'The case view could not be refreshed: [INTERNAL_ERROR] The service is temporarily unavailable; keep the original request key. Open the case again to see its current state.'
      );
      expect(screen.queryByText(/Could not open/)).not.toBeInTheDocument();
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      expect(recordFounderDecision).toHaveBeenCalledTimes(1);
    });
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
      expect(await screen.findByText(/Confirm: Reject/i)).toBeInTheDocument();
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
      expect(await screen.findByTitle('COMPLETED')).toHaveTextContent('Completed');
      expect(screen.queryByText('Updates every 5 seconds')).not.toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(30000);
      });
      expect(getFounderCase).toHaveBeenCalledTimes(3);
    });

    it('discards a background read still in flight when the confirmation opens (C review of #130)', async () => {
      vi.mocked(isMockMode).mockReturnValue(false);
      const newer: CaseView = {
        ...CONTRACT_SHAPED_VIEW,
        case_version: 2,
        current_proposal: { ...CONTRACT_SHAPED_VIEW.current_proposal!, proposal_id: 'prop_newer', proposal_version: 2 },
      };
      let answerRead!: (view: CaseView) => void;
      vi.mocked(getFounderCase)
        .mockResolvedValueOnce(CONTRACT_SHAPED_VIEW)
        .mockImplementationOnce(() => new Promise<CaseView>((resolve) => { answerRead = resolve; }));
      vi.mocked(recordFounderDecision).mockResolvedValue({
        case_id: 'case_contract_shape',
        case_version: 2,
        decision_id: 'dec_on_screen_version',
        decision: 'REJECT',
        accepted_at: '2026-10-26T00:00:00Z',
        processing_status: 'ACCEPTED',
      });

      render(<FounderConsole />);
      fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
      expect(await screen.findByText('Updates every 5 seconds')).toBeInTheDocument();

      // A 5 s refresh starts and is still waiting for the server ...
      act(() => {
        vi.advanceTimersByTime(5000);
      });
      await waitFor(() => expect(getFounderCase).toHaveBeenCalledTimes(2));

      // ... while the Founder opens the confirmation for the version on screen.
      fireEvent.click(screen.getByRole('button', { name: /^Reject$/i }));
      const dialog = await screen.findByRole('dialog', { name: /Confirm: Reject/i });
      fireEvent.change(within(dialog).getByPlaceholderText(/Why are you making this decision/i), {
        target: { value: 'Reviewed the version on screen.' },
      });

      // The late answer, a newer version with a new proposal, arrives behind the dialog and is dropped.
      await act(async () => {
        answerRead(newer);
      });
      expect(within(dialog).getByText(/\(version 1\)/)).toBeInTheDocument();
      expect(within(dialog).getByText('prop_contract')).toBeInTheDocument();
      expect(screen.queryByText('prop_newer')).not.toBeInTheDocument();

      fireEvent.click(within(dialog).getByRole('button', { name: /Record decision/i }));
      await waitFor(() => expect(recordFounderDecision).toHaveBeenCalledTimes(1));
      expect(vi.mocked(recordFounderDecision).mock.calls[0][1]).toStrictEqual({
        expected_case_version: 1,
        decision: 'REJECT',
        reason: 'Reviewed the version on screen.',
        proposal_id: 'prop_contract',
        proposal_version: 1,
      });
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
    const rationale = await screen.findByPlaceholderText(/Why are you making this decision/i);
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

      expect(await screen.findByText('Total cases')).toBeInTheDocument();
      expect(getFounderAnalytics).toHaveBeenCalledWith({});

      expect(holder('Typical time to proposal')).toHaveTextContent('—');
      expect(holder('Typical time to proposal')).toHaveTextContent('Not measured (no samples)');
      expect(holder('Slow cases (95th percentile)')).toHaveTextContent('—');
      expect(holder('Slow cases (95th percentile)')).toHaveTextContent('Not measured (no samples)');

      expect(holder('Measured:')).toHaveTextContent('Measured: 0');
      expect(holder('Failed:')).toHaveTextContent('Failed: 1');
      expect(holder('Unmeasured:')).toHaveTextContent('Unmeasured: 2');
      expect(holder('As of:')).toHaveTextContent(`As of: ${formatDate(TIER0_SNAPSHOT.as_of)}`);
      expect(holder('Filters applied:')).toHaveTextContent('Filters applied: none');

      // Only the buckets the server sent are drawn, in the order it sent them.
      const statusPanel = panel('Cases by status');
      // Shown in words, with the contract value as the title (31 October 2026).
      const buckets = within(statusPanel).getAllByTitle(/^[A-Z_]+$/);
      expect(buckets.map((el) => el.getAttribute('title'))).toEqual(['SUBMITTED', 'REJECTED']);
      expect(buckets.map((el) => el.textContent?.trim())).toEqual(['Submitted', 'Rejected']);
      expect(within(statusPanel).getByText('2 (67%)')).toBeInTheDocument();
      const riskPanel = panel('Cases by risk review outcome');
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
      expect(await screen.findByText('Total cases')).toBeInTheDocument();

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

describe('FounderConsole audit paging and the in-flight decision dialog', () => {
  const auditEvent = (n: number): AuditEvent => ({
    event_id: `evt_${n}`,
    case_id: 'case_contract_shape',
    sequence: n,
    event_type: `TEST_EVENT_${String(n).padStart(4, '0')}`,
    actor: 'system',
    occurred_at: '2026-10-01T00:00:00Z',
  });

  const openAudit = async () => {
    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('tab', { name: /Audit History/i }));
  };

  beforeEach(() => {
    localStorage.clear();
    vi.mocked(isMockMode).mockReturnValue(true);
    vi.mocked(listFounderCases).mockResolvedValue({ items: [CONTRACT_SUMMARY], next_cursor: undefined });
    vi.mocked(getFounderCase).mockResolvedValue(CONTRACT_SHAPED_VIEW);
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('follows next_cursor across pages and shows the whole chain (#122 item 13)', async () => {
    vi.mocked(listFounderCaseAuditPage).mockImplementation(async (_caseId, cursor) => {
      if (!cursor) return { items: [auditEvent(1), auditEvent(2)], next_cursor: 'c1' };
      if (cursor === 'c1') return { items: [auditEvent(3)], next_cursor: 'c2' };
      return { items: [auditEvent(4)], next_cursor: undefined };
    });
    await openAudit();

    expect(await screen.findByText(/TEST_EVENT_0004/)).toBeInTheDocument();
    for (const n of [1, 2, 3]) expect(screen.getByText(new RegExp(`TEST_EVENT_000${n}`))).toBeInTheDocument();
    expect(listFounderCaseAuditPage).toHaveBeenNthCalledWith(1, 'case_contract_shape', undefined, 50);
    expect(listFounderCaseAuditPage).toHaveBeenNthCalledWith(2, 'case_contract_shape', 'c1', 50);
    expect(listFounderCaseAuditPage).toHaveBeenNthCalledWith(3, 'case_contract_shape', 'c2', 50);
    expect(screen.queryByText(/Only the first/)).not.toBeInTheDocument();
  });

  it('stops when the server repeats a cursor instead of reading the same page again', async () => {
    let calls = 0;
    vi.mocked(listFounderCaseAuditPage).mockImplementation(async () => {
      calls += 1;
      return { items: [auditEvent(calls)], next_cursor: 'same' };
    });
    await openAudit();

    expect(await screen.findByText(/TEST_EVENT_0002/)).toBeInTheDocument();
    expect(listFounderCaseAuditPage).toHaveBeenCalledTimes(2);
    expect(screen.queryByText(/Only the first/)).not.toBeInTheDocument();
  });

  it('keeps the events it read and says so when the chain is longer than the bound', async () => {
    let calls = 0;
    vi.mocked(listFounderCaseAuditPage).mockImplementation(async () => {
      calls += 1;
      return { items: [auditEvent(calls)], next_cursor: `c${calls}` };
    });
    await openAudit();

    expect(
      await screen.findByText(/Only the first 1000 recorded events were read\. The events shown are real/)
    ).toBeInTheDocument();
    expect(screen.getByText(/TEST_EVENT_0001/)).toBeInTheDocument();
    expect(screen.getByText(/TEST_EVENT_0020/)).toBeInTheDocument();
    expect(listFounderCaseAuditPage).toHaveBeenCalledTimes(20);
  });

  it('freezes X, Cancel and the rationale while a decision is in flight (#122 item 12)', async () => {
    vi.mocked(isMockMode).mockReturnValue(false);
    vi.mocked(listFounderCaseAuditPage).mockResolvedValue({ items: [], next_cursor: undefined });
    let settle!: (error: Error) => void;
    vi.mocked(recordFounderDecision).mockReturnValue(
      new Promise((_resolve, reject) => {
        settle = reject;
      })
    );

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('button', { name: /^Reject$/i }));
    const reason = await screen.findByPlaceholderText(/Why are you making this decision/i);
    fireEvent.change(reason, { target: { value: 'Outside the policy window.' } });
    fireEvent.click(screen.getByRole('button', { name: /Record decision/i }));

    await waitFor(() => expect(screen.getByRole('button', { name: /Submitting/i })).toBeDisabled());
    expect(screen.getByRole('button', { name: 'Close decision confirmation' })).toBeDisabled();
    expect(screen.getByRole('button', { name: /^Cancel$/i })).toBeDisabled();
    expect(reason).toBeDisabled();

    await act(async () => {
      settle(new ApiError(409, 'The request is not available in the current state.', 'INVALID_STATE'));
    });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Close decision confirmation' })).toBeEnabled());
    expect(screen.getByRole('button', { name: /^Cancel$/i })).toBeEnabled();
    expect(reason).toBeEnabled();
  });

  it('marks the case window and the confirmation as modal dialogs, and Escape closes the top one', async () => {
    vi.mocked(listFounderCaseAuditPage).mockResolvedValue({ items: [], next_cursor: undefined });
    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    const caseWindow = await screen.findByRole('dialog', { name: 'Case case_contract_shape' });
    expect(caseWindow).toHaveAttribute('aria-modal', 'true');
    // Keyboard focus starts inside the window, not on the queue behind it.
    expect(await screen.findByRole('button', { name: 'Close case' })).toHaveFocus();

    fireEvent.click(screen.getByRole('button', { name: /^Reject$/i }));
    const confirmation = await screen.findByRole('dialog', { name: /Confirm: Reject/i });
    expect(confirmation).toHaveAttribute('aria-modal', 'true');
    expect(within(confirmation).getByPlaceholderText(/Why are you making this decision/i)).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Confirm:/i })).not.toBeInTheDocument()
    );
    expect(screen.getByRole('dialog', { name: 'Case case_contract_shape' })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('ignores Escape while a decision is being sent', async () => {
    vi.mocked(isMockMode).mockReturnValue(false);
    vi.mocked(listFounderCaseAuditPage).mockResolvedValue({ items: [], next_cursor: undefined });
    let settle!: (error: Error) => void;
    vi.mocked(recordFounderDecision).mockReturnValue(
      new Promise((_resolve, reject) => {
        settle = reject;
      })
    );

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('button', { name: /^Reject$/i }));
    fireEvent.change(await screen.findByPlaceholderText(/Why are you making this decision/i), {
      target: { value: 'Outside the policy window.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Record decision/i }));
    await waitFor(() => expect(screen.getByRole('button', { name: /Submitting/i })).toBeDisabled());

    // Closing now would hide whether the server accepted the decision.
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.getByRole('dialog', { name: /Confirm: Reject/i })).toBeInTheDocument();
    expect(screen.getByRole('dialog', { name: 'Case case_contract_shape' })).toBeInTheDocument();

    await act(async () => {
      settle(new ApiError(409, 'The request is not available in the current state.', 'INVALID_STATE'));
    });
    await waitFor(() => expect(screen.getByRole('button', { name: /^Cancel$/i })).toBeEnabled());
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Confirm:/i })).not.toBeInTheDocument()
    );
  });
});
