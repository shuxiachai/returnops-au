import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

// #122 item 5: the panels a Founder needs before deciding, and the evidence download.
// The client is mocked at the boundary; nothing here touches the fixture store.
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    isMockMode: vi.fn(() => true),
    listFounderCases: vi.fn(),
    getFounderCase: vi.fn(),
    listFounderCaseAuditPage: vi.fn(),
    recordFounderDecision: vi.fn(),
    getFounderAnalytics: vi.fn(),
    downloadEvidence: vi.fn(),
  };
});

import {
  ApiError,
  downloadEvidence,
  getFounderCase,
  listFounderCaseAuditPage,
  listFounderCases,
} from '../api/client';
import { FounderConsole } from './FounderConsole';
import type { CaseView } from '../types/domain';

const HASH = 'a'.repeat(64);

const SUMMARY = {
  case_id: 'case_contract_05',
  case_version: 1,
  input_version: 1,
  status: 'AWAITING_APPROVAL' as const,
  created_at: '2026-10-20T00:00:00Z',
  updated_at: '2026-10-20T00:00:00Z',
  issue_category: 'CHANGE_OF_MIND' as const,
};

const VIEW: CaseView = {
  case_id: 'case_contract_05',
  case_version: 1,
  input_version: 1,
  status: 'AWAITING_APPROVAL',
  created_at: '2026-10-20T00:00:00Z',
  updated_at: '2026-10-20T00:00:00Z',
  statements: [
    {
      statement_id: 'stmt_1',
      kind: 'ORIGINAL',
      raw_text: 'The sheets arrived opened.',
      submitted_at: '2026-10-20T00:00:00Z',
    },
  ],
  evidence: [
    {
      evidence_id: 'ev_contract_1',
      filename: 'parcel_photo.jpg',
      media_type: 'image/jpeg',
      size_bytes: 2048,
      sha256: HASH,
      status: 'BOUND',
      created_at: '2026-10-20T00:00:00Z',
      content_path: '/v1/evidence/ev_contract_1/content',
    },
  ],
  current_proposal: {
    proposal_id: 'prop_contract_1',
    proposal_version: 1,
    created_at: '2026-10-20T00:00:00Z',
    rationale: 'Policy applies if the item is unopened.',
    conditions: ['The item is unopened and in its original packaging.'],
    unresolved_questions: ['No photograph of the sealed packaging was attached.'],
    citations: [
      {
        citation_id: 'cite_1',
        passage_id: 'passage_1',
        document_id: 'doc_1',
        source_version: '2026.1',
        corpus_version: 'demo-corpus-v1',
        content_sha256: HASH,
        location: 'Store Policy §2.1',
      },
    ],
  },
  cited_passages: [
    {
      passage_id: 'passage_1',
      document_id: 'doc_1',
      source_type: 'STORE_POLICY',
      title: 'Store policy §2.1',
      source_uri: 'urn:returnops:demo-store/policy#2.1',
      accessed_on: '2026-10-20',
      source_version: '2026.1',
      corpus_version: 'demo-corpus-v1',
      location: 'Store Policy §2.1',
      content: 'A customer may return an unused item within 30 days.',
      content_sha256: HASH,
      retrieved_at: '2026-10-20T00:00:00Z',
      is_synthetic: true,
    },
  ],
  current_review: {
    review_id: 'rev_contract_1',
    outcome: 'PASS_WITH_WARNING',
    reviewed_at: '2026-10-20T00:00:00Z',
    findings: [],
    revision_requests: ['Ask the customer for a photograph of the seal.'],
    questions: [{ question_id: 'q_1', text: 'Was the parcel opened before delivery?', reason: 'Scope.' }],
  },
};


// An approval preview that expired while the dialog was open. The server never sends
// one on a fresh read (lifecycle_projection.py:62), so this is the held-open dialog.
const EXPIRED_VIEW: CaseView = {
  ...VIEW,
  action_preview: {
    preview_id: 'prev_expired',
    scope_fingerprint: HASH,
    scope: {
      case_id: 'case_contract_05',
      input_version: 1,
      proposal_id: 'prop_contract_1',
      proposal_version: 1,
      review_id: 'rev_contract_1',
      parcel_id: 'parcel_1',
      commands: [],
      currency: 'AUD',
      amount_ceiling_minor: 0,
      expires_at: '2026-10-01T00:00:00Z',
      allowlist_version: 'allowlist-v1',
      environment: 'SIMULATED',
    },
  },
};

