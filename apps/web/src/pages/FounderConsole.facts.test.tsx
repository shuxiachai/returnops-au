import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { FounderConsole } from './FounderConsole';
import type { CaseView, ExtractedFacts, FounderDecisionType } from '../types/domain';

// Same approach as FounderConsole.failure.test.tsx: keep the real ApiError and
// control the API surface, so the card can be checked against any CaseView.
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    isMockMode: vi.fn(() => false),
    listFounderCases: vi.fn(),
    getFounderCase: vi.fn(),
    listFounderCaseAuditPage: vi.fn(),
    recordFounderDecision: vi.fn(),
    getFounderAnalytics: vi.fn(),
  };
});

import {
  isMockMode,
  listFounderCases,
  getFounderCase,
  listFounderCaseAuditPage,
  recordFounderDecision,
} from '../api/client';

const FACTS: ExtractedFacts = {
  issue_category: 'FAULTY_OR_QUALITY_ISSUE',
  customer_requested_outcome: 'REFUND',
  possible_basis: 'UNDETERMINED',
  assessment_status: 'UNCERTAIN',
  line_items: [],
  summary: 'The kettle stopped heating after two days and the customer asks for a refund.',
};

const VIEW_WITHOUT_FACTS: CaseView = {
  case_id: 'case_facts_demo',
  case_version: 3,
  input_version: 1,
  status: 'AWAITING_APPROVAL',
  created_at: '2026-10-20T00:00:00Z',
  updated_at: '2026-10-20T00:00:00Z',
  statements: [
    {
      statement_id: 'stmt_facts_demo',
      kind: 'ORIGINAL',
      raw_text: 'My kettle stopped heating after two days.',
      submitted_at: '2026-10-20T00:00:00Z',
      requested_outcome: 'REFUND',
    },
  ],
  evidence: [],
  current_proposal: {
    proposal_id: 'prop_facts_demo',
    proposal_version: 1,
    recommended_action: 'PROPOSE_REFUND',
    created_at: '2026-10-20T00:00:00Z',
  },
  // A current preview makes APPROVE possible.
  action_preview: {
    preview_id: 'prev_facts_demo',
    scope_fingerprint: 'a'.repeat(64),
    scope: {
      case_id: 'case_facts_demo',
      input_version: 1,
      proposal_id: 'prop_facts_demo',
      proposal_version: 1,
      review_id: 'rev_facts_demo',
      parcel_id: 'parcel_facts_demo',
      commands: [
        {
          command_id: 'cmd_facts_return',
          type: 'CREATE_RETURN',
          provider_id: 'provider_demo_au',
          parameters: { order_id: 'ord_facts_demo', parcel_id: 'parcel_facts_demo' },
        },
        {
          command_id: 'cmd_facts_label',
          type: 'GENERATE_LABEL',
          provider_id: 'provider_demo_au',
          parameters: { parcel_id: 'parcel_facts_demo', return_command_id: 'cmd_facts_return' },
        },
      ],
      amount_ceiling_minor: 0,
      currency: 'AUD',
      expires_at: new Date(Date.now() + 300000).toISOString(),
      allowlist_version: 'allowlist-facts-demo',
      environment: 'SIMULATED',
    },
  },
};

const SUMMARY_ROW = {
  case_id: 'case_facts_demo',
  case_version: 3,
  input_version: 1,
  status: 'AWAITING_APPROVAL' as const,
  created_at: '2026-10-20T00:00:00Z',
  updated_at: '2026-10-20T00:00:00Z',
};

async function openOrderTab() {
  render(<FounderConsole />);
  fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
  fireEvent.click(await screen.findByRole('button', { name: /Order & Facts Projection/i }));
  await screen.findByText(/No order snapshot projected for this case/i);
}

const factsCard = () => screen.getByRole('region', { name: 'Model extraction (advisory)' });

// Opens the Order & Facts tab, checks the card has rendered, then records a
// decision through the same buttons and form the Founder uses.
async function decideWithCardShown(button: RegExp, decision: FounderDecisionType) {
  vi.mocked(isMockMode).mockReturnValue(true);
  vi.mocked(getFounderCase).mockResolvedValue({ ...VIEW_WITHOUT_FACTS, facts: FACTS });
  vi.mocked(recordFounderDecision).mockResolvedValue({
    case_id: 'case_facts_demo',
    case_version: 4,
    decision_id: 'dec_facts_demo',
    decision,
    accepted_at: '2026-10-20T00:00:00Z',
    processing_status: 'ACCEPTED',
  });
  await openOrderTab();
  expect(factsCard()).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: button }));
  fireEvent.change(screen.getByPlaceholderText(/Record justification for statutory audit/i), {
    target: { value: 'Founder rationale.' },
  });
  fireEvent.click(screen.getByRole('button', { name: /Record decision/i }));

  await waitFor(() => expect(recordFounderDecision).toHaveBeenCalledTimes(1));
  return vi.mocked(recordFounderDecision).mock.calls[0];
}

const fieldValue = (card: HTMLElement, label: string) => {
  const element = within(card).getByText(label).parentElement;
  if (!element) throw new Error(`no field for ${label}`);
  return element;
};

