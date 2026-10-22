import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FounderConsole } from './FounderConsole';
import type { CaseView } from '../types/domain';

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
} from '../api/client';

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
    scope_fingerprint: 'fp_contract_shape',
    scope: {
      case_id: 'case_contract_shape',
      input_version: 1,
      proposal_id: 'prop_contract',
      proposal_version: 1,
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
    // so those tiles degrade to a placeholder instead of fabricating a value:
    // no "Australia Post"/"Waived" claim, an "N/A" risk score, and "—" for the
    // refund amount and return-label flag (confidence stays a real 50%) — no
    // summary or citation block at all. Anchor each assertion to its own tile so
    // an unrelated "—"/"N/A" elsewhere on the page cannot satisfy it.
    const tile = (label: string) => {
      const element = screen.getByText(label).parentElement;
      if (!element) throw new Error(`no tile for ${label}`);
      return element;
    };

    expect(tile('Refund Amount')).toHaveTextContent('—');
    expect(tile('Return Label Required')).toHaveTextContent('—');
    expect(tile('Risk Score')).toHaveTextContent('N/A');
    expect(tile('Return Label Required')).not.toHaveTextContent(/Waived|Australia Post/);
    expect(screen.queryByText(/Reviewer Summary/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Statutory & Policy Citations/)).not.toBeInTheDocument();

    // The contract-shaped Action Preview renders, but must not invent an
    // operation type or parameter map the contract never carried.
    expect(screen.getByText(/Governed Execution Preview/)).toBeInTheDocument();
    expect(tile('Operation Type:')).toHaveTextContent(/^Operation Type:$/);
    expect(tile('Parameters:')).toHaveTextContent(/^Parameters:$/);
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

  it('keeps Founder decisions and analytics explicitly unavailable in live mode', async () => {
    vi.mocked(isMockMode).mockReturnValue(false);

    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    expect(await screen.findByText(/Live Mode Notice: Decision recording/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve Return \(UC-04\)/i })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /Analytics Dashboard \(OF-006\)/i }));
    expect(await screen.findByText(/Operations analytics \(OF-006\) backend endpoint is not yet deployed/i)).toBeInTheDocument();
  });
});
