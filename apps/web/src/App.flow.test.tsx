import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from './App';
import { setMockMode } from './api/client';
import {
  MOCK_CUSTOMER_CASES,
  MOCK_FOUNDER_CASE_VIEWS,
} from './api/mockData';

// KAN-20; docs/08 B2.05 and E.11: one journey through the real application in
// Mock Mode, across both pages — lodge, clarify, Founder inspect, decide, audit.
// This is the App-level Vitest variant of the two options in #122 item 6: it
// starts from <App />, uses the shared fixture store the demo falls back to, and
// stubs no boundary, so it adds no Playwright or Cypress dependency and no CI job.
//
// What it does not evidence, and says so rather than implying it: the case the
// Founder decides here is a curated queue row with a proposal, not the case
// lodged in the first half. Since #147 the lodged case does reach the Mock Mode
// queue (asserted below), but it carries no proposal to approve. Lodging and then
// deciding the same case is only possible on a real server; the recorded run of
// the 29 October rehearsal covers that.
const MOCK_VIEWS_AT_START = structuredClone(MOCK_FOUNDER_CASE_VIEWS);

const STATEMENT = 'Two of the cups I ordered arrived chipped. I would like a refund.';
const ANSWER = 'The outer carton was intact; the cups were chipped inside it.';
const RATIONALE = 'Approved under the store 30-day change of mind policy.';

describe('Mock Mode journey across both pages (KAN-20; B2.05, E.11)', () => {
  beforeEach(() => {
    localStorage.clear();
    setMockMode(true);
    for (const caseId of Object.keys(MOCK_FOUNDER_CASE_VIEWS)) delete MOCK_FOUNDER_CASE_VIEWS[caseId];
    Object.assign(MOCK_FOUNDER_CASE_VIEWS, structuredClone(MOCK_VIEWS_AT_START));
  });

  afterEach(() => {
    localStorage.clear();
    for (const caseId of Object.keys(MOCK_CUSTOMER_CASES)) {
      if (!/^case_demo_0\d\d$/.test(caseId)) delete MOCK_CUSTOMER_CASES[caseId];
    }
    vi.restoreAllMocks();
  });

  it('lodges, answers the clarification, then inspects, decides and audits the case', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    render(<App />);

    // 1. Lodge Return (UC-01): plain words, no order reference, the default outcome.
    fireEvent.change(screen.getByPlaceholderText(/Tell us what happened with your purchase/i), {
      target: { value: STATEMENT },
    });
    fireEvent.click(screen.getByRole('button', { name: /Submit Return Request/i }));

    expect(await screen.findByText('Return Request Submitted Successfully!')).toBeInTheDocument();
    // The case ID is the one thing the customer is told to keep.
    const lodgedCaseId = screen.getByText(/^case_demo_\d{3}$/).textContent as string;

    // 2. Track & Clarify (UC-01E): the store's question set, then the answers.
    fireEvent.click(screen.getByRole('button', { name: /Track This Case & View Status/i }));
    expect(
      await screen.findByText(/Provide an order reference \(at most 120 characters\)/i)
    ).toBeInTheDocument();
    // The server asks two things: the order reference, or the alternative.
    const answerFields = screen.getAllByPlaceholderText('Your answer...');
    expect(answerFields).toHaveLength(2);
    answerFields.forEach((field) => fireEvent.change(field, { target: { value: ANSWER } }));
    fireEvent.click(screen.getByRole('button', { name: /Submit Answers/i }));

    expect(
      await screen.findByText(
        'Thank you. Your answers were received and the shop will continue reviewing your case.'
      )
    ).toBeInTheDocument();
    // The question set is answered and gone; the answer and the original statement
    // are both preserved as customer statements.
    expect(screen.queryByPlaceholderText('Your answer...')).not.toBeInTheDocument();
    expect(screen.getByText(/outer carton was intact/i)).toBeInTheDocument();
    expect(screen.getByText(STATEMENT)).toBeInTheDocument();
    // The customer reads plain words, not the internal status name.
    expect(screen.getByText('Being reviewed')).toBeInTheDocument();
    expect(screen.queryByText('UNDER_INVESTIGATION')).not.toBeInTheDocument();

    // 3. The Founder console (UC-03/UC-05): the queue, then one case opened.
    fireEvent.click(screen.getByRole('button', { name: 'Founder Console' }));
    await waitFor(() => expect(screen.getByText('case_demo_003')).toBeInTheDocument());
    // The case lodged in the Customer Portal reaches the Founder's queue.
    expect(screen.getByText(lodgedCaseId)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Filter by Case ID or Category/i), {
      target: { value: 'case_demo_003' },
    });
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    // 4. Decide (UC-04): the dialog names the exact scope, and the rationale is mandatory.
    fireEvent.click(await screen.findByRole('button', { name: /Approve Return/i }));
    const rationale = await screen.findByPlaceholderText(/Record justification for statutory audit/i);
    const record = screen.getByRole('button', { name: /Record decision/i });
    expect(record).toBeDisabled();
    fireEvent.change(rationale, { target: { value: RATIONALE } });
    expect(record).toBeEnabled();
    fireEvent.click(record);

    // The case reopens on what the decision produced.
    expect(await screen.findByText('Approved scope')).toBeInTheDocument();
    expect(screen.getByText(RATIONALE)).toBeInTheDocument();

    // 5. Audit (NFR-003): the recorded chain, shown as recorded, not as verified.
    fireEvent.click(await screen.findByRole('button', { name: /Tamper-Evident Audit Chain/i }));
    expect(await screen.findByText(/Recorded Audit Events:/i)).toBeInTheDocument();
    expect(screen.getByText(/This view does not recompute or verify the chain\./i)).toBeInTheDocument();
    expect(screen.getByText(/CASE_CREATED/)).toBeInTheDocument();

    // Nothing on the journey raised a browser alert: refusals and failures are on the page.
    expect(alertSpy).not.toHaveBeenCalled();
  });
});