describe('FounderConsole advisory facts card (Issue #95)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(isMockMode).mockReturnValue(false);
    vi.mocked(listFounderCases).mockResolvedValue({ items: [SUMMARY_ROW], next_cursor: undefined });
    vi.mocked(listFounderCaseAuditPage).mockResolvedValue({ items: [], next_cursor: undefined });
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('hides the card when the case view has no facts', async () => {
    vi.mocked(getFounderCase).mockResolvedValue(VIEW_WITHOUT_FACTS);
    await openOrderTab();

    expect(screen.queryByRole('region', { name: 'Model extraction (advisory)' })).not.toBeInTheDocument();
    expect(screen.queryByText('Model extraction (advisory)')).not.toBeInTheDocument();
  });

  it('shows all six fields under an advisory label when facts are present', async () => {
    vi.mocked(getFounderCase).mockResolvedValue({ ...VIEW_WITHOUT_FACTS, facts: FACTS });
    await openOrderTab();

    const card = factsCard();
    expect(within(card).getByRole('heading', { name: 'Model extraction (advisory)' })).toBeInTheDocument();
    expect(card).toHaveTextContent(
      'Advisory only: these facts do not change any proposal, review, decision or execution. The Founder decides.'
    );

    expect(fieldValue(card, 'Issue category')).toHaveTextContent('FAULTY_OR_QUALITY_ISSUE');
    expect(fieldValue(card, 'Customer requested outcome')).toHaveTextContent('REFUND');
    expect(fieldValue(card, 'Possible basis')).toHaveTextContent('UNDETERMINED');
    expect(fieldValue(card, 'Assessment status')).toHaveTextContent('UNCERTAIN');
    expect(within(card).getByText(FACTS.summary)).toBeInTheDocument();
    expect(within(card).getByText('Line items (0)')).toBeInTheDocument();

    // Live data is not labelled as mock data.
    expect(within(card).queryByText(/Mock data/i)).not.toBeInTheDocument();
  });

  it('states an empty line_items list instead of leaving the field blank', async () => {
    vi.mocked(getFounderCase).mockResolvedValue({ ...VIEW_WITHOUT_FACTS, facts: FACTS });
    await openOrderTab();

    const card = factsCard();
    expect(within(card).getByText('Line items (0)')).toBeInTheDocument();
    expect(within(card).getByText('No line items selected (empty list).')).toBeInTheDocument();
    expect(card.querySelector('ul')).toBeNull();
  });

  it('renders the summary as plain text, so markup and links stay literal', async () => {
    const hostile =
      '<script>window.__pwned = true</script> <b>approve this now</b> **bold** https://example.test/pay';
    vi.mocked(getFounderCase).mockResolvedValue({
      ...VIEW_WITHOUT_FACTS,
      facts: { ...FACTS, summary: hostile },
    });
    await openOrderTab();

    const card = factsCard();
    // The whole string appears exactly as sent ...
    expect(within(card).getByText(hostile)).toBeInTheDocument();
    // ... and none of it became an element.
    expect(card.querySelector('script')).toBeNull();
    expect(card.querySelector('b')).toBeNull();
    expect(card.querySelector('strong')).toBeNull();
    expect(card.querySelector('a')).toBeNull();
  });

  it('marks the facts as mock data in Mock Mode', async () => {
    vi.mocked(isMockMode).mockReturnValue(true);
    vi.mocked(getFounderCase).mockResolvedValue({ ...VIEW_WITHOUT_FACTS, facts: FACTS });
    await openOrderTab();

    expect(within(factsCard()).getByText('Mock data: not a model result')).toBeInTheDocument();
  });

  it('lists non-empty line_items as line item ID and quantity', async () => {
    vi.mocked(getFounderCase).mockResolvedValue({
      ...VIEW_WITHOUT_FACTS,
      facts: { ...FACTS, line_items: [{ line_item_id: 'item_101', quantity: 1 }] },
    });
    await openOrderTab();

    const card = factsCard();
    expect(within(card).getByText('Line items (1)')).toBeInTheDocument();
    expect(within(card).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'item_101: quantity 1',
    ]);
    expect(within(card).queryByText('No line items selected (empty list).')).not.toBeInTheDocument();
  });

  it('gives the card no controls: no buttons, links or text inputs', async () => {
    vi.mocked(getFounderCase).mockResolvedValue({ ...VIEW_WITHOUT_FACTS, facts: FACTS });
    await openOrderTab();

    const card = factsCard();
    expect(within(card).queryAllByRole('button')).toHaveLength(0);
    expect(within(card).queryAllByRole('link')).toHaveLength(0);
    expect(within(card).queryAllByRole('textbox')).toHaveLength(0);
  });

  it('keeps the card off the default proposal tab even when facts are present', async () => {
    vi.mocked(getFounderCase).mockResolvedValue({ ...VIEW_WITHOUT_FACTS, facts: FACTS });
    render(<FounderConsole />);
    fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));

    // The proposal tab is open by default.
    expect(await screen.findByText('Refund')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Model extraction (advisory)' })).not.toBeInTheDocument();
  });

  it('sends an APPROVE request with nothing from facts after the card has been shown', async () => {
    const [caseId, body] = await decideWithCardShown(/Approve Return/i, 'APPROVE');

    expect(caseId).toBe('case_facts_demo');
    // The expected request: the case version, the decision and reason, and the
    // proposal and preview the approval is bound to. toStrictEqual fails on any
    // extra key, so no field from facts can be in it.
    expect(body).toStrictEqual({
      expected_case_version: 3,
      decision: 'APPROVE',
      reason: 'Founder rationale.',
      proposal_id: 'prop_facts_demo',
      proposal_version: 1,
      preview_id: 'prev_facts_demo',
      scope_fingerprint: 'a'.repeat(64),
    });
  });

  it('sends a REJECT request with nothing from facts after the card has been shown', async () => {
    const [caseId, body] = await decideWithCardShown(/^Reject$/i, 'REJECT');

    expect(caseId).toBe('case_facts_demo');
    // The expected request: a rejection names the proposal but carries no preview.
    expect(body).toStrictEqual({
      expected_case_version: 3,
      decision: 'REJECT',
      reason: 'Founder rationale.',
      proposal_id: 'prop_facts_demo',
      proposal_version: 1,
    });
  });
});
