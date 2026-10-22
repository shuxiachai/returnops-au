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

describe('CustomerPortal lodgement idempotency (Finding 1)', () => {
  beforeEach(() => {
    localStorage.clear();
    // Simulate a committed request whose response never arrived.
    vi.mocked(createCase).mockRejectedValue(
      new ApiError(0, 'response lost before it was read', 'NETWORK_ERROR')
    );
  });

  afterEach(() => {
    localStorage.clear();
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
