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
    expect(screen.getByText(/Lodge return requests with natural language/i)).toBeInTheDocument();
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

    expect(screen.getByText('SUBMITTED')).toBeInTheDocument();
    expect(screen.getByText(/Lodge Another Return/i)).toBeInTheDocument();
  });

  it('switches to Track & Clarify tab and loads demo case questions', async () => {
    render(<CustomerPortal />);

    const trackTabBtn = screen.getByRole('button', { name: /Track & Clarify \(UC-01E\)/i });
    fireEvent.click(trackTabBtn);

    // Track tab lookup controls should appear
    expect(screen.getByPlaceholderText(/Enter Case ID/i)).toBeInTheDocument();

    // In mock mode, case_demo_001 is loaded on mount when activeSubTab is track
    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    expect(screen.getByText('AWAITING_INFORMATION')).toBeInTheDocument();
    expect(
      screen.getByText(/Please confirm the SKU or barcode number printed on the garment label tag./i)
    ).toBeInTheDocument();
  });

  it('submits clarification answers and handles HTTP 202 acceptance feedback', async () => {
    render(<CustomerPortal />);

    const trackTabBtn = screen.getByRole('button', { name: /Track & Clarify \(UC-01E\)/i });
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
      name: /Submit Supplementary Clarification/i,
    });
    fireEvent.click(submitClarifyBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Clarification successfully admitted \(HTTP 202\)/i)
      ).toBeInTheDocument();
    });
  });

  it('displays error alert when looking up non-existent case', async () => {
    render(<CustomerPortal />);

    const trackTabBtn = screen.getByRole('button', { name: /Track & Clarify \(UC-01E\)/i });
    fireEvent.click(trackTabBtn);

    // Wait for initial load to settle
    await waitFor(() => {
      expect(screen.getByText('case_demo_001')).toBeInTheDocument();
    });

    const lookupInput = screen.getByPlaceholderText(/Enter Case ID/i);
    fireEvent.change(lookupInput, { target: { value: 'case_does_not_exist_999' } });

    const lookupBtn = screen.getByRole('button', { name: /Lookup/i });
    expect(lookupBtn).not.toBeDisabled();
    fireEvent.click(lookupBtn);

    await waitFor(() => {
      expect(screen.getByText(/NOT_FOUND: Case case_does_not_exist_999 not found/i)).toBeInTheDocument();
    });
  });
});