async function openCase() {
  render(<FounderConsole />);
  await waitFor(() => expect(screen.getByText('case_contract_05')).toBeInTheDocument());
  fireEvent.change(screen.getByPlaceholderText(/Filter by Case ID or Category/i), {
    target: { value: 'case_contract_05' },
  });
  fireEvent.click(await screen.findByRole('button', { name: /Inspect/i }));
  await screen.findByText('Assessment Proposal');
}

describe('what the Founder sees before deciding (#122 item 5)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(listFounderCases).mockResolvedValue({ items: [SUMMARY], next_cursor: undefined });
    vi.mocked(getFounderCase).mockResolvedValue(VIEW);
    vi.mocked(listFounderCaseAuditPage).mockResolvedValue({ items: [], next_cursor: undefined });
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('shows the conditions, the unresolved questions and the citations behind the proposal', async () => {
    await openCase();

    expect(screen.getByText('Conditions (1)')).toBeInTheDocument();
    expect(screen.getByText('The item is unopened and in its original packaging.')).toBeInTheDocument();
    expect(screen.getByText('Unresolved questions (1)')).toBeInTheDocument();
    expect(screen.getByText('No photograph of the sealed packaging was attached.')).toBeInTheDocument();
    // The contract's citation, resolved against the case view's passage.
    expect(screen.getByText('Citations (1)')).toBeInTheDocument();
    expect(screen.getByText('Store policy §2.1')).toBeInTheDocument();
    expect(screen.getByText('A customer may return an unused item within 30 days.')).toBeInTheDocument();
    expect(screen.getByText(/synthetic corpus/)).toBeInTheDocument();
  });

  it('shows the review revision requests and reviewer questions, which used to be hidden', async () => {
    await openCase();

    expect(screen.getByText('Revision requests (1)')).toBeInTheDocument();
    expect(screen.getByText('Ask the customer for a photograph of the seal.')).toBeInTheDocument();
    expect(screen.getByText('Reviewer questions (1)')).toBeInTheDocument();
    expect(screen.getByText('Was the parcel opened before delivery?')).toBeInTheDocument();
  });

  it('lists the customer evidence and downloads the file the Founder picked', async () => {
    await openCase();
    fireEvent.click(screen.getByRole('button', { name: /Customer Statements/i }));

    expect(await screen.findByText('Customer evidence (1)')).toBeInTheDocument();
    expect(screen.getByText('parcel_photo.jpg')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Download parcel_photo\.jpg/i }));

    await waitFor(() =>
      expect(downloadEvidence).toHaveBeenCalledWith('ev_contract_1', 'parcel_photo.jpg')
    );
  });

  it('reports a refused download on the page with the server code', async () => {
    vi.mocked(downloadEvidence).mockRejectedValueOnce(
      new ApiError(403, 'not your evidence', 'FORBIDDEN')
    );
    await openCase();
    fireEvent.click(screen.getByRole('button', { name: /Customer Statements/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Download parcel_photo\.jpg/i }));

    expect(await screen.findByText(/\[FORBIDDEN\] not your evidence/)).toBeInTheDocument();
  });
});

describe('a preview that expired while the dialog is open (review round 2, finding 1)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(listFounderCases).mockResolvedValue({ items: [SUMMARY], next_cursor: undefined });
    vi.mocked(getFounderCase).mockResolvedValue(EXPIRED_VIEW);
    vi.mocked(listFounderCaseAuditPage).mockResolvedValue({ items: [], next_cursor: undefined });
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('refuses APPROVE while the decisions that need no preview still work', async () => {
    await openCase();

    // An expired preview never opens the APPROVE dialog (selectDecisionTarget refuses it).
    // The case window is itself a dialog, so the confirmation is found by its name.
    fireEvent.click(screen.getByRole('button', { name: /Approve Return/i }));
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Confirm Founder Decision/i })).not.toBeInTheDocument()
    );

    // Reject does not depend on a preview, so the same case still allows it.
    fireEvent.click(screen.getByRole('button', { name: /^Reject$/i }));
    const rejectDialog = await screen.findByRole('dialog', { name: /Confirm Founder Decision: REJECT/i });
    fireEvent.change(screen.getByPlaceholderText(/Record justification for statutory audit/i), {
      target: { value: 'Rejected after looking at the case.' },
    });
    expect(rejectDialog).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Record decision/i })).toBeEnabled();
  });
});
