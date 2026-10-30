import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

// The Founder queue in Live API mode: the table on a narrow window, paging after a
// reload, the wording of a failed read and the Gate 1 category placeholder.
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    isMockMode: vi.fn(() => false),
    listFounderCases: vi.fn(),
    getFounderCase: vi.fn(),
    listFounderCaseAuditPage: vi.fn(),
  };
});

import { ApiError, NETWORK_ERROR, listFounderCases } from '../api/client';
import { FounderConsole } from './FounderConsole';
import type { CaseSummary } from '../types/domain';

// Server-shaped rows: a case ID is "case_" plus 32 hexadecimal characters, and the
// summary carries the UNCLEAR placeholder (founder_queries.summary).
const ROWS: CaseSummary[] = Array.from({ length: 45 }, (_, i) => ({
  case_id: `case_${(i + 1).toString(16).padStart(32, '0')}`,
  case_version: 3,
  input_version: 2,
  status: 'RISK_REVIEW',
  created_at: '2026-10-30T00:00:00Z',
  updated_at: '2026-10-30T00:00:00Z',
  issue_category: 'UNCLEAR',
}));

// The server binds a cursor to the limit it was issued with (founder_queries.resume):
// any other limit is refused with 409 INVALID_STATE.
function serveQueue() {
  vi.mocked(listFounderCases).mockImplementation(async (cursor?: string, limit = 20) => {
    let start = 0;
    if (cursor) {
      const match = /^c(\d+)x(\d+)$/.exec(cursor);
      if (!match || Number(match[2]) !== limit) {
        throw new ApiError(409, 'The request is not available in the current state.', 'INVALID_STATE');
      }
      start = Number(match[1]);
    }
    const items = ROWS.slice(start, start + limit);
    return { items, next_cursor: start + limit < ROWS.length ? `c${start + limit}x${limit}` : undefined };
  });
}

describe('FounderConsole queue (Live API mode)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('keeps Inspect reachable: the table scrolls inside the card, Actions is pinned and the long ID is shortened', async () => {
    serveQueue();
    render(<FounderConsole />);

    const id = await screen.findByText(ROWS[0].case_id);
    // The full ID stays in the text and on hover; only the cell is shortened.
    expect(id).toHaveAttribute('title', ROWS[0].case_id);
    expect(id).toHaveClass('truncate');
    expect(screen.getByRole('table').parentElement).toHaveClass('overflow-x-auto');
    expect(screen.getByRole('columnheader', { name: 'Actions' })).toHaveClass('sticky', 'right-0');
    const inspect = screen.getAllByRole('button', { name: /Inspect/i })[0];
    expect(inspect.closest('td')).toHaveClass('sticky', 'right-0');
  });

  it('reads the next page with the limit that produced the cursor after a reload on return', async () => {
    serveQueue();
    render(<FounderConsole />);
    await screen.findByText(ROWS[0].case_id);

    fireEvent.click(screen.getByRole('button', { name: /Load Next Page/i }));
    await screen.findByText(ROWS[39].case_id);

    // Coming back to the window reloads the 40 loaded rows in one page of 40.
    await act(async () => {
      window.dispatchEvent(new Event('focus'));
    });
    await waitFor(() => expect(listFounderCases).toHaveBeenCalledWith(undefined, 40));
    await waitFor(() => expect(screen.getByRole('button', { name: /Load Next Page/i })).toBeEnabled());

    fireEvent.click(screen.getByRole('button', { name: /Load Next Page/i }));
    expect(await screen.findByText(ROWS[44].case_id)).toBeInTheDocument();
    expect(vi.mocked(listFounderCases).mock.calls).toEqual([
      [undefined, 20],
      ['c20x20', 20],
      [undefined, 40],
      ['c40x40', 40],
    ]);
    expect(screen.queryByText(/INVALID_STATE/)).not.toBeInTheDocument();
  });

  it('names a failed connection and never shows "[undefined]"', async () => {
    vi.mocked(listFounderCases).mockRejectedValueOnce(new ApiError(0, 'Failed to fetch', NETWORK_ERROR));
    const view = render(<FounderConsole />);
    expect(await screen.findByText('[NETWORK_ERROR] Failed to fetch')).toBeInTheDocument();
    view.unmount();

    // An error without a code is shown as its message alone.
    vi.mocked(listFounderCases).mockRejectedValueOnce(new ApiError(0, 'Failed to fetch'));
    render(<FounderConsole />);
    expect(await screen.findByText('Failed to fetch')).toBeInTheDocument();
    expect(screen.queryByText(/undefined/)).not.toBeInTheDocument();
  });

  it('shows the Gate 1 placeholder category as not yet classified', async () => {
    serveQueue();
    render(<FounderConsole />);
    await screen.findByText(ROWS[0].case_id);

    expect(screen.getAllByText('Not yet classified')).toHaveLength(20);
    expect(screen.queryByText('Unclear Statement')).not.toBeInTheDocument();
  });
});
