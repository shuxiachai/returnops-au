import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import examples from '../../../../contracts/v1/examples.json';
import { CaseOutcomePanel } from './CaseOutcomePanel';
import type {
  ApprovalRecord,
  CaseView,
  FounderDecisionRecord,
  NotificationRecord,
  OperationAttempt,
} from '../types/domain';
import { formatDate } from '../utils/formatters';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return { ...actual, downloadEvidence: vi.fn() };
});

import { ApiError, downloadEvidence } from '../api/client';

// The contract's own example records (contracts/v1/examples.json), so the tab is
// checked against the wire shapes the server sends (#122 item 4).
function example<T>(name: string): T {
  const found = examples.positive.find((item) => item.name === name);
  if (!found) throw new Error(`no contract example ${name}`);
  return structuredClone(found.value) as unknown as T;
}

const DECISION = example<FounderDecisionRecord>('founder-decision-record');
const APPROVAL = example<ApprovalRecord>('approval-record');
const RETURN_OPERATION = example<OperationAttempt>('operation-success');
const UNKNOWN_OPERATION = example<OperationAttempt>('operation-unknown');
const SENT_NOTICE = example<NotificationRecord>('notification-sent');
const FAILED_NOTICE = example<NotificationRecord>('notification-failed');
const LABEL_ID = 'glabel_' + 'ab'.repeat(32);
// The contract has no GENERATE_LABEL example, so the return example is turned into
// the label operation of the same approval (OperationResult's second branch).
const LABEL_OPERATION: OperationAttempt = {
  ...RETURN_OPERATION,
  operation_id: 'operation-label-001',
  command_id: 'command-label-001',
  idempotency_key: 'operation-label-key-001',
  result: { type: 'GENERATE_LABEL', provider_label_id: 'provider-label-001', parcel_id: 'parcel-demo-001', label_evidence_id: LABEL_ID },
};

const BASE: CaseView = {
  case_id: 'case-demo-001',
  case_version: 11,
  input_version: 1,
  status: 'COMPLETED',
  created_at: '2026-09-07T01:00:00Z',
  updated_at: '2026-09-07T02:00:00Z',
  statements: [],
  evidence: [],
};

const COMPLETED: CaseView = {
  ...BASE,
  decisions: [DECISION],
  approvals: [APPROVAL],
  operations: [RETURN_OPERATION, LABEL_OPERATION],
  notifications: [SENT_NOTICE],
};

