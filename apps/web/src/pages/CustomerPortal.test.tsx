import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CustomerPortal } from './CustomerPortal';
import { setMockMode } from '../api/client';

describe('CustomerPortal (UC-01 & UC-01E)', () => {
  beforeEach(() => {
    localStorage.clear();
    setMockMode(true);
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders Customer Portal heading and intake form by default', () => {
    render(<CustomerPortal />);

    expect(screen.getByText('Customer Service Portal')).toBeInTheDocument();
    expect(screen.getByText(/Describe your problem in your own words/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Tell us what happened with your purchase/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Submit Return Request/i })).toBeInTheDocument();
  });

  it('disables submission button when natural language statement is empty', () => {
    render(<CustomerPortal />);

    const submitBtn = screen.getByRole('button', { name: /Submit Return Request/i });
    expect(submitBtn).toBeDisabled();
  });

  it('enables submit button when valid statement is provided and successfully lodges case', async () => {
    render(<CustomerPortal />);

    const textarea = screen.getByPlaceholderText(/Tell us what happened with your purchase/i);
    fireEvent.change(textarea, {
      target: {
        value: 'The package arrived completely crushed and the coffee machine is cracked.',
      },
    });

    const submitBtn = screen.getByRole('button', { name: /Submit Return Request/i });
    expect(submitBtn).not.toBeDisabled();

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Return Request Submitted Successfully!')).toBeInTheDocument();
    });

    // The receipt is SUBMITTED: the intake runs on the next read, not here.
    expect(screen.getByText('Received')).toBeInTheDocument();
    expect(screen.queryByText('SUBMITTED')).not.toBeInTheDocument();
    expect(screen.getByText(/Lodge Another Return/i)).toBeInTheDocument();
  });

  it('shows no demo cases or demo case ID in Live API mode (#111 item 3)', async () => {
    localStorage.setItem('returnops_mock_mode', 'false');
    render(<CustomerPortal />);

    fireEvent.click(screen.getByRole('button', { name: /Track & Clarify/i }));

    expect(screen.queryByText(/Demo Cases/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /case_demo_00/i })).not.toBeInTheDocument();
    expect(screen.getByLabelText(/case ID/i)).toHaveValue('');
    expect(screen.queryByText(/UC-0/)).not.toBeInTheDocument();
  });

  it('switches to Track & Clarify tab and loads demo case questions', async () => {
    render(<CustomerPortal />);

    const trackTabBtn = screen.getByRole('button', { name: /Track & Clarify/i });
    fireEvent.click(trackTabBtn);

    // Track tab lookup controls should appear
    expect(screen.getByLabelText(/case ID/i)).toBeInTheDocument();

    // In mock mode, case_demo_001 is loaded on mount when activeSubTab is track
    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    expect(screen.getByText('We need a bit more information')).toBeInTheDocument();
    expect(screen.queryByText('AWAITING_INFORMATION')).not.toBeInTheDocument();
    expect(
      screen.getByText(/Please confirm the SKU or barcode number printed on the garment label tag./i)
    ).toBeInTheDocument();
  });

  it('submits clarification answers and handles HTTP 202 acceptance feedback', async () => {
    render(<CustomerPortal />);

    const trackTabBtn = screen.getByRole('button', { name: /Track & Clarify/i });
    fireEvent.click(trackTabBtn);

    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    // Find all question answer inputs with placeholder "Your answer..." and fill required inputs
    const answerInputs = screen.getAllByPlaceholderText('Your answer...');
    expect(answerInputs.length).toBeGreaterThan(0);

    answerInputs.forEach((input, index) => {
      fireEvent.change(input, {
        target: { value: `Valid supplementary answer detail ${index + 1}` },
      });
    });

    const submitClarifyBtn = screen.getByRole('button', {
      name: /Submit Answers/i,
    });
    fireEvent.click(submitClarifyBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Your answers were received/i)
      ).toBeInTheDocument();
    });
  });

  it('displays error alert when looking up non-existent case', async () => {
    render(<CustomerPortal />);

    const trackTabBtn = screen.getByRole('button', { name: /Track & Clarify/i });
    fireEvent.click(trackTabBtn);

    // Wait for initial load to settle
    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    const lookupInput = screen.getByLabelText(/case ID/i);
    fireEvent.change(lookupInput, { target: { value: 'case_does_not_exist_999' } });

    const lookupBtn = screen.getByRole('button', { name: /Lookup/i });
    expect(lookupBtn).not.toBeDisabled();
    fireEvent.click(lookupBtn);

    // The customer reads plain words, not the raw NOT_FOUND code.
    await waitFor(() => {
      expect(
        screen.getByText('No case with this ID was found for your account. Check the ID and try again.')
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/NOT_FOUND/)).not.toBeInTheDocument();
  });

  it('blocks case submission while a selected evidence file is unstaged (Finding 7)', async () => {
    render(<CustomerPortal />);

    const textarea = screen.getByPlaceholderText(/Tell us what happened with your purchase/i);
    fireEvent.change(textarea, {
      target: { value: 'My parcel arrived crushed and the item inside is damaged.' },
    });

    const submitBtn = screen.getByRole('button', { name: /Submit Return Request/i });
    // With a valid statement and no files, submission is allowed.
    expect(submitBtn).not.toBeDisabled();

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['dummy image bytes'], 'receipt.png', { type: 'image/png' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    // The unstaged file must be listed before submission is attempted.
    expect(await screen.findByText('receipt.png')).toBeInTheDocument();

    // Submission stays blocked and the reason is visible to the customer.
    expect(screen.getByRole('button', { name: /Submit Return Request/i })).toBeDisabled();
    expect(
      screen.getByText(/Please stage or remove all selected evidence files before submitting/i)
    ).toBeInTheDocument();

    // Even a forced click must not lodge the case.
    fireEvent.click(screen.getByRole('button', { name: /Submit Return Request/i }));
    await waitFor(() => {
      expect(screen.queryByText('Return Request Submitted Successfully!')).not.toBeInTheDocument();
    });

    // Removing the unstaged file unblocks submission.
    fireEvent.click(screen.getByRole('button', { name: /Remove receipt\.png/i }));
    expect(screen.queryByText('receipt.png')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Submit Return Request/i })).not.toBeDisabled();
  });

  it('reports the 12,000-character intake bound as advisory rather than enforced (Finding 12)', () => {
    render(<CustomerPortal />);

    const textarea = screen.getByPlaceholderText(
      /Tell us what happened with your purchase/i
    ) as HTMLTextAreaElement;

    // Exactly at the documented capacity the counter reads 12,000 / 12,000.
    fireEvent.change(textarea, { target: { value: 'a'.repeat(12000) } });
    expect(screen.getByText('12000 / 12,000 chars')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Submit Return Request/i })).not.toBeDisabled();

    // One character past the bound, the counter keeps counting: the bound is a
    // display affordance here, not a client-side rejection rule.
    fireEvent.change(textarea, { target: { value: 'a'.repeat(12001) } });
    expect(screen.getByText('12001 / 12,000 chars')).toBeInTheDocument();
    expect(textarea).not.toHaveAttribute('maxlength');
  });

  it('holds the order reference to the 120 characters the server accepts, and says so', () => {
    render(<CustomerPortal />);

    // A 121st character used to reach the server and come back as "Request fields are invalid".
    expect(screen.getByPlaceholderText('e.g. SYN-1001')).toHaveAttribute('maxlength', '120');
    expect(screen.getByText('(Optional, up to 120 characters)')).toBeInTheDocument();
  });

  it('shows a completed case with its outcome, the long ID wrapping and the customer words breaking', async () => {
    render(<CustomerPortal />);
    fireEvent.click(screen.getByRole('button', { name: /Track & Clarify/i }));
    // The tab first opens the demo case; Lookup is disabled until that read settles.
    await screen.findByText('case_demo_001', { selector: 'span' });
    fireEvent.change(screen.getByLabelText(/case ID/i), { target: { value: 'case_demo_005' } });
    fireEvent.click(screen.getByRole('button', { name: /^Lookup$/ }));

    expect(await screen.findByText('Completed')).toBeInTheDocument();
    // Mock Mode now tells the customer what the Founder's Outcome tab shows as sent.
    expect(screen.getByText(/A simulated return and parcel label have been recorded/)).toBeInTheDocument();
    const id = screen.getByText('case_demo_005', { selector: 'span' });
    expect(id).toHaveClass('break-all');
    expect(id.parentElement).toHaveClass('flex-wrap');
    const words = screen.getByText(/My Synthbrew S2 coffee machine stopped heating/);
    expect(words).toHaveClass('break-words');
    expect(words).toHaveAttribute('dir', 'auto');
  });
});
