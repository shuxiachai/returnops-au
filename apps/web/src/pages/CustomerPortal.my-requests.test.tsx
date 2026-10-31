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
    expect(screen.getByLabelText('Case ID')).toHaveValue('case_live_mine');
    // The list folds away so the case is what the customer reads.
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Show list/ })).toBeInTheDocument();
  });

  it('keeps Lookup by case ID where the server offers no list', async () => {
    vi.mocked(listMyCases).mockRejectedValue(new ApiError(405, 'Method Not Allowed', 'HTTP_405'));
    render(<CustomerPortal />);

    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    await waitFor(() => expect(listMyCases).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByText(/My Requests/)).not.toBeInTheDocument());
    expect(screen.getByLabelText('Case ID')).toBeInTheDocument();
  });
});
