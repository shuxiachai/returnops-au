import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { App } from './App';
import { SignInPage } from './components/SignInPage';
import { FounderConsole } from './pages/FounderConsole';
import {
  clearSessionRejection,
  getFounderCase,
  getSession,
  listFounderCases,
  recordFounderDecision,
  setMockMode,
  setStoredToken,
} from './api/client';
import { MOCK_CUSTOMER_CASES, MOCK_FOUNDER_CASE_VIEWS, MOCK_FOUNDER_SUMMARIES } from './api/mockData';
import { usePolling, useRefreshOnReturn } from './utils/autoRefresh';

// Runtime review of 31 October 2026: each test pins one fixed defect. NFR-004, NFR-006.
function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

const FOUNDER = { principal_id: 'founder_live', role: 'FOUNDER', enabled: true, session_id: 's_f' };

function storageChange(key: string | null, newValue: string | null) {
  act(() => {
    window.dispatchEvent(new StorageEvent('storage', { key, newValue, storageArea: localStorage }));
  });
}

describe('runtime review fixes (31 October 2026)', () => {
  beforeEach(() => {
    localStorage.clear();
    clearSessionRejection();
  });

  afterEach(() => {
    localStorage.clear();
    clearSessionRejection();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('a tab in the sample data follows another tab that left it, instead of reaching the server', async () => {
    setMockMode(true);
    render(<App />);
    expect(screen.getByText(/You are exploring built-in sample data/)).toBeInTheDocument();

    // Another tab changes an unrelated key: nothing happens here.
    localStorage.setItem('returnops_active_role', 'FOUNDER');
    storageChange('returnops_active_role', 'FOUNDER');
    expect(screen.getByText(/You are exploring built-in sample data/)).toBeInTheDocument();

    // Another tab leaves the sample data: this tab no longer shows sample pages.
    localStorage.setItem('returnops_mock_mode', 'false');
    storageChange('returnops_mock_mode', 'false');
    expect(await screen.findByText(/in another tab\. Sign in again here\./)).toBeInTheDocument();
    expect(screen.queryByText(/You are exploring built-in sample data/)).not.toBeInTheDocument();
  });

  it('a signed-in tab follows another tab that signed out', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/v1/session')) return jsonResponse(200, FOUNDER);
        if (url.includes('/v1/founder/cases')) return jsonResponse(200, { items: [] });
        return jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'Not found.' } });
      })
    );
    localStorage.setItem('returnops_mock_mode', 'false');
    setStoredToken('founder.live.key');
    render(<App />);
    expect(await screen.findByText('Founder Console')).toBeInTheDocument();

    localStorage.removeItem('returnops_auth_token');
    storageChange('returnops_auth_token', null);
    expect(await screen.findByText(/in another tab\. Sign in again here\./)).toBeInTheDocument();
  });

  it('sample data cannot be chosen while a sign-in is being checked', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => undefined)));
    const onExploreSample = vi.fn();
    render(<SignInPage onSignedIn={vi.fn()} onExploreSample={onExploreSample} />);
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'founder_live' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'founder-pass-1234' } });
    const explore = screen.getByRole('button', { name: 'Explore with sample data' });
    expect(explore).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(explore).toBeDisabled());
    fireEvent.click(explore);
    expect(onExploreSample).not.toHaveBeenCalled();
  });

  it('polling and focus refreshes stop while the session is rejected', async () => {
    setMockMode(false);
    setStoredToken('expired.key');
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(401, { error: { code: 'UNAUTHENTICATED', message: 'No.' } })));
    await expect(getSession()).rejects.toMatchObject({ status: 401 });

    vi.useFakeTimers();
    const tick = vi.fn();
    const back = vi.fn();
    renderHook(() => {
      usePolling(tick, true, 100);
      useRefreshOnReturn(back);
    });
    act(() => {
      vi.advanceTimersByTime(350);
      window.dispatchEvent(new Event('focus'));
    });
    expect(tick).not.toHaveBeenCalled();
    expect(back).not.toHaveBeenCalled();

    act(() => clearSessionRejection());
    act(() => {
      vi.advanceTimersByTime(250);
      window.dispatchEvent(new Event('focus'));
    });
    expect(tick).toHaveBeenCalled();
    expect(back).toHaveBeenCalledTimes(1);
  });

  it('in the sample data a decision also moves the queue row and the customer copy', async () => {
    setMockMode(true);
    const view = MOCK_FOUNDER_CASE_VIEWS.case_demo_003;
    const row = MOCK_FOUNDER_SUMMARIES.find((summary) => summary.case_id === 'case_demo_003')!;
    const saved = { view: structuredClone(view), row: { ...row }, customer: MOCK_CUSTOMER_CASES.case_demo_003 && { ...MOCK_CUSTOMER_CASES.case_demo_003 } };
    try {
      expect(row.status).toBe('AWAITING_APPROVAL');
      await recordFounderDecision('case_demo_003', {
        expected_case_version: view.case_version,
        decision: 'REJECT',
        reason: 'The photos do not show the damage described.',
        proposal_id: view.current_proposal?.proposal_id,
        proposal_version: view.current_proposal?.proposal_version,
      });
      const queue = await listFounderCases();
      expect(queue.items.find((item) => item.case_id === 'case_demo_003')?.status).toBe('REJECTED');
      expect((await getFounderCase('case_demo_003')).status).toBe('REJECTED');
      if (MOCK_CUSTOMER_CASES.case_demo_003) expect(MOCK_CUSTOMER_CASES.case_demo_003.status).toBe('REJECTED');
    } finally {
      Object.assign(view, saved.view);
      Object.assign(row, saved.row);
      if (saved.customer) Object.assign(MOCK_CUSTOMER_CASES.case_demo_003, saved.customer);
    }
  });

  it('an AI group filter never outlives the triage that made it', async () => {
    setMockMode(true);
    render(<FounderConsole />);
    await screen.findByText('case_demo_001');
    const rows = () => screen.getAllByRole('row').slice(1);
    const all = rows().length;

    fireEvent.click(screen.getByRole('button', { name: 'Triage the queue' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Sample group (2)' }));
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(screen.getByText(/Showing only the AI group Sample group/)).toBeInTheDocument();

    // Leaving the queue tab ends the triage and its filter.
    fireEvent.click(screen.getByRole('button', { name: /Analytics Dashboard/ }));
    fireEvent.click(screen.getByRole('button', { name: /Case Queue/ }));
    await waitFor(() => expect(rows()).toHaveLength(all));
    expect(screen.queryByText(/Showing only the AI group/)).not.toBeInTheDocument();

    // The notice's own button clears it too.
    fireEvent.click(screen.getByRole('button', { name: 'Triage the queue' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Sample group (2)' }));
    await waitFor(() => expect(rows()).toHaveLength(2));
    fireEvent.click(screen.getByRole('button', { name: 'Show all cases' }));
    await waitFor(() => expect(rows()).toHaveLength(all));
  });
});
