import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CustomerPortal } from './CustomerPortal';
import type { CustomerCaseView, StagedEvidence } from '../types/domain';

// Issue #88 (KAN-18; FR-001, NFR-006; UC-01/01E): while a customer POST is pending,
// the draft is frozen so a success reset cannot discard edits made during the wait.
// Boundary mocks only.
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    getCustomerCase: vi.fn(),
    stageEvidence: vi.fn(),
    createCase: vi.fn(),
    submitClarification: vi.fn(),
  };
});

import { ApiError, createCase, getCustomerCase, stageEvidence, submitClarification } from '../api/client';

const caseId = 'case_demo_001';
const statement = 'The kettle arrived with a cracked base.';
const answer = 'Barcode 9312345678901';

function caseView(version = 2): CustomerCaseView {
  return {
    case_id: caseId,
    case_version: version,
    input_version: 1,
    status: 'AWAITING_INFORMATION',
    created_at: '2026-10-22T00:00:00Z',
    updated_at: '2026-10-22T00:00:00Z',
    statements: [{ statement_id: 'stmt_1', kind: 'ORIGINAL', raw_text: statement, submitted_at: '2026-10-22T00:00:00Z' }],
    evidence: [],
    clarification: {
      question_set_id: 'qset_1',
      input_version: 1,
      questions: [{ question_id: 'q_barcode', text: 'What barcode is on the label?' }],
    },
  };
}

