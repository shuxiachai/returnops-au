import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { FounderConsole } from './FounderConsole';
import { setMockMode } from '../api/client';

describe('FounderConsole (UC-03, UC-04, UC-05 & OF-006)', () => {
  beforeEach(() => {
    localStorage.clear();
    setMockMode(true);
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders Founder Console heading, quick metric cards, and case queue table', async () => {
    render(<FounderConsole />);

    expect(screen.getByText('Founder Console & Governance')).toBeInTheDocument();
    expect(screen.getByText(/Authoritative return inspection, governed execution/i)).toBeInTheDocument();

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
        screen.getByText(/Cryptographic Audit Chain Integrity Validated/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/CASE_CREATED/i)).toBeInTheDocument();
    });
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
      expect(screen.getByRole('button', { name: /Approve Return \(UC-04\)/i })).toBeInTheDocument();
    });

    // Open APPROVE decision confirmation modal
    const approveBtn = screen.getByRole('button', { name: /Approve Return \(UC-04\)/i });
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(screen.getByText(/Confirm Founder Decision: APPROVE/i)).toBeInTheDocument();
    });

    // Fill mandatory rationale
    const rationaleInput = screen.getByPlaceholderText(/Record justification for statutory audit/i);
    fireEvent.change(rationaleInput, {
      target: { value: 'Approved under store 30-day change of mind policy.' },
    });

    const executeBtn = screen.getByRole('button', { name: /Record & Execute/i });
    fireEvent.click(executeBtn);

    // Modal should close upon successful admission
    await waitFor(() => {
      expect(screen.queryByText(/Confirm Founder Decision: APPROVE/i)).not.toBeInTheDocument();
    });
  });

  it('switches to Operations Analytics tab (OF-006) and displays throughput and latency metrics', async () => {
    render(<FounderConsole />);

    const analyticsTabBtn = screen.getByRole('button', { name: /Analytics Dashboard \(OF-006\)/i });
    fireEvent.click(analyticsTabBtn);

    await waitFor(() => {
      expect(screen.getByText('Total Case Volume')).toBeInTheDocument();
      expect(screen.getByText('128')).toBeInTheDocument();
      expect(screen.getByText('Unreviewed Cases')).toBeInTheDocument();
      expect(screen.getByText('58')).toBeInTheDocument();
      expect(screen.getByText('p50 Median Latency')).toBeInTheDocument();
      expect(screen.getByText('11.20s')).toBeInTheDocument();
      expect(screen.getByText('p95 Latency SLA')).toBeInTheDocument();
      expect(screen.getByText('46.50s')).toBeInTheDocument();
    });

    // Status breakdown chart should be displayed
    expect(screen.getByText('Case Status Distribution')).toBeInTheDocument();
    expect(screen.getByText('Risk Review Outcome Distribution')).toBeInTheDocument();
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
      [/Approve Return \(UC-04\)/i, 'APPROVE'],
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
      expect(screen.getByRole('button', { name: /Record & Execute/i })).toBeEnabled();
      expect(
        screen.getByPlaceholderText(/Record justification for statutory audit/i)
      ).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));
      await waitFor(() => {
        expect(screen.queryByText(`Confirm Founder Decision: ${decision}`)).not.toBeInTheDocument();
      });
    }
  });
});
