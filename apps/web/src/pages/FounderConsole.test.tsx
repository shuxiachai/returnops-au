import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { FounderConsole } from './FounderConsole';
import { setMockMode } from '../api/client';
import { MOCK_DEMO_003_SCOPE_FINGERPRINT, MOCK_FOUNDER_CASE_VIEWS } from '../api/mockData';

// A Mock Mode decision changes the shared mock case (status, version, records), and
// the decision buttons follow the server's state rules (#104 item 1), so every test
// starts from the case views as loaded.
const MOCK_VIEWS_AT_START = structuredClone(MOCK_FOUNDER_CASE_VIEWS);

describe('FounderConsole (UC-03, UC-04, UC-05 & OF-006)', () => {
  beforeEach(() => {
    localStorage.clear();
    setMockMode(true);
    for (const caseId of Object.keys(MOCK_FOUNDER_CASE_VIEWS)) delete MOCK_FOUNDER_CASE_VIEWS[caseId];
    Object.assign(MOCK_FOUNDER_CASE_VIEWS, structuredClone(MOCK_VIEWS_AT_START));
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders Founder Console heading, quick metric cards, and case queue table', async () => {
    render(<FounderConsole />);

    expect(screen.getByText('Founder Console & Governance')).toBeInTheDocument();
    expect(screen.getByText(/Review cases, record decisions/i)).toBeInTheDocument();

    // Table rows should load from mock data
    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
      expect(screen.getByText('case_demo_002')).toBeInTheDocument();
      expect(screen.getByText('case_demo_003')).toBeInTheDocument();
    });
  });

  it('filters queue cases by status dropdown', async () => {
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'AWAITING_APPROVAL' } });

    await waitFor(() => {
      // case_demo_003 has status AWAITING_APPROVAL
      expect(screen.getByText('case_demo_003')).toBeInTheDocument();
      // case_demo_001 has status AWAITING_INFORMATION so it should be filtered out
      expect(screen.queryByText('case_demo_001')).not.toBeInTheDocument();
    });
  });

  it('offers all sixteen contract statuses in the queue filter, so any case can be found (#111 item 9)', async () => {
    render(<FounderConsole />);
    await waitFor(() => expect(screen.getByText('case_demo_001')).toBeInTheDocument());

    const select = screen.getByRole('combobox', { name: 'Filter the queue by status' });
    const values = within(select).getAllByRole('option').map((option) => (option as HTMLOptionElement).value);
    expect(values).toEqual([
      'ALL',
      'SUBMITTED',
      'AWAITING_INFORMATION',
      'UNDER_INVESTIGATION',
      'POLICY_ASSESSMENT',
      'RISK_REVIEW',
      'AWAITING_APPROVAL',
      'APPROVED',
      'ACTION_IN_PROGRESS',
      'ACTION_FAILED',
      'RECONCILING',
      'ESCALATED',
      'NOTIFICATION_PENDING',
      'NOTIFICATION_FAILED',
      'COMPLETED',
      'REJECTED',
      'MANUAL_HANDLED',
    ]);
    expect(within(select).getByRole('option', { name: 'Notification Pending' })).toBeInTheDocument();
    expect(within(select).getByRole('option', { name: 'Manual Handled' })).toBeInTheDocument();

    // POLICY_ASSESSMENT was not in the old seven-item list; its rows can now be isolated.
    fireEvent.change(select, { target: { value: 'POLICY_ASSESSMENT' } });
    await waitFor(() => {
      expect(screen.getByText('case_demo_007')).toBeInTheDocument();
      expect(screen.queryByText('case_demo_001')).not.toBeInTheDocument();
      expect(screen.queryByText('case_demo_006')).not.toBeInTheDocument();
    });
  });

  it('opens case inspection modal and navigates across multi-tab projections', async () => {
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    // Click inspect on case_demo_001 (first case in table)
    const inspectButtons = screen.getAllByRole('button', { name: /Inspect/i });
    fireEvent.click(inspectButtons[0]);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Order & Facts Projection/i })).toBeInTheDocument();
    });

    // Check Order & Facts tab
    const orderTabBtn = screen.getByRole('button', { name: /Order & Facts Projection/i });
    fireEvent.click(orderTabBtn);

    await waitFor(() => {
      expect(screen.getByText('ord_9042')).toBeInTheDocument();
      expect(screen.getByText(/Navy Blue Cashmere Crewneck/i)).toBeInTheDocument();
    });

    // Check Statements tab
    const statementsTabBtn = screen.getByRole('button', { name: /Customer Statements/i });
    fireEvent.click(statementsTabBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/received the wrong item in my delivery yesterday/i)
      ).toBeInTheDocument();
    });

    // Check Tamper-Evident Audit Chain tab
    const auditTabBtn = screen.getByRole('button', { name: /Tamper-Evident Audit Chain/i });
    fireEvent.click(auditTabBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Recorded Audit Events:/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/CASE_CREATED/i)).toBeInTheDocument();
    });
  });

  it('shows the mock advisory facts card on case_demo_001, marked as mock data (Issue #95)', async () => {
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Filter by Case ID or Category/i), {
      target: { value: 'case_demo_001' },
    });
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Order & Facts Projection/i }));

    const card = await screen.findByRole('region', { name: 'Model extraction (advisory)' });
    expect(within(card).getByText('Mock data: not a model result')).toBeInTheDocument();
    expect(within(card).getByText('WRONG_ITEM')).toBeInTheDocument();
    expect(within(card).getByText('No line items selected (empty list).')).toBeInTheDocument();
  });

  it('shows no advisory facts card on a mock case without facts (Issue #95)', async () => {
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_002')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Filter by Case ID or Category/i), {
      target: { value: 'case_demo_002' },
    });
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Order & Facts Projection/i }));

    expect(await screen.findByText('ord_8819')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Model extraction (advisory)' })).not.toBeInTheDocument();
  });

  it('executes governed APPROVE decision with mandatory rationale', async () => {
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_003')).toBeInTheDocument();
    });

    // Inspect case_demo_003 (third case in table)
    const inspectButtons = screen.getAllByRole('button', { name: /Inspect/i });
    fireEvent.click(inspectButtons[2]);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Approve Return/i })).toBeInTheDocument();
    });

    // Open APPROVE decision confirmation modal
    const approveBtn = screen.getByRole('button', { name: /Approve Return/i });
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(screen.getByText(/Confirm Founder Decision: APPROVE/i)).toBeInTheDocument();
    });

    // The confirmation shows what the approval authorises (FR-012).
    const dialog = screen.getByRole('dialog', { name: /Confirm Founder Decision: APPROVE/i });
    expect(within(dialog).getByText('Approval scope: this is all the approval authorises')).toBeInTheDocument();
    expect(within(dialog).getByText('prev_demo_003')).toBeInTheDocument();
    expect(within(dialog).getByText(MOCK_DEMO_003_SCOPE_FINGERPRINT)).toBeInTheDocument();
    expect(within(dialog).getByText('CREATE_RETURN')).toBeInTheDocument();
    expect(within(dialog).getByText('GENERATE_LABEL')).toBeInTheDocument();
    expect(within(dialog).getByText('$0.00 AUD')).toBeInTheDocument();

    // Fill mandatory rationale
    const rationaleInput = screen.getByPlaceholderText(/Record justification for statutory audit/i);
    fireEvent.change(rationaleInput, {
      target: { value: 'Approved under store 30-day change of mind policy.' },
    });

    const executeBtn = screen.getByRole('button', { name: /Record decision/i });
    fireEvent.click(executeBtn);

    // Modal should close upon successful admission
    await waitFor(() => {
      expect(screen.queryByText(/Confirm Founder Decision: APPROVE/i)).not.toBeInTheDocument();
    });

    // The reopened case lands on what the decision produced (#122 item 4): the
    // approval of the preview's exact scope, and no operation yet.
    expect(await screen.findByText('Approved scope')).toBeInTheDocument();
    expect(screen.getByText('Approved under store 30-day change of mind policy.')).toBeInTheDocument();
    expect(screen.getByText(MOCK_DEMO_003_SCOPE_FINGERPRINT)).toBeInTheDocument();
    expect(screen.getByText(/No operation has been recorded yet/)).toBeInTheDocument();
  });

  it('shows the outcome of the completed case_demo_005: approval, both operations, the label and the notice (#122 item 4)', async () => {
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });
    fireEvent.change(screen.getByPlaceholderText(/Filter by Case ID or Category/i), {
      target: { value: 'case_demo_005' },
    });
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Decision & Outcome/i }));

    const reason = await screen.findByText(
      'Approved the simulated return and label for the reported electrical fault.'
    );
    expect(within(reason.closest('div.p-4') as HTMLElement).getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('Create the simulated return')).toBeInTheDocument();
    expect(screen.getByText('Generate the return label (PDF)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download label \(PDF\)/ })).toBeEnabled();
    expect(screen.getByText('Return created')).toBeInTheDocument();
    expect(screen.getByText('SENT')).toBeInTheDocument();
    // The decision buttons follow the server's states: nothing is decidable on a completed case.
    for (const name of [/Approve Return/i, /^Request Revision$/i, /^Reject$/i, /^Manual Takeover$/i]) {
      expect(screen.getByRole('button', { name })).toBeDisabled();
    }
  });

  it('switches to Operations Analytics tab (OF-006) and displays throughput and latency metrics', async () => {
    render(<FounderConsole />);

    const analyticsTabBtn = screen.getByRole('button', { name: /Analytics Dashboard/i });
    fireEvent.click(analyticsTabBtn);

    await waitFor(() => {
      expect(screen.getByText('Total Case Volume')).toBeInTheDocument();
      expect(screen.getByText('128')).toBeInTheDocument();
      expect(screen.getByText('Unreviewed Cases')).toBeInTheDocument();
      expect(screen.getByText('58')).toBeInTheDocument();
      expect(screen.getByText('p50 Median Latency')).toBeInTheDocument();
      expect(screen.getByText('11.20s')).toBeInTheDocument();
      expect(screen.getByText('p95 Latency')).toBeInTheDocument();
      expect(screen.getByText('46.50s')).toBeInTheDocument();
    });

    // Status breakdown chart should be displayed
    expect(screen.getByText('Case Status Distribution')).toBeInTheDocument();
    expect(screen.getByText('Risk Review Outcome Distribution')).toBeInTheDocument();

    // The latency counts sit next to the tiles and add up to the case total
    // (70 + 2 + 56 = 128), as the contract requires.
    expect(screen.getByText('Measured:').parentElement).toHaveTextContent('Measured: 70');
    expect(screen.getByText('Failed:').parentElement).toHaveTextContent('Failed: 2');
    expect(screen.getByText('Unmeasured:').parentElement).toHaveTextContent('Unmeasured: 56');
    expect(screen.getByText('Filters applied:').parentElement).toHaveTextContent('Filters applied: none');

    // The fixed mock snapshot cannot be filtered, so the filter form is disabled.
    expect(screen.getByLabelText(/Current status/i)).toBeDisabled();
    expect(screen.getByRole('button', { name: /Apply Filters/i })).toBeDisabled();
  });

  it('loads the next queue page so the twenty-first case is reachable (Finding 6)', async () => {
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    // The first page holds 20 of the 25 synthetic cases.
    expect(screen.queryByText('case_demo_021')).not.toBeInTheDocument();

    const nextPageBtn = screen.getByRole('button', { name: /Load Next Page \(Next Cursor\)/i });
    fireEvent.click(nextPageBtn);

    await waitFor(() => {
      expect(screen.getByText('case_demo_021')).toBeInTheDocument();
    });
    // The cursor is exhausted once the final page is loaded.
    expect(screen.queryByRole('button', { name: /Load Next Page \(Next Cursor\)/i })).not.toBeInTheDocument();
  });

  it('makes all four Founder decision confirmations reachable (Finding 3)', async () => {
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    // Narrow the queue to the awaiting-approval case so the decision controls are live.
    fireEvent.change(screen.getByPlaceholderText(/Filter by Case ID or Category/i), {
      target: { value: 'case_demo_003' },
    });
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    const decisions: Array<[RegExp, string]> = [
      [/Approve Return/i, 'APPROVE'],
      [/^Request Revision$/i, 'REQUEST_REVISION'],
      [/^Reject$/i, 'REJECT'],
      [/^Manual Takeover$/i, 'MANUAL_HANDLING'],
    ];

    for (const [buttonName, decision] of decisions) {
      const control = await screen.findByRole('button', { name: buttonName });
      expect(control).toBeEnabled();
      fireEvent.click(control);

      // The confirmation overlay and its rationale/confirm controls must be reachable.
      expect(await screen.findByText(`Confirm Founder Decision: ${decision}`)).toBeInTheDocument();
      const confirm = screen.getByRole('button', { name: /Record decision/i });
      const rationale = screen.getByPlaceholderText(/Record justification for statutory audit/i);
      expect(rationale).toBeInTheDocument();

      // Rationale is mandatory: an empty justification cannot confirm a decision.
      expect(confirm).toBeDisabled();
      fireEvent.change(rationale, { target: { value: 'Scripted governance rationale.' } });
      expect(confirm).toBeEnabled();

      fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));
      await waitFor(() => {
        expect(screen.queryByText(`Confirm Founder Decision: ${decision}`)).not.toBeInTheDocument();
      });
    }
  });

  it('refuses to confirm a decision without a governance rationale', async () => {
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_003')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Filter by Case ID or Category/i), {
      target: { value: 'case_demo_003' },
    });
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Approve Return/i }));

    const confirm = await screen.findByRole('button', { name: /Record decision/i });
    expect(confirm).toBeDisabled();

    // Even a forced click must leave the confirmation open and record nothing.
    fireEvent.click(confirm);
    expect(screen.getByText(/Confirm Founder Decision: APPROVE/i)).toBeInTheDocument();

    // A blank or whitespace-only justification is not a rationale.
    fireEvent.change(screen.getByPlaceholderText(/Record justification for statutory audit/i), {
      target: { value: '   ' },
    });
    expect(confirm).toBeDisabled();
  });

  it('inspects the escalated case and blocks direct approval with the documented outcomes (Finding 11)', async () => {
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    // Narrow the queue so the escalated summary row is the only inspectable case.
    fireEvent.change(screen.getByPlaceholderText(/Filter by Case ID or Category/i), {
      target: { value: 'case_demo_004' },
    });
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    // The advertised escalated case must resolve to a real detail view, not a 404.
    // The text names the decisions the server accepts for an escalated case.
    expect(
      await screen.findByText(/Escalated Case: Direct approval blocked\. Manual takeover or revision required\./i)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve Return/i })).toBeDisabled();

    // Manual handling remains available. Rejection is blocked for an escalated
    // case: the server accepts Reject only for a case awaiting approval.
    expect(screen.getByRole('button', { name: /Manual Takeover/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /^Reject$/i })).toBeDisabled();
  });

  it('shows the completed lifecycle audit history for case_demo_005 (Finding 11)', async () => {
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Filter by Case ID or Category/i), {
      target: { value: 'case_demo_005' },
    });
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    fireEvent.click(
      await screen.findByRole('button', { name: /Tamper-Evident Audit Chain/i })
    );

    expect(
      await screen.findByText(/Recorded Audit Events:/i)
    ).toBeInTheDocument();
    // The banner must not claim verification it does not perform.
    expect(screen.getByText(/This view does not recompute or verify the chain\./i)).toBeInTheDocument();
    // The whole closure of the demo case must be present, not just a summary row.
    expect(screen.getByText(/#5 CASE_COMPLETED/i)).toBeInTheDocument();
    expect(screen.getByText(/#3 FOUNDER_DECISION_ACCEPTED/i)).toBeInTheDocument();
    // The approval covered a simulated return and label only; no money moved (#122 item 3).
    expect(screen.getByText(/#4 SIMULATED_RETURN_AND_LABEL_CREATED/i)).toBeInTheDocument();
    expect(screen.queryByText(/REFUND_DISPATCHED/i)).not.toBeInTheDocument();
  });

  it('opens a generated queue row instead of failing with a not-found alert (#122 item 1)', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    render(<FounderConsole />);

    await waitFor(() => {
      expect(screen.getByText('case_demo_006')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Filter by Case ID or Category/i), {
      target: { value: 'case_demo_006' },
    });
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    // The row opens: it is still under investigation, so there is no proposal yet.
    expect(await screen.findByText('No active proposal generated for this case yet.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve Return/i })).toBeDisabled();
    expect(alertSpy).not.toHaveBeenCalled();
  });
});
