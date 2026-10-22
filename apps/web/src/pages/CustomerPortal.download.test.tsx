import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CustomerPortal } from './CustomerPortal';

// Only the protected-download call is stubbed; everything else stays real so
// the track-and-clarify projection renders from the mock store (Finding 5).
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    downloadEvidence: vi.fn(),
  };
});

import { ApiError, downloadEvidence } from '../api/client';

describe('CustomerPortal protected evidence download (Finding 5)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(downloadEvidence).mockResolvedValue(undefined);
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('surfaces a visible error when a protected download is rejected (403)', async () => {
    vi.mocked(downloadEvidence).mockRejectedValue(
      new ApiError(403, 'evidence access forbidden', 'FORBIDDEN')
    );

    render(<CustomerPortal />);
    fireEvent.click(screen.getByRole('button', { name: /Track & Clarify \(UC-01E\)/i }));

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /^Download$/i }));

    expect(await screen.findByText(/\[FORBIDDEN\] evidence access forbidden/i)).toBeInTheDocument();
  });

  it('invokes the protected download for an authorised user without a visible error', async () => {
    render(<CustomerPortal />);
    fireEvent.click(screen.getByRole('button', { name: /Track & Clarify \(UC-01E\)/i }));

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /^Download$/i }));

    await waitFor(() => {
      expect(vi.mocked(downloadEvidence)).toHaveBeenCalledWith('ev_demo_01', 'parcel_package_label.jpg');
    });
    expect(screen.queryByText(/Failed to download evidence content/i)).not.toBeInTheDocument();
  });
});
