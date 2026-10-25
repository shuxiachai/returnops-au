import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CustomerPortal } from './CustomerPortal';
import type { CaseStatus, CustomerCaseView } from '../types/domain';

// #111 item 2 (auto-refresh) and #122 item 2 (409 reload) on the customer side,
// in Live API mode. FR-001/002/005, NFR-006; UC-01E.
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    isMockMode: vi.fn(() => false),
    getCustomerCase: vi.fn(),
    submitClarification: vi.fn(),
  };
});

import { ApiError, getCustomerCase, submitClarification } from '../api/client';

const CASE_ID = 'case_live_001';

function view(status: CaseStatus, version: number, withQuestions = false): CustomerCaseView {
  return {
    case_id: CASE_ID,
    case_version: version,
    input_version: 1,
    status,
    created_at: '2026-10-25T00:00:00Z',
    updated_at: '2026-10-25T00:00:00Z',
    statements: [
      {
        statement_id: 'stmt_live',
        kind: 'ORIGINAL',
        raw_text: 'The kettle stopped working after two days.',
        submitted_at: '2026-10-25T00:00:00Z',
      },
    ],
    evidence: [],
    ...(withQuestions
      ? {
          clarification: {
            question_set_id: 'qset_live',
            input_version: 1,
            questions: [{ question_id: 'q_order', text: 'What is your order number?' }],
          },
        }
      : {}),
  };
}

const setVisibility = (state: DocumentVisibilityState) => {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
};

async function lookUpCase() {
  render(<CustomerPortal />);
  fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
  fireEvent.change(screen.getByPlaceholderText('Enter your case ID...'), { target: { value: CASE_ID } });
  fireEvent.click(screen.getByRole('button', { name: /Lookup/i }));
}

describe('CustomerPortal auto-refresh and stale answers (Live API mode)', () => {
  beforeEach(() => {
    localStorage.clear();
    // Only the interval is faked, so Testing Library's own timers keep running.
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    setVisibility('visible');
  });

  afterEach(() => {
    vi.useRealTimers();
    setVisibility('visible');
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('re-reads the case every 5 s while the shop works on it, not while the tab is hidden, and stops when final', async () => {
    vi.mocked(getCustomerCase)
      .mockResolvedValueOnce(view('UNDER_INVESTIGATION', 3))
      .mockResolvedValueOnce(view('AWAITING_APPROVAL', 4))
      .mockResolvedValue({ ...view('COMPLETED', 6), outcome_message: 'Your return label is ready.' });

    await lookUpCase();
    expect(await screen.findByText('Being reviewed')).toBeInTheDocument();
    expect(screen.getByText('This page updates by itself')).toBeInTheDocument();

    setVisibility('hidden');
    act(() => {
      vi.advanceTimersByTime(15000);
    });
    expect(getCustomerCase).toHaveBeenCalledTimes(1);
    setVisibility('visible');

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(await screen.findByText("Waiting for the shop's decision")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(await screen.findByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('Your return label is ready.')).toBeInTheDocument();
    expect(getCustomerCase).toHaveBeenCalledTimes(3);

    // COMPLETED is final: nothing more is read.
    expect(screen.queryByText('This page updates by itself')).not.toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(30000);
    });
    expect(getCustomerCase).toHaveBeenCalledTimes(3);
  });

  it('does not poll while the shop waits for answers, and a refresh on focus keeps the typed answer', async () => {
    vi.mocked(getCustomerCase).mockResolvedValue(view('AWAITING_INFORMATION', 2, true));

    await lookUpCase();
    expect(await screen.findByText('A few questions for you')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Your answer...'), { target: { value: 'SYN-1001' } });

    act(() => {
      vi.advanceTimersByTime(30000);
    });
    expect(getCustomerCase).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('This page updates by itself')).not.toBeInTheDocument();

    // Coming back to the window reads the case once; the same question set keeps the draft.
    fireEvent.focus(window);
    await waitFor(() => expect(getCustomerCase).toHaveBeenCalledTimes(2));
    expect(screen.getByPlaceholderText('Your answer...')).toHaveValue('SYN-1001');
  });

  it('reloads the case after a 409 STALE_CASE_VERSION, keeps the typed answer and resends only on request (#122 item 2)', async () => {
    vi.mocked(getCustomerCase)
      .mockResolvedValueOnce(view('AWAITING_INFORMATION', 2, true))
      .mockResolvedValue(view('AWAITING_INFORMATION', 3, true));
    vi.mocked(submitClarification)
      .mockRejectedValueOnce(new ApiError(409, 'The case version has changed.', 'STALE_CASE_VERSION'))
      .mockResolvedValue(view('UNDER_INVESTIGATION', 4));

    await lookUpCase();
    fireEvent.change(await screen.findByPlaceholderText('Your answer...'), { target: { value: 'SYN-1001' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit Answers/i }));

    expect(
      await screen.findByText(
        'Your case changed while you were answering, so the page was reloaded. Check the questions and send your answers again.'
      )
    ).toBeInTheDocument();
    expect(getCustomerCase).toHaveBeenCalledTimes(2);
    expect(submitClarification).toHaveBeenCalledTimes(1);
    expect(screen.getByPlaceholderText('Your answer...')).toHaveValue('SYN-1001');
    expect(screen.queryByText(/STALE_CASE_VERSION/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Submit Answers/i }));
    expect(await screen.findByText(/Your answers were received/i)).toBeInTheDocument();
    const [first, second] = vi.mocked(submitClarification).mock.calls;
    expect(first[1]).toMatchObject({ expected_case_version: 2 });
    expect(second[1]).toMatchObject({
      expected_case_version: 3,
      question_set_id: 'qset_live',
      answers: [{ question_id: 'q_order', text: 'SYN-1001' }],
    });
    expect(second[2]).not.toBe(first[2]);
  });
});