describe('CaseOutcomePanel (#122 item 4; FR-012, docs/08 B2.03)', () => {
  beforeEach(() => {
    vi.mocked(downloadEvidence).mockReset();
  });

  it('shows the decision, the approved scope, both operations and the sent notice of a completed case', () => {
    render(<CaseOutcomePanel caseView={COMPLETED} />);

    const decision = screen.getByText(DECISION.reason).closest('div.p-4') as HTMLElement;
    expect(within(decision).getByText('Approved')).toBeInTheDocument();
    expect(within(decision).getByText(/on proposal proposal-demo-001 v1/)).toBeInTheDocument();
    expect(within(decision).getByText(/approval-demo-001/)).toBeInTheDocument();
    expect(within(decision).getByText(formatDate(DECISION.decided_at))).toBeInTheDocument();

    // The exact scope of the approval: fingerprint, both commands, no payment, expiry.
    expect(screen.getByText(APPROVAL.scope_fingerprint)).toBeInTheDocument();
    expect(screen.getByText('Commands (2)')).toBeInTheDocument();
    expect(screen.getByText(formatDate(APPROVAL.scope.expires_at), { selector: 'dd' })).toBeInTheDocument();

    expect(screen.getByText('Create the simulated return')).toBeInTheDocument();
    expect(screen.getByText('Generate the return label (PDF)')).toBeInTheDocument();
    expect(screen.getAllByText('SUCCEEDED')).toHaveLength(2);
    expect(screen.getByText('Simulated label: not valid for postage.')).toBeInTheDocument();

    expect(screen.getByText('Return created')).toBeInTheDocument();
    expect(screen.getByText('SENT')).toBeInTheDocument();
    expect(screen.getByText(SENT_NOTICE.message)).toBeInTheDocument();
    expect(screen.getByText(SENT_NOTICE.next_steps[0])).toBeInTheDocument();
    expect(screen.getByText(/Attempts: 2/)).toBeInTheDocument();
  });

  it('downloads the generated label through the evidence route with the label evidence ID', async () => {
    vi.mocked(downloadEvidence).mockResolvedValue(undefined);
    render(<CaseOutcomePanel caseView={COMPLETED} />);

    fireEvent.click(screen.getByRole('button', { name: /Download label \(PDF\)/ }));
    await waitFor(() => expect(downloadEvidence).toHaveBeenCalledTimes(1));
    expect(downloadEvidence).toHaveBeenCalledWith(LABEL_ID, 'case-demo-001-return-label.pdf');
    // Only the label operation offers a download.
    expect(screen.getAllByRole('button', { name: /Download label/ })).toHaveLength(1);
  });

  it('shows a refused label download instead of failing silently', async () => {
    vi.mocked(downloadEvidence).mockRejectedValue(new ApiError(403, 'Not allowed to read this file.', 'FORBIDDEN'));
    render(<CaseOutcomePanel caseView={COMPLETED} />);

    fireEvent.click(screen.getByRole('button', { name: /Download label \(PDF\)/ }));
    expect(await screen.findByText(/Label download failed: \[FORBIDDEN\] Not allowed to read this file\./)).toBeInTheDocument();
  });

  it('shows an uncertain operation and a failed notice with the server messages', () => {
    render(
      <CaseOutcomePanel caseView={{ ...COMPLETED, operations: [UNKNOWN_OPERATION], notifications: [FAILED_NOTICE] }} />
    );

    // The type comes from the approved command until the provider confirms a result.
    const operation = screen.getByText('Create the simulated return').closest('div.p-4') as HTMLElement;
    expect(within(operation).getByText('UNKNOWN')).toBeInTheDocument();
    expect(within(operation).getByText(/\[PROVIDER_UNAVAILABLE\] Provider outcome is unknown/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Download label/ })).not.toBeInTheDocument();

    expect(screen.getByText('FAILED')).toBeInTheDocument();
    expect(screen.getByText(/not sent yet/)).toBeInTheDocument();
    expect(screen.getByText(/\[PROVIDER_UNAVAILABLE\] Mock notification delivery failed\./)).toBeInTheDocument();
  });

  it('says plainly when an approval has no operation yet', () => {
    render(<CaseOutcomePanel caseView={{ ...BASE, decisions: [DECISION], approvals: [APPROVAL] }} />);

    expect(screen.getByText(/No operation has been recorded yet/)).toBeInTheDocument();
    expect(screen.getByText('No notice to the customer is recorded yet.')).toBeInTheDocument();
  });

  it('shows a rejection without an approval or operations section', () => {
    const reject: FounderDecisionRecord = {
      decision_id: 'decision-reject-001',
      case_id: 'case-demo-001',
      proposal_id: 'proposal-demo-001',
      proposal_version: 1,
      decision: 'REJECT',
      principal_id: 'founder-demo-001',
      reason: 'Outside the store policy window.',
      decided_at: '2026-09-07T02:00:00Z',
    };
    render(<CaseOutcomePanel caseView={{ ...BASE, status: 'NOTIFICATION_PENDING', decisions: [reject] }} />);

    expect(screen.getByText('Rejected')).toBeInTheDocument();
    expect(screen.queryByText('Approved scope')).not.toBeInTheDocument();
    expect(screen.queryByText('Simulated operations')).not.toBeInTheDocument();
  });

  it('tells the Founder that nothing has been decided yet', () => {
    render(<CaseOutcomePanel caseView={{ ...BASE, status: 'AWAITING_APPROVAL' }} />);

    expect(screen.getByText(/No Founder decision is recorded for this case yet/)).toBeInTheDocument();
  });

  it('wraps a 2,000-character rationale with no break point and lets its script set the direction', () => {
    const reason = 'Twoordersshareonereference'.repeat(74).slice(0, 2000);
    render(<CaseOutcomePanel caseView={{ ...COMPLETED, decisions: [{ ...DECISION, reason }] }} />);

    const text = screen.getByText(reason);
    expect(text).toHaveClass('break-words');
    expect(text).toHaveAttribute('dir', 'auto');
    expect(screen.getByText(SENT_NOTICE.message)).toHaveClass('break-words');
  });
});
