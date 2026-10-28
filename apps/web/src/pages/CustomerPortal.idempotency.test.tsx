import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CustomerPortal } from './CustomerPortal';

// Only case creation is stubbed so the lodgement retry identity can be
// observed without a live backend (Finding 1).
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    createCase: vi.fn(),
  };
});

import { ApiError, createCase } from '../api/client';
import type { CustomerCaseView } from '../types/domain';

// The lodgement key and its payload are kept in sessionStorage for the tab (#122 item 7).
const STORED_KEY = 'returnops_lodgement_idempotency';

describe('CustomerPortal lodgement idempotency (Finding 1)', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    // Simulate a committed request whose response never arrived.
    vi.mocked(createCase).mockRejectedValue(
      new ApiError(0, 'response lost before it was read', 'NETWORK_ERROR')
    );
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('reuses the original key when the identical payload is retried after a lost response', async () => {
    render(<CustomerPortal />);

    fireEvent.change(screen.getByPlaceholderText(/Tell us what happened with your purchase/i), {
      target: { value: 'Lost-response retry payload for the same return intent.' },
    });

    const submit = () => screen.getByRole('button', { name: /Submit Return Request/i });

    fireEvent.click(submit());
    await waitFor(() => expect(vi.mocked(createCase)).toHaveBeenCalledTimes(1));
    // The uncertain outcome must leave the form available for retry.
    expect(screen.getByText(/\[NETWORK_ERROR\] response lost before it was read/i)).toBeInTheDocument();

    fireEvent.click(submit());
    await waitFor(() => expect(vi.mocked(createCase)).toHaveBeenCalledTimes(2));

    const firstKey = vi.mocked(createCase).mock.calls[0][1];
    const secondKey = vi.mocked(createCase).mock.calls[1][1];
    expect(firstKey).toBeTruthy();
    expect(secondKey).toBe(firstKey);
  });

  it('never silently reuses a key when the payload materially changed', async () => {
    render(<CustomerPortal />);

    const textarea = screen.getByPlaceholderText(/Tell us what happened with your purchase/i);
    fireEvent.change(textarea, { target: { value: 'First version of the request.' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit Return Request/i }));
    await waitFor(() => expect(vi.mocked(createCase)).toHaveBeenCalledTimes(1));

    fireEvent.change(textarea, {
      target: { value: 'A materially different request for a different product.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Submit Return Request/i }));
    await waitFor(() => expect(vi.mocked(createCase)).toHaveBeenCalledTimes(2));

    const firstKey = vi.mocked(createCase).mock.calls[0][1];
    const secondKey = vi.mocked(createCase).mock.calls[1][1];
    expect(firstKey).toBeTruthy();
    expect(secondKey).not.toBe(firstKey);
  });
});

describe('CustomerPortal lodgement key across a reload (#122 item 7)', () => {
  const TEXT = 'The kettle stopped heating after two days. I would like a replacement.';
  const statement = () => screen.getByPlaceholderText(/Tell us what happened with your purchase/i);
  const submit = () => screen.getByRole('button', { name: /Submit Return Request/i });

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.mocked(createCase).mockRejectedValue(
      new ApiError(0, 'response lost before it was read', 'NETWORK_ERROR')
    );
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('re-sends the same key after a reload when the customer sends the same request', async () => {
    const before = render(<CustomerPortal />);
    fireEvent.change(statement(), { target: { value: TEXT } });
    fireEvent.click(submit());
    await waitFor(() => expect(vi.mocked(createCase)).toHaveBeenCalledTimes(1));
    expect(sessionStorage.getItem(STORED_KEY)).not.toBeNull();

    // A reload: the page state is gone, the tab's sessionStorage is not.
    before.unmount();
    render(<CustomerPortal />);
    fireEvent.change(statement(), { target: { value: TEXT } });
    fireEvent.click(submit());
    await waitFor(() => expect(vi.mocked(createCase)).toHaveBeenCalledTimes(2));

    const [first, second] = vi.mocked(createCase).mock.calls;
    expect(first[1]).toBeTruthy();
    expect(second[1]).toBe(first[1]);
  });

  it('mints a new key after a reload when the request changed', async () => {
    const before = render(<CustomerPortal />);
    fireEvent.change(statement(), { target: { value: TEXT } });
    fireEvent.click(submit());
    await waitFor(() => expect(vi.mocked(createCase)).toHaveBeenCalledTimes(1));

    before.unmount();
    render(<CustomerPortal />);
    fireEvent.change(statement(), { target: { value: `${TEXT} It also leaks.` } });
    fireEvent.click(submit());
    await waitFor(() => expect(vi.mocked(createCase)).toHaveBeenCalledTimes(2));

    const [first, second] = vi.mocked(createCase).mock.calls;
    expect(second[1]).toBeTruthy();
    expect(second[1]).not.toBe(first[1]);
  });

  it('forgets the stored key once the case is accepted', async () => {
    const accepted: CustomerCaseView = {
      case_id: 'case_demo_901',
      case_version: 1,
      input_version: 1,
      status: 'SUBMITTED',
      created_at: '2026-10-27T00:00:00Z',
      updated_at: '2026-10-27T00:00:00Z',
      statements: [
        { statement_id: 'stmt_901', kind: 'ORIGINAL', raw_text: TEXT, submitted_at: '2026-10-27T00:00:00Z' },
      ],
      evidence: [],
    };
    vi.mocked(createCase).mockResolvedValueOnce(accepted);

    render(<CustomerPortal />);
    fireEvent.change(statement(), { target: { value: TEXT } });
    fireEvent.click(submit());

    expect(await screen.findByText('Return Request Submitted Successfully!')).toBeInTheDocument();
    expect(sessionStorage.getItem(STORED_KEY)).toBeNull();
  });
});
