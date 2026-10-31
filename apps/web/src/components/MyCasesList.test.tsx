import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MyCasesList } from './MyCasesList';
import type { CustomerCaseSummary, CustomerCaseView } from '../types/domain';

// "My Requests" (31 October 2026): the signed-in customer's own cases, GET /v1/cases
// outside contract v1. FR-001; NFR-003, NFR-006; UC-01E.
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return { ...actual, listMyCases: vi.fn() };
});

import { ApiError, listMyCases } from '../api/client';

const listed = vi.mocked(listMyCases);

function summary(caseId: string, extra: Partial<CustomerCaseSummary> = {}): CustomerCaseSummary {
  return {
    case_id: caseId,
    status: 'SUBMITTED',
    created_at: '2026-10-31T01:00:00Z',
    updated_at: '2026-10-31T01:00:00Z',
    awaiting_answer: false,
    ...extra,
  };
}

const NEWER = summary('case_newer', {
  status: 'AWAITING_INFORMATION',
  awaiting_answer: true,
  excerpt: 'The kettle stopped heating after two days.',
  requested_outcome: 'REFUND',
  created_at: '2026-10-31T02:00:00Z',
});
const OLDER = summary('case_older', { excerpt: 'The parcel arrived crushed.', requested_outcome: 'UNSPECIFIED' });

describe('My Requests on Track & Clarify', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('lists the requests in the order the server sent and opens the one clicked', async () => {
    listed.mockResolvedValue({ items: [NEWER, OLDER], limit: 20 });
    const onOpen = vi.fn();
    render(<MyCasesList openCaseId={null} openCase={null} onOpen={onOpen} />);

    expect(await screen.findByText('The kettle stopped heating after two days.')).toBeInTheDocument();
    expect(screen.getByText('My Requests (2)')).toBeInTheDocument();
    const rows = screen.getAllByRole('listitem');
    expect(rows[0]).toHaveTextContent('The kettle stopped heating after two days.');
    expect(rows[1]).toHaveTextContent('The parcel arrived crushed.');
    // Plain words, not internal status names; a case waiting for the customer says what to
    // do in place of its status; a request without a chosen outcome names none.
    expect(rows[0]).toHaveTextContent('Your answer is needed');
    expect(rows[0]).not.toHaveTextContent('We need a bit more information');
    expect(rows[0]).toHaveTextContent('Asked for: Refund');
    expect(rows[1]).toHaveTextContent('Received');
    expect(rows[1]).not.toHaveTextContent('Asked for');
    expect(rows[1]).not.toHaveTextContent('Your answer is needed');

    fireEvent.click(screen.getByText('The parcel arrived crushed.'));
    expect(onOpen).toHaveBeenCalledWith('case_older');
  });

  it('stays hidden where the server offers no list (no password sign-in)', async () => {
    for (const status of [404, 405]) {
      listed.mockRejectedValueOnce(new ApiError(status, 'Not here', `HTTP_${status}`));
      const { container, unmount } = render(<MyCasesList openCaseId={null} openCase={null} onOpen={vi.fn()} />);
      await waitFor(() => expect(container).toBeEmptyDOMElement());
      unmount();
    }
  });

  it('says when there is nothing yet, and offers a reload after a failure', async () => {
    listed.mockRejectedValueOnce(new ApiError(503, 'Busy', 'INTERNAL_ERROR'));
    listed.mockResolvedValueOnce({ items: [], limit: 20 });
    render(<MyCasesList openCaseId={null} openCase={null} onOpen={vi.fn()} />);

    expect(await screen.findByText(/could not be loaded just now/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Reload list' }));
    expect(await screen.findByText(/You have not lodged any requests yet/i)).toBeInTheDocument();
    expect(listed).toHaveBeenCalledTimes(2);
  });

  it('folds away while a case is open, unfolds on request, and follows the open case', async () => {
    listed.mockResolvedValue({ items: [NEWER, OLDER], limit: 20 });
    const open: CustomerCaseView = {
      case_id: 'case_newer',
      case_version: 3,
      input_version: 2,
      status: 'UNDER_INVESTIGATION',
      created_at: NEWER.created_at,
      updated_at: '2026-10-31T03:00:00Z',
      statements: [],
      evidence: [],
    };
    render(<MyCasesList openCaseId="case_newer" openCase={open} onOpen={vi.fn()} />);

    expect(await screen.findByText('My Requests (2)')).toBeInTheDocument();
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Show list/ }));

    const rows = screen.getAllByRole('listitem');
    // The page has read the open case again since the list was read: its row follows it.
    expect(rows[0]).toHaveTextContent('Being reviewed');
    expect(rows[0]).not.toHaveTextContent('Your answer is needed');
    expect(screen.getByRole('button', { name: /The kettle stopped heating/ })).toHaveAttribute('aria-current', 'true');
    fireEvent.click(screen.getByRole('button', { name: /Hide list/ }));
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
  });

  it('reports which requests match the search, and none while no list is shown', async () => {
    listed.mockResolvedValue({ items: [NEWER, OLDER], limit: 20 });
    const onMatches = vi.fn();
    const { rerender } = render(
      <MyCasesList openCaseId={null} openCase={null} onOpen={vi.fn()} filter="parcel" onMatches={onMatches} />
    );
    expect(onMatches).toHaveBeenCalledWith(null);
    await waitFor(() => expect(onMatches).toHaveBeenLastCalledWith(['case_older']));
    // Status words and what was asked for match too.
    rerender(<MyCasesList openCaseId={null} openCase={null} onOpen={vi.fn()} filter="your answer" onMatches={onMatches} />);
    await waitFor(() => expect(onMatches).toHaveBeenLastCalledWith(['case_newer']));
    rerender(<MyCasesList openCaseId={null} openCase={null} onOpen={vi.fn()} filter="nothing like it" onMatches={onMatches} />);
    await waitFor(() => expect(onMatches).toHaveBeenLastCalledWith([]));
    expect(screen.getByText(/None of your requests matches this/)).toBeInTheDocument();
  });

  it('says when only the most recent requests are shown', async () => {
    const many = Array.from({ length: 20 }, (_, n) => summary(`case_${n}`, { excerpt: `Request ${n}` }));
    listed.mockResolvedValue({ items: many, limit: 20 });
    render(<MyCasesList openCaseId={null} openCase={null} onOpen={vi.fn()} />);

    expect(await screen.findByText(/Showing your 20 most recent requests/)).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(20);
  });
});
