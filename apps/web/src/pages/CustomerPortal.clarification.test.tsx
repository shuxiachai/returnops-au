import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CustomerPortal } from './CustomerPortal';

// Only the clarification submit and the multipart staging call are stubbed, so
// the evidence identity that actually reaches the wire can be observed from the
// UI (Finding 8: staged clarification evidence must not be dropped in the UI).
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    stageEvidence: vi.fn(),
    submitClarification: vi.fn(),
  };
});

import { setMockMode, stageEvidence, submitClarification } from '../api/client';
import { MOCK_CUSTOMER_CASES } from '../api/mockData';

describe('CustomerPortal clarification evidence binding (Finding 8)', () => {
  beforeEach(() => {
    localStorage.clear();
    setMockMode(true);
    vi.mocked(stageEvidence).mockResolvedValue({
      evidence_id: 'ev_clarify_staged_01',
      filename: 'barcode.png',
      media_type: 'image/png',
      size_bytes: 12,
      sha256: 'd4e5f67890123456789abcdef0123456789abcdef0123456789abcdef012345',
      status: 'STAGED',
      created_at: '2026-10-15T00:00:00Z',
    });
    vi.mocked(submitClarification).mockImplementation(async (caseId: string) => ({
      ...MOCK_CUSTOMER_CASES[caseId],
    }));
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('carries the staged evidence_id on the clarification submit wire payload', async () => {
    render(<CustomerPortal />);

    fireEvent.click(screen.getByRole('button', { name: /Track & Clarify/i }));

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    // Attach supplementary evidence to the clarification and stage it.
    const addFileLabel = screen.getByText('Add File').closest('label');
    const fileInput = addFileLabel?.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeTruthy();

    fireEvent.change(fileInput, {
      target: { files: [new File(['barcode bytes'], 'barcode.png', { type: 'image/png' })] },
    });

    // Staging is an explicit step here, not implicit on selection.
    fireEvent.click(await screen.findByRole('button', { name: /^Stage File$/i }));

    await waitFor(() => {
      expect(vi.mocked(stageEvidence)).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText('Staged')).toBeInTheDocument();

    // Answer the questions and submit (the answer fields are `required`, so the
    // browser-level form validation must be satisfied for the submit to fire).
    const answerInputs = screen.getAllByPlaceholderText('Your answer...');
    answerInputs.forEach((input, index) => {
      fireEvent.change(input, { target: { value: `Supplementary answer ${index + 1} for the reviewer.` } });
    });
    fireEvent.click(screen.getByRole('button', { name: /Submit Answers/i }));

    await waitFor(() => {
      expect(vi.mocked(submitClarification)).toHaveBeenCalledTimes(1);
    });

    const wirePayload = vi.mocked(submitClarification).mock.calls[0][1];
    // The staged evidence identity reaches the wire rather than being dropped.
    expect(wirePayload.evidence_ids).toEqual(['ev_clarify_staged_01']);
    // ...and the retry identity is threaded through as a real idempotency key.
    expect(vi.mocked(submitClarification).mock.calls[0][2]).toBeTruthy();
  });
});