function staged(name: string): StagedEvidence {
  return {
    evidence_id: `ev_${name.replace('.', '_')}`,
    filename: name,
    media_type: 'image/png',
    size_bytes: 12,
    sha256: 'a'.repeat(64),
    status: 'STAGED',
    created_at: '2026-10-22T00:00:00Z',
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function fileInput() {
  return document.querySelector<HTMLInputElement>('input[type="file"]')!;
}

function attachFile(name: string) {
  fireEvent.change(fileInput(), { target: { files: [new File(['image bytes'], name, { type: 'image/png' })] } });
}

async function attachAndStage(name: string) {
  attachFile(name);
  fireEvent.click(screen.getByRole('button', { name: /^Stage File$/i }));
  await waitFor(() => expect(screen.queryByRole('button', { name: /^Stage File$/i })).not.toBeInTheDocument());
}

// Tries every draft change a customer could make; the caller asserts none took effect.
function attemptChangesWhilePending(textFields: HTMLElement[], stagedName: string) {
  textFields.forEach(field => fireEvent.change(field, { target: { value: 'Edited while pending' } }));
  attachFile('late.png');
  fireEvent.click(screen.getByRole('button', { name: `Remove ${stagedName}` }));
}

beforeEach(() => {
  localStorage.clear();
  vi.resetAllMocks();
  vi.spyOn(window, 'alert').mockImplementation(() => undefined);
  vi.mocked(getCustomerCase).mockImplementation(async () => caseView());
  vi.mocked(stageEvidence).mockImplementation(async file => staged(file.name));
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('lodgement while createCase is pending', () => {
  const statementField = () => screen.getByPlaceholderText(/Tell us what happened with your purchase/i);
  const orderField = () => screen.getByPlaceholderText('e.g. SYN-1001');
  const outcomeField = () => screen.getByRole('combobox');

  async function submitPending() {
    const pending = deferred<CustomerCaseView>();
    vi.mocked(createCase).mockReturnValueOnce(pending.promise);
    render(<CustomerPortal />);
    fireEvent.change(statementField(), { target: { value: statement } });
    fireEvent.change(orderField(), { target: { value: 'ORD-1' } });
    await attachAndStage('receipt.png');
    fireEvent.click(screen.getByRole('button', { name: /Submit Return Request/i }));
    await waitFor(() => expect(createCase).toHaveBeenCalledTimes(1));
    return pending;
  }

  const draftControls = () =>
    [statementField(), orderField(), outcomeField(), fileInput(), screen.getByRole('button', { name: 'Remove receipt.png' })];

  function expectFrozenSubmittedDraft() {
    draftControls().forEach(control => expect(control).toBeDisabled());
    expect(statementField()).toHaveValue(statement);
    expect(orderField()).toHaveValue('ORD-1');
    expect(outcomeField()).toHaveValue('UNSPECIFIED');
    expect(screen.getByText('Staged', { exact: true })).toHaveAttribute('data-evidence-id', 'ev_receipt_png');
    expect(screen.queryByText('late.png')).not.toBeInTheDocument();
    // Every submitted file is already staged and adding is refused, so nothing can be staged.
    expect(screen.queryByRole('button', { name: /^Stage File$/i })).not.toBeInTheDocument();
    expect(stageEvidence).toHaveBeenCalledTimes(1);
  }

  it('refuses edit, add, stage and remove, so success clears only what was submitted', async () => {
    const pending = await submitPending();
    attemptChangesWhilePending([statementField(), orderField()], 'receipt.png');
    fireEvent.change(outcomeField(), { target: { value: 'REPAIR' } });
    expectFrozenSubmittedDraft();

    await act(async () => {
      pending.resolve({ ...caseView(1), status: 'SUBMITTED', clarification: undefined });
      await pending.promise;
    });

    expect(screen.getByText('Return Request Submitted Successfully!')).toBeInTheDocument();
    expect(vi.mocked(createCase).mock.calls[0][0]).toEqual({
      original_message: statement,
      order_reference: 'ORD-1',
      requested_outcome: 'UNSPECIFIED', // #111 item 5: "Not sure" is the default
      evidence_ids: ['ev_receipt_png'],
    });
    fireEvent.click(screen.getByRole('button', { name: /Lodge Another Return/i }));
    expect(statementField()).toHaveValue('');
    expect(orderField()).toHaveValue('');
    expect(outcomeField()).toHaveValue('UNSPECIFIED');
    expect(screen.queryByText('receipt.png')).not.toBeInTheDocument();
    expect(statementField()).toBeEnabled();
  });

  it('keeps the key, payload and staged evidence when the pending request fails, then unfreezes', async () => {
    const pending = await submitPending();
    attemptChangesWhilePending([statementField(), orderField()], 'receipt.png');
    expectFrozenSubmittedDraft();

    await act(async () => {
      pending.reject(new ApiError(0, 'response lost', 'NETWORK_ERROR'));
      await pending.promise.catch(() => undefined);
    });

    expect(screen.getByText(/\[NETWORK_ERROR\] response lost/i)).toBeInTheDocument();
    expect(statementField()).toHaveValue(statement);
    expect(screen.getByText('Staged', { exact: true })).toHaveAttribute('data-evidence-id', 'ev_receipt_png');
    draftControls().forEach(control => expect(control).toBeEnabled());
    vi.mocked(createCase).mockRejectedValueOnce(new ApiError(0, 'response lost', 'NETWORK_ERROR'));
    fireEvent.click(screen.getByRole('button', { name: /Submit Return Request/i }));
    await waitFor(() => expect(createCase).toHaveBeenCalledTimes(2));
    expect(vi.mocked(createCase).mock.calls[1]).toEqual(vi.mocked(createCase).mock.calls[0]);
  });
});

describe('clarification while submitClarification is pending', () => {
  const answerField = () => screen.getByPlaceholderText('Your answer...');

  async function submitPending() {
    const pending = deferred<CustomerCaseView>();
    vi.mocked(submitClarification).mockReturnValueOnce(pending.promise);
    render(<CustomerPortal />);
    fireEvent.click(screen.getByRole('button', { name: /Track & Clarify/i }));
    await screen.findByText(caseId, { exact: true });
    fireEvent.change(answerField(), { target: { value: answer } });
    await attachAndStage('barcode.png');
    fireEvent.click(screen.getByRole('button', { name: /Submit Answers/i }));
    await waitFor(() => expect(submitClarification).toHaveBeenCalledTimes(1));
    return pending;
  }

  const draftControls = () =>
    [answerField(), fileInput(), screen.getByRole('button', { name: 'Remove barcode.png' })];

  function expectFrozenSubmittedDraft() {
    draftControls().forEach(control => expect(control).toBeDisabled());
    expect(answerField()).toHaveValue(answer);
    expect(screen.getByText('barcode.png')).toBeInTheDocument();
    expect(screen.getByText('Staged')).toBeInTheDocument();
    expect(screen.queryByText('late.png')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Stage File$/i })).not.toBeInTheDocument();
    expect(stageEvidence).toHaveBeenCalledTimes(1);
  }

  it('refuses edit, add, stage and remove, so success clears only what was submitted', async () => {
    const pending = await submitPending();
    attemptChangesWhilePending([answerField()], 'barcode.png');
    expectFrozenSubmittedDraft();

    // #122 item 10: once the answers are accepted the page reads the case again,
    // so what it shows is the server's current view and not the POST receipt.
    vi.mocked(getCustomerCase).mockResolvedValue({
      ...caseView(3),
      status: 'UNDER_INVESTIGATION',
      clarification: undefined,
    });

    await act(async () => {
      pending.resolve({ ...caseView(3), status: 'UNDER_INVESTIGATION', clarification: undefined });
      await pending.promise;
    });

    expect(screen.getByText(/Your answers were received/i)).toBeInTheDocument();
    expect(vi.mocked(submitClarification).mock.calls[0][1]).toEqual({
      expected_case_version: 2,
      question_set_id: 'qset_1',
      answers: [{ question_id: 'q_barcode', text: answer }],
      evidence_ids: ['ev_barcode_png'],
    });
    expect(screen.queryByPlaceholderText('Your answer...')).not.toBeInTheDocument();
  });

  it('keeps the key, payload and staged evidence when the pending request fails, then unfreezes', async () => {
    const pending = await submitPending();
    attemptChangesWhilePending([answerField()], 'barcode.png');
    expectFrozenSubmittedDraft();

    await act(async () => {
      pending.reject(new ApiError(0, 'response lost', 'NETWORK_ERROR'));
      await pending.promise.catch(() => undefined);
    });

    expect(screen.getByText(/\[NETWORK_ERROR\] response lost/i)).toBeInTheDocument();
    expect(answerField()).toHaveValue(answer);
    expect(screen.getByText('Staged')).toBeInTheDocument();
    draftControls().forEach(control => expect(control).toBeEnabled());
    vi.mocked(submitClarification).mockRejectedValueOnce(new ApiError(0, 'response lost', 'NETWORK_ERROR'));
    fireEvent.click(screen.getByRole('button', { name: /Submit Answers/i }));
    await waitFor(() => expect(submitClarification).toHaveBeenCalledTimes(2));
    expect(vi.mocked(submitClarification).mock.calls[1]).toEqual(vi.mocked(submitClarification).mock.calls[0]);
  });
});
