import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { FounderConsole } from './FounderConsole';
import { describeApproval } from '../components/ApprovalScopeSummary';
import { MOCK_FOUNDER_CASE_VIEWS } from '../api/mockData';
import { setMockMode } from '../api/client';

const WAITING = ['AWAITING_APPROVAL', 'ESCALATED'];

function queueRows() {
  return screen.getAllByRole('row').slice(1);
}

function rowStatus(row: HTMLElement) {
  return within(row).getAllByTitle(/^[A-Z_]+$/)[0].getAttribute('title');
}

// 31 October 2026, the lead's product review: the Founder sees what waits for them,
// reads statuses in words and understands an approval before the exact scope.
describe('Founder console for daily use', () => {
  beforeEach(() => {
    localStorage.clear();
    setMockMode(true);
  });

  afterEach(() => localStorage.clear());

  it('lists the cases waiting for the Founder first and marks them', async () => {
    render(<FounderConsole />);
    await screen.findByText('case_demo_001');

    const statuses = queueRows().map(rowStatus);
    const firstOther = statuses.findIndex((status) => !WAITING.includes(status as string));
    expect(firstOther).toBeGreaterThan(0);
    expect(statuses.slice(firstOther).some((status) => WAITING.includes(status as string))).toBe(false);
    expect(within(queueRows()[0]).getByText('Needs you')).toBeInTheDocument();
    expect(within(queueRows()[firstOther]).queryByText('Needs you')).not.toBeInTheDocument();
  });

  it('filters the queue from the tiles', async () => {
    render(<FounderConsole />);
    await screen.findByText('case_demo_001');
    const all = queueRows().length;

    const approval = screen.getByRole('button', { name: /Needs your approval/i });
    fireEvent.click(approval);
    expect(approval).toHaveAttribute('aria-pressed', 'true');
    expect(queueRows().length).toBeGreaterThan(0);
    expect(queueRows().map(rowStatus).every((status) => status === 'AWAITING_APPROVAL')).toBe(true);

    fireEvent.click(screen.getByRole('button', { name: /All cases/i }));
    expect(queueRows()).toHaveLength(all);
  });

  it("opens a case on what it waits for and the customer's own words", async () => {
    render(<FounderConsole />);
    await screen.findByText('case_demo_003');
    fireEvent.click(
      within(screen.getByText('case_demo_003').closest('tr') as HTMLElement).getByRole('button', { name: /Inspect/i })
    );

    expect(await screen.findByText('Your decision is needed.')).toBeInTheDocument();
    expect(screen.getByText('Customer wrote:')).toBeInTheDocument();
    const window = screen.getByRole('dialog', { name: 'Case case_demo_003' });
    expect(within(window).getByTitle('AWAITING_APPROVAL')).toHaveTextContent('Awaiting Approval');
  });

  it('describes an approval in words, with the exact scope still one click away', async () => {
    const preview = Object.values(MOCK_FOUNDER_CASE_VIEWS)
      .map((view) => view.action_preview)
      .find((value) => value !== undefined);
    expect(preview).toBeDefined();
    expect(describeApproval(preview!)).toMatch(
      /^This approval allows the shop to register one simulated return for order \S+ \(\d+ items?\) and create its return label\. No payment is authorised\. It can be used until .+; nothing else is authorised\.$/
    );

    render(<FounderConsole />);
    await screen.findByText('case_demo_003');
    fireEvent.click(
      within(screen.getByText('case_demo_003').closest('tr') as HTMLElement).getByRole('button', { name: /Inspect/i })
    );
    fireEvent.click(await screen.findByRole('button', { name: /Approve Return/i }));
    const dialog = await screen.findByRole('dialog', { name: /Confirm: Approve return/i });
    expect(within(dialog).getByText(/^This approval allows the shop to/)).toBeInTheDocument();
    expect(within(dialog).getByText('Exact scope (technical details)')).toBeInTheDocument();
    expect(within(dialog).getByText('Scope fingerprint')).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/Reason/)).toHaveAttribute('placeholder', 'Why are you making this decision?');
  });
});
