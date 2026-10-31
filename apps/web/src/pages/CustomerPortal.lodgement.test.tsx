import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

// After a lodgement, in Live API mode: the form the next case starts from, the
// receipt, the Track read, the clarification confirmation and the file inputs.
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    isMockMode: vi.fn(() => false),
    createCase: vi.fn(),
    getCustomerCase: vi.fn(),
    submitClarification: vi.fn(),
  };
});

import { ApiError, createCase, getCustomerCase, submitClarification } from '../api/client';
import { CustomerPortal } from './CustomerPortal';
import type { CustomerCaseView } from '../types/domain';

// A server case ID: "case_" plus 32 hexadecimal characters, with no break point.
const CASE_ID = `case_${'4f1e'.repeat(8)}`;
const EARLIER_CASE_ID = `case_${'a'.repeat(32)}`;

function caseView(caseId: string, status: CustomerCaseView['status'], version: number, withQuestions = false): CustomerCaseView {
  return {
    case_id: caseId,
    case_version: version,
    input_version: version,
    status,
    created_at: '2026-10-30T00:00:00Z',
    updated_at: '2026-10-30T00:00:00Z',
    statements: [
      { statement_id: 'stmt_original', kind: 'ORIGINAL', raw_text: 'Two cups arrived chipped.', submitted_at: '2026-10-30T00:00:00Z' },
    ],
    evidence: [],
    ...(withQuestions
      ? {
          clarification: {
            question_set_id: 'qset_live',
            input_version: version,
            questions: [{ question_id: 'q_order', text: 'What is your order reference?', reason: 'No order is verified.' }],
          },
        }
      : {}),
  };
}

const statementField = () => screen.getByPlaceholderText(/Tell us what happened with your purchase/i);

async function lodge(statement: string) {
  fireEvent.change(statementField(), { target: { value: statement } });
  fireEvent.click(screen.getByRole('button', { name: /Submit Return Request/i }));
  await screen.findByText('Return Request Submitted Successfully!');
}

describe('CustomerPortal after a lodgement (Live API mode)', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.mocked(createCase).mockResolvedValue(caseView(CASE_ID, 'SUBMITTED', 1));
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('starts the next case from "Not sure" instead of the outcome chosen for the last one', async () => {
    render(<CustomerPortal />);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'REFUND' } });
    await lodge('Two of the cups I ordered arrived chipped. I would like a refund.');
    expect(vi.mocked(createCase).mock.calls[0][0]).toMatchObject({ requested_outcome: 'REFUND' });

    fireEvent.click(screen.getByRole('button', { name: /Lodge Another Return/i }));
    expect(screen.getByRole('combobox')).toHaveValue('UNSPECIFIED');
    await lodge('The kettle stopped heating after two days.');
    expect(vi.mocked(createCase).mock.calls[1][0]).toMatchObject({ requested_outcome: 'UNSPECIFIED' });
  });

  it('wraps the long case ID in the receipt instead of running it into the status badge', async () => {
    render(<CustomerPortal />);
    await lodge('Two of the cups I ordered arrived chipped.');

    expect(screen.getByText(CASE_ID)).toHaveClass('break-all');
  });

  it('reads the new case once when the customer follows Track This Case', async () => {
    vi.mocked(getCustomerCase).mockResolvedValue(caseView(CASE_ID, 'UNDER_INVESTIGATION', 2));
    render(<CustomerPortal />);
    await lodge('Two of the cups I ordered arrived chipped.');

    fireEvent.click(screen.getByRole('button', { name: /Track This Case & View Status/i }));
    expect(await screen.findByText('Being reviewed')).toBeInTheDocument();
    await waitFor(() => expect(getCustomerCase).toHaveBeenCalledTimes(1));
    expect(getCustomerCase).toHaveBeenCalledWith(CASE_ID);
  });

  it('drops the confirmation for answers on an earlier case once a new case is lodged', async () => {
    vi.mocked(getCustomerCase)
      .mockResolvedValueOnce(caseView(EARLIER_CASE_ID, 'AWAITING_INFORMATION', 2, true))
      .mockResolvedValue(caseView(EARLIER_CASE_ID, 'UNDER_INVESTIGATION', 3));
    vi.mocked(submitClarification).mockResolvedValue(caseView(EARLIER_CASE_ID, 'UNDER_INVESTIGATION', 3));
    render(<CustomerPortal />);

    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    fireEvent.change(screen.getByLabelText(/case ID/i), { target: { value: EARLIER_CASE_ID } });
    fireEvent.click(screen.getByRole('button', { name: /Lookup/i }));
    fireEvent.change(await screen.findByPlaceholderText('Your answer...'), { target: { value: 'SYN-1001' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit Answers/i }));
    expect(await screen.findByText(/Your answers were received/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Lodge Return' }));
    await lodge('The kettle stopped heating after two days.');
    // Back on Track & Clarify the earlier case is read again, without the old confirmation.
    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    expect(await screen.findByText(EARLIER_CASE_ID)).toBeInTheDocument();
    expect(screen.queryByText(/Your answers were received/i)).not.toBeInTheDocument();
  });

  it('lets the keyboard reach Add File on the lodgement and the clarification forms', async () => {
    vi.mocked(getCustomerCase).mockResolvedValue(caseView(EARLIER_CASE_ID, 'AWAITING_INFORMATION', 2, true));
    render(<CustomerPortal />);

    // Visually hidden rather than display:none, which no keyboard can reach.
    const lodgeInput = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    expect(lodgeInput).toHaveClass('sr-only');
    expect(lodgeInput).not.toHaveClass('hidden');
    lodgeInput.focus();
    expect(lodgeInput).toHaveFocus();

    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    fireEvent.change(screen.getByLabelText(/case ID/i), { target: { value: EARLIER_CASE_ID } });
    fireEvent.click(screen.getByRole('button', { name: /Lookup/i }));
    await screen.findByPlaceholderText('Your answer...');
    const clarifyInput = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    expect(clarifyInput).toHaveClass('sr-only');
    expect(clarifyInput).not.toHaveClass('hidden');
  });
});

