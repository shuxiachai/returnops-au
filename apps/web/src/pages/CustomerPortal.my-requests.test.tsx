import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CustomerPortal } from './CustomerPortal';
import type { CustomerCaseView } from '../types/domain';

// "My Requests" in the portal (31 October 2026), Live API mode: a row opens the case
// exactly as Lookup does. FR-001; NFR-003, NFR-006; UC-01E.
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    isMockMode: vi.fn(() => false),
    getCustomerCase: vi.fn(),
    listMyCases: vi.fn(),
  };
});

import { ApiError, getCustomerCase, listMyCases } from '../api/client';

const VIEW: CustomerCaseView = {
  case_id: 'case_live_mine',
  case_version: 1,
  input_version: 1,
  status: 'SUBMITTED',
  created_at: '2026-10-31T01:00:00Z',
  updated_at: '2026-10-31T01:00:00Z',
  statements: [
    {
      statement_id: 'stmt_live_mine',
      kind: 'ORIGINAL',
      raw_text: 'The blender stopped after one use.',
      submitted_at: '2026-10-31T01:00:00Z',
    },
  ],
  evidence: [],
};

describe('CustomerPortal: My Requests', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('opens a listed request on Track & Clarify without typing its case ID', async () => {
    vi.mocked(listMyCases).mockResolvedValue({
      items: [
        {
          case_id: 'case_live_mine',
          status: 'SUBMITTED',
          created_at: VIEW.created_at,
          updated_at: VIEW.updated_at,
          awaiting_answer: false,
          excerpt: 'The blender stopped after one use.',
        },
      ],
      limit: 20,
    });
    vi.mocked(getCustomerCase).mockResolvedValue(VIEW);
    render(<CustomerPortal />);

    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    fireEvent.click(await screen.findByRole('button', { name: /The blender stopped after one use/ }));

    await waitFor(() => expect(getCustomerCase).toHaveBeenCalledWith('case_live_mine'));
    expect(await screen.findByText('case_live_mine')).toBeInTheDocument();
    expect(screen.getByLabelText(/case ID/i)).toHaveValue('case_live_mine');
    // The list folds away so the case is what the customer reads.
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Show list/ })).toBeInTheDocument();
  });

  it('searches the requests from the box above them and opens the one match with Enter (31 October 2026)', async () => {
    const summary = (caseId: string, excerpt: string) => ({
      case_id: caseId,
      status: 'SUBMITTED' as const,
      created_at: VIEW.created_at,
      updated_at: VIEW.updated_at,
      awaiting_answer: false,
      excerpt,
    });
    vi.mocked(listMyCases).mockResolvedValue({
      items: [summary('case_live_mine', 'The blender stopped after one use.'), summary('case_live_kettle', 'The kettle leaks.')],
      limit: 20,
    });
    vi.mocked(getCustomerCase).mockResolvedValue(VIEW);
    render(<CustomerPortal />);
    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    await screen.findByRole('button', { name: /The kettle leaks/ });

    // The box sits above the list.
    const box = screen.getByLabelText(/case ID/i);
    expect(box.compareDocumentPosition(screen.getByText(/My Requests/)) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    // Words filter the list; Enter opens the only match.
    fireEvent.change(box, { target: { value: 'BLENDER' } });
    expect(screen.getByText('My Requests (1 of 2)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /The kettle leaks/ })).not.toBeInTheDocument();
    fireEvent.submit(box.closest('form')!);
    await waitFor(() => expect(getCustomerCase).toHaveBeenCalledWith('case_live_mine'));
    expect(box).toHaveValue('case_live_mine');

    // Nothing matches: the list says so, and Enter looks the text up as a case ID.
    vi.mocked(getCustomerCase).mockClear();
    fireEvent.change(box, { target: { value: 'case_older_one' } });
    expect(await screen.findByText(/None of your requests matches this/)).toBeInTheDocument();
    fireEvent.submit(box.closest('form')!);
    await waitFor(() => expect(getCustomerCase).toHaveBeenCalledWith('case_older_one'));
  });

  it('keeps the open case when Enter meets several matches, and a search word is no case ID (1 November 2026)', async () => {
    const summary = (caseId: string, excerpt: string) => ({
      case_id: caseId,
      status: 'SUBMITTED' as const,
      created_at: VIEW.created_at,
      updated_at: VIEW.updated_at,
      awaiting_answer: false,
      excerpt,
    });
    vi.mocked(listMyCases).mockResolvedValue({
      items: [summary('case_live_mine', 'The blender stopped after one use.'), summary('case_live_kettle', 'The kettle stopped heating.')],
      limit: 20,
    });
    vi.mocked(getCustomerCase).mockResolvedValue(VIEW);
    render(<CustomerPortal />);
    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    fireEvent.click(await screen.findByRole('button', { name: /The blender stopped/ }));
    await waitFor(() => expect(getCustomerCase).toHaveBeenCalledWith('case_live_mine'));
    expect(await screen.findByText('The blender stopped after one use.', { selector: 'p' })).toBeInTheDocument();

    // Two requests match "stopped": Enter keeps them listed and the open case stays open.
    vi.mocked(getCustomerCase).mockClear();
    const box = screen.getByLabelText(/case ID/i);
    fireEvent.change(box, { target: { value: 'stopped' } });
    expect(screen.getByText('My Requests (2 of 2)')).toBeInTheDocument();
    fireEvent.submit(box.closest('form')!);
    expect(getCustomerCase).not.toHaveBeenCalled();
    expect(screen.getByText('The blender stopped after one use.', { selector: 'p' })).toBeInTheDocument();

    // Back to Track & Clarify with the word still in the box: it stays a search.
    fireEvent.click(screen.getByRole('button', { name: 'Lodge Return' }));
    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    await screen.findByRole('button', { name: /The kettle stopped heating/ });
    expect(getCustomerCase).not.toHaveBeenCalled();
    expect(screen.queryByText(/No case with this ID/i)).not.toBeInTheDocument();
  });

  it('keeps Lookup by case ID where the server offers no list', async () => {
    vi.mocked(listMyCases).mockRejectedValue(new ApiError(405, 'Method Not Allowed', 'HTTP_405'));
    render(<CustomerPortal />);

    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    await waitFor(() => expect(listMyCases).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByText(/My Requests/)).not.toBeInTheDocument());
    expect(screen.getByLabelText(/case ID/i)).toBeInTheDocument();
  });
});
