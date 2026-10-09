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
      expect(screen.getByText('ORD-2026-9042')).toBeInTheDocument();
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
});