function picture(name: string, bytes = 12, type = 'image/png'): File {
  const file = new File(['image bytes'], name, { type });
  Object.defineProperty(file, 'size', { value: bytes });
  return file;
}

describe('CustomerPortal edge cases on the forms (Live API mode)', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('refuses a wrong type, an empty or oversize file and an eleventh file on selection, and says why', () => {
    render(<CustomerPortal />);
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;

    fireEvent.change(input, {
      target: {
        files: [
          picture('notes.txt', 10, 'text/plain'),
          picture('empty.png', 0),
          picture('huge.png', 10 * 1024 * 1024 + 1),
          ...Array.from({ length: 11 }, (_, i) => picture(`chair_${i + 1}.png`)),
        ],
      },
    });

    // Ten files are the server's limit; nothing over it reaches the upload route.
    expect(screen.getAllByRole('button', { name: /^Remove chair_/ })).toHaveLength(10);
    expect(screen.queryByText('notes.txt')).not.toBeInTheDocument();
    const notice = screen.getByRole('alert');
    expect(notice).toHaveTextContent('notes.txt is not a JPEG, PNG or PDF file.');
    expect(notice).toHaveTextContent('empty.png is empty.');
    expect(notice).toHaveTextContent('huge.png is larger than 10 MB.');
    expect(notice).toHaveTextContent('chair_11.png was not added: at most 10 files can be attached.');
  });

  it('refuses a wrong file type on the clarification form as well', async () => {
    vi.mocked(getCustomerCase).mockResolvedValue(caseView(EARLIER_CASE_ID, 'AWAITING_INFORMATION', 2, true));
    render(<CustomerPortal />);
    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    fireEvent.change(screen.getByLabelText(/case ID/i), { target: { value: EARLIER_CASE_ID } });
    fireEvent.click(screen.getByRole('button', { name: /Lookup/i }));
    await screen.findByPlaceholderText('Your answer...');

    fireEvent.change(document.querySelector<HTMLInputElement>('input[type="file"]')!, {
      target: { files: [picture('invoice.docx', 2000, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')] },
    });
    expect(screen.getByRole('alert')).toHaveTextContent('invoice.docx is not a JPEG, PNG or PDF file.');
    expect(screen.queryByRole('button', { name: 'Remove invoice.docx' })).not.toBeInTheDocument();
  });

  it('shows a refused lodgement next to the Submit button, not at the top of the form', async () => {
    vi.mocked(createCase).mockRejectedValue(
      new ApiError(422, 'Request fields are invalid.', 'VALIDATION_ERROR', undefined, undefined, false)
    );
    render(<CustomerPortal />);
    fireEvent.change(statementField(), { target: { value: 'The kettle stopped heating after two days.' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit Return Request/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('[VALIDATION_ERROR] Request fields are invalid.');
    expect(alert.nextElementSibling).toContainElement(screen.getByRole('button', { name: /Submit Return Request/i }));
  });

  it('looks a case up with Enter in the box, once, and not again while that lookup runs', async () => {
    let settle!: (view: CustomerCaseView) => void;
    vi.mocked(getCustomerCase).mockReturnValue(new Promise((resolve) => { settle = resolve; }));
    render(<CustomerPortal />);
    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    const box = screen.getByRole('textbox', { name: /case ID/i });
    fireEvent.change(box, { target: { value: ` ${CASE_ID} ` } });

    // Enter submits the lookup form, as the Lookup button does.
    fireEvent.submit(box.closest('form')!);
    fireEvent.submit(box.closest('form')!);
    expect(getCustomerCase).toHaveBeenCalledTimes(1);
    expect(getCustomerCase).toHaveBeenCalledWith(CASE_ID);
    expect(screen.getByRole('button', { name: /Lookup/i })).toHaveAttribute('type', 'submit');

    settle(caseView(CASE_ID, 'UNDER_INVESTIGATION', 2));
    expect(await screen.findByText('Being reviewed')).toBeInTheDocument();
    // The case ID box keeps its full width below 1024 px: the bar stacks until then.
    expect(box.closest('form')!.parentElement).toHaveClass('flex-col', 'lg:flex-row');
  });

  it('tells the customer in plain words when a case ID is malformed', async () => {
    vi.mocked(getCustomerCase).mockRejectedValue(new ApiError(422, 'Request fields are invalid.', 'VALIDATION_ERROR'));
    render(<CustomerPortal />);
    fireEvent.click(screen.getByRole('button', { name: 'Track & Clarify' }));
    fireEvent.change(screen.getByRole('textbox', { name: /case ID/i }), { target: { value: 'not a case id!' } });
    fireEvent.click(screen.getByRole('button', { name: /Lookup/i }));

    expect(
      await screen.findByText('This is not a valid case ID. Use the ID shown when your request was lodged.')
    ).toBeInTheDocument();
    expect(screen.queryByText(/VALIDATION_ERROR/)).not.toBeInTheDocument();
  });
});
