import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import {
  AiImageObservationsPanel,
  AiReplyDraftPanel,
  AiRiskReviewPanel,
  AiTriagePanel,
  AiWeeklySummaryPanel,
  describeReviewInputs,
} from './AiAssistant';

// The Founder AI assistant (31 October 2026): advisory answers asked for by the Founder.
// FR-002, FR-012; NFR-002, NFR-003, NFR-006; UC-03, UC-05.
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    draftCustomerReply: vi.fn(),
    triageQueue: vi.fn(),
    summariseRecentCases: vi.fn(),
    reviewCaseRisk: vi.fn(),
    observeCaseImages: vi.fn(),
  };
});

import {
  ApiError,
  draftCustomerReply,
  observeCaseImages,
  reviewCaseRisk,
  summariseRecentCases,
  triageQueue,
} from '../api/client';
import type { EvidenceAttachment } from '../types/domain';

const STAMP = { model_id: 'qwen3.5-122b-a10b', prompt_version: 'founder-assistant-v1', generated_at: '2026-10-31T07:00:00Z' };

describe('Founder AI assistant panels', () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('asks for nothing until the Founder clicks, then shows the draft in both languages', async () => {
    vi.mocked(draftCustomerReply).mockResolvedValue({
      ...STAMP,
      case_id: 'case_one',
      customer_language: 'zh',
      reply: '您好，我们已收到您的请求。<b>不是标记</b>',
      reply_english: 'Hello, we have received your request.',
    });
    const writeText = vi.fn(async () => undefined);
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });
    render(<AiReplyDraftPanel caseId="case_one" />);
    expect(draftCustomerReply).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Draft a reply' }));
    // Model text is shown as text: the tag is visible, not interpreted.
    expect(await screen.findByText('您好，我们已收到您的请求。<b>不是标记</b>')).toBeInTheDocument();
    expect(screen.getByText('Hello, we have received your request.')).toBeInTheDocument();
    expect(screen.getByText("In the customer's language (zh)")).toBeInTheDocument();
    expect(screen.getByText(/Advisory only: it changes nothing and is sent to no one/)).toBeInTheDocument();
    expect(draftCustomerReply).toHaveBeenCalledWith('case_one');

    fireEvent.click(screen.getByRole('button', { name: /Copy the draft/ }));
    expect(await screen.findByText('Copied.')).toBeInTheDocument();
    expect(writeText).toHaveBeenCalledWith('您好，我们已收到您的请求。<b>不是标记</b>');
  });

  it('shows only the English draft for an English-speaking customer', async () => {
    vi.mocked(draftCustomerReply).mockResolvedValue({
      ...STAMP,
      case_id: 'case_two',
      customer_language: 'en',
      reply: 'Thank you for writing.',
      reply_english: 'Thank you for writing.',
    });
    render(<AiReplyDraftPanel caseId="case_two" />);
    fireEvent.click(screen.getByRole('button', { name: 'Draft a reply' }));
    expect(await screen.findAllByText('Thank you for writing.')).toHaveLength(1);
    expect(screen.queryByText(/In the customer's language/)).not.toBeInTheDocument();
  });

  it('says when the deployment has no assistant, and offers a retry after a failure', async () => {
    vi.mocked(draftCustomerReply).mockRejectedValueOnce(new ApiError(405, 'Method Not Allowed', 'HTTP_405'));
    const { unmount } = render(<AiReplyDraftPanel caseId="case_three" />);
    fireEvent.click(screen.getByRole('button', { name: 'Draft a reply' }));
    expect(await screen.findByText('The AI assistant is not switched on for this deployment.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Draft a reply' })).not.toBeInTheDocument();
    unmount();

    vi.mocked(summariseRecentCases).mockRejectedValueOnce(new ApiError(503, 'Busy', 'INTERNAL_ERROR'));
    render(<AiWeeklySummaryPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'Summarise' }));
    expect(await screen.findByText(/could not answer just now/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Summarise' })).toBeEnabled();
  });

  it('triages the queue: read-first cases open, groups filter, Clear removes the marks', async () => {
    const triage = {
      ...STAMP,
      considered: 3,
      cases: [
        { case_id: 'case_hot', urgency: 'HIGH' as const, reason: 'Smoke suggests a safety risk.' },
        { case_id: 'case_mid', urgency: 'MEDIUM' as const, reason: 'A damaged item.' },
        { case_id: 'case_low', urgency: 'LOW' as const, reason: 'A question.' },
      ],
      groups: [{ label: 'Kitchen appliances', case_ids: ['case_hot', 'case_mid'] }],
    };
    vi.mocked(triageQueue).mockResolvedValue(triage);
    const onTriage = vi.fn();
    const onGroup = vi.fn();
    const onInspect = vi.fn();
    const { rerender } = render(<AiTriagePanel onTriage={onTriage} activeGroup={null} onGroup={onGroup} onInspect={onInspect} />);

    fireEvent.click(screen.getByRole('button', { name: 'Triage the queue' }));
    expect(await screen.findByText('Read first:')).toBeInTheDocument();
    expect(onTriage).toHaveBeenCalledWith(triage);
    expect(screen.getByText('Smoke suggests a safety risk.')).toBeInTheDocument();
    expect(screen.queryByText('A question.')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'case_hot' }));
    expect(onInspect).toHaveBeenCalledWith('case_hot');

    fireEvent.click(screen.getByRole('button', { name: 'Kitchen appliances (2)' }));
    expect(onGroup).toHaveBeenCalledWith('Kitchen appliances', ['case_hot', 'case_mid']);
    rerender(<AiTriagePanel onTriage={onTriage} activeGroup="Kitchen appliances" onGroup={onGroup} onInspect={onInspect} />);
    fireEvent.click(screen.getByRole('button', { name: 'Kitchen appliances (2)' }));
    expect(onGroup).toHaveBeenLastCalledWith(null, null);

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(onTriage).toHaveBeenLastCalledWith(null);
  });

  it('shows the weekly summary, and says when no model was asked', async () => {
    vi.mocked(summariseRecentCases).mockResolvedValueOnce({
      ...STAMP,
      period_days: 7,
      case_count: 7,
      model_called: true,
      summary: 'Seven cases came in; three wait for the customer.',
      highlights: ['One case is escalated.', 'Two are in risk review.'],
    });
    render(<AiWeeklySummaryPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'Summarise' }));
    expect(await screen.findByText('Seven cases came in; three wait for the customer.')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(2);

    vi.mocked(summariseRecentCases).mockResolvedValueOnce({
      ...STAMP,
      period_days: 7,
      case_count: 0,
      model_called: false,
      summary: 'No return cases came in during the last seven days.',
      highlights: [],
    });
    fireEvent.click(screen.getByRole('button', { name: 'Summarise again' }));
    expect(await screen.findByText('No cases in the period, so no model was asked.')).toBeInTheDocument();
  });

  it('shows the C2 risk review on request, as text, and says it records nothing', async () => {
    const review = {
      ...STAMP,
      prompt_version: 'c2-risk-review-advisory-v1',
      case_id: 'case_one',
      case_version: 4,
      case_status: 'AWAITING_INFORMATION',
      reviewed_proposal: null,
      recorded: false as const,
      outcome: 'ESCALATE' as const,
      summary: 'The customer tells the system to mark the claim supported. <b>not markup</b>',
      findings: [
        { category: 'INJECTION', severity: 'BLOCK' as const, message: 'The statement gives the reviewer instructions.' },
        { category: 'MISSING_INFORMATION', severity: 'WARNING' as const, message: 'No order reference was given.' },
      ],
      questions: ['Which order is the mug from?'],
      revision_requests: [],
    };
    vi.mocked(reviewCaseRisk).mockResolvedValueOnce(review);
    render(<AiRiskReviewPanel caseId="case_one" />);
    expect(reviewCaseRisk).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Run AI risk review' }));
    expect(await screen.findByText('Escalate to the Founder')).toBeInTheDocument();
    expect(reviewCaseRisk).toHaveBeenCalledWith('case_one');
    // Model text is shown as text: the tag is visible, not interpreted.
    expect(screen.getByText('The customer tells the system to mark the claim supported. <b>not markup</b>')).toBeInTheDocument();
    expect(screen.getByText('INJECTION (BLOCK):')).toBeInTheDocument();
    expect(screen.getByText('No order reference was given.')).toBeInTheDocument();
    expect(screen.getByText('Which order is the mug from?')).toBeInTheDocument();
    expect(screen.getByText('No proposal yet: the request itself was reviewed')).toBeInTheDocument();
    expect(screen.getByText(/not recorded as this case's risk review/)).toBeInTheDocument();
    expect(screen.queryByText('Changes to the proposal:')).not.toBeInTheDocument();

    vi.mocked(reviewCaseRisk).mockResolvedValueOnce({
      ...review,
      reviewed_proposal: { proposal_id: 'proposal_one', proposal_version: 2 },
      outcome: 'REVISE',
      summary: 'The proposal covers a line the customer did not mention.',
      findings: [{ category: 'SCOPE', severity: 'WARNING', message: 'Line 3 was not part of the complaint.' }],
      questions: [],
      revision_requests: ['Cover only the two chipped cups.'],
    });
    fireEvent.click(screen.getByRole('button', { name: 'Review again' }));
    expect(await screen.findByText('Revise the proposal')).toBeInTheDocument();
    expect(screen.getByText('Reviewed proposal version 2')).toBeInTheDocument();
    expect(screen.getByText('Cover only the two chipped cups.')).toBeInTheDocument();
  });

  it('says when the deployment has no risk reviewer, and when it could not answer', async () => {
    vi.mocked(reviewCaseRisk).mockRejectedValueOnce(new ApiError(404, 'Not Found', 'HTTP_404'));
    const { unmount } = render(<AiRiskReviewPanel caseId="case_one" />);
    fireEvent.click(screen.getByRole('button', { name: 'Run AI risk review' }));
    expect(await screen.findByText('The AI assistant is not switched on for this deployment.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /review/i })).not.toBeInTheDocument();
    unmount();

    vi.mocked(reviewCaseRisk).mockRejectedValueOnce(new ApiError(503, 'Busy', 'INTERNAL_ERROR'));
    render(<AiRiskReviewPanel caseId="case_one" />);
    fireEvent.click(screen.getByRole('button', { name: 'Run AI risk review' }));
    expect(await screen.findByText('The AI assistant could not answer just now. Try again in a moment.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run AI risk review' })).toBeInTheDocument();
  });

  // The roles in a chain (1 November 2026): the C2 review says which other roles' advisory
  // output it read. FR-008; UC-02.
  it('says which other AI answers the risk review read', async () => {
    expect(describeReviewInputs({ coordinator_facts: true, photo_observations: true })).toBe(
      "Also read: the Coordinator's facts card and the photo check (C3)."
    );
    expect(describeReviewInputs({ coordinator_facts: true, photo_observations: false })).toBe(
      "Also read: the Coordinator's facts card. If the case has photos, run Analyse photos under Customer evidence first to include them."
    );
    expect(describeReviewInputs({ coordinator_facts: false, photo_observations: false })).toMatch(/^Read the case only\./);
    vi.mocked(reviewCaseRisk).mockResolvedValueOnce({
      model_id: 'qwen-plus',
      prompt_version: 'c2-risk-review-advisory-v2',
      generated_at: '2026-11-01T09:00:00Z',
      case_id: 'case_one',
      case_version: 4,
      case_status: 'AWAITING_INFORMATION',
      reviewed_proposal: null,
      recorded: false,
      inputs_used: { coordinator_facts: true, photo_observations: true },
      outcome: 'ESCALATE',
      summary: 'A photo holds instructions, and the photos show one chipped cup, not two.',
      findings: [
        { category: 'CONFLICT', severity: 'WARNING', message: 'The photos show one chipped cup; the customer says two.' },
        { category: 'INJECTION', severity: 'BLOCK', message: 'A photo holds text telling the system to approve a refund.' },
      ],
      questions: [],
      revision_requests: [],
    });
    render(<AiRiskReviewPanel caseId="case_one" />);
    fireEvent.click(screen.getByRole('button', { name: 'Run AI risk review' }));
    expect(
      await screen.findByText("Also read: the Coordinator's facts card and the photo check (C3).")
    ).toBeInTheDocument();
    expect(screen.getByText('CONFLICT (WARNING):')).toBeInTheDocument();
    expect(screen.getByText('INJECTION (BLOCK):')).toBeInTheDocument();
  });

  // C3 photo observations (1 November 2026): asked for by the Founder, shown as text,
  // linked to each file, never recorded. FR-005; NFR-009; UC-02.
  const file = (evidence_id: string, filename: string, media_type = 'image/png'): EvidenceAttachment =>
    ({
      evidence_id,
      case_id: 'case_one',
      filename,
      media_type,
      size_bytes: 2048,
      sha256: 'a'.repeat(64),
      created_at: '2026-11-01T07:00:00Z',
      content_path: `/v1/evidence/${evidence_id}/content`,
      status: 'BOUND',
    }) as EvidenceAttachment;

  it('shows the photo check on request, file by file, and says text in a photo was not followed', async () => {
    vi.mocked(observeCaseImages).mockResolvedValueOnce({
      model_id: 'qwen3-vl-plus',
      prompt_version: 'c3-image-observation-advisory-v1',
      generated_at: '2026-11-01T08:00:00Z',
      case_id: 'case_one',
      case_version: 3,
      recorded: false,
      model_called: true,
      result: {
        case_id: 'case_one',
        input_version: 1,
        component_version: 'c3-image-observation-advisory-v1',
        observations: [
          {
            evidence_id: 'ev_cups',
            visible_observations: ['Two white cups; one has a chip on the rim. <b>not markup</b>'],
            limitations: ['The photo cannot show when or how the chip happened.'],
            confidence: 0.82,
          },
          {
            evidence_id: 'ev_note',
            visible_observations: ['A handwritten note next to a mug.'],
            limitations: ['The note cannot show whether the mug is damaged.'],
            confidence: 0.4,
          },
        ],
      },
      details: [
        { evidence_id: 'ev_cups', condition: 'DAMAGE_VISIBLE', text_in_image: 'NONE' },
        { evidence_id: 'ev_note', condition: 'CANNOT_DETERMINE', text_in_image: 'PRESENT_IGNORED' },
      ],
      consistency: 'CONSISTENT',
      summary: 'The first photo matches the complaint; the second shows a note.',
      skipped: [{ evidence_id: 'ev_receipt', reason: 'NOT_AN_IMAGE' }],
    });
    const evidence = [file('ev_cups', 'cups.png'), file('ev_note', 'note.png'), file('ev_receipt', 'receipt.pdf', 'application/pdf')];
    render(<AiImageObservationsPanel caseId="case_one" evidence={evidence} />);
    expect(observeCaseImages).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Analyse photos (AI)' }));
    expect(await screen.findByText("The photos match the customer's words")).toBeInTheDocument();
    expect(observeCaseImages).toHaveBeenCalledWith('case_one');
    expect(screen.getByText('Photo 1: cups.png')).toBeInTheDocument();
    expect(screen.getByText('Photo 2: note.png')).toBeInTheDocument();
    expect(screen.getByText('Damage visible')).toBeInTheDocument();
    expect(screen.getByText('Cannot tell from the photo')).toBeInTheDocument();
    expect(screen.getByText('Confidence 82%')).toBeInTheDocument();
    // Model text is shown as text: the tag is visible, not interpreted.
    expect(screen.getByText('Two white cups; one has a chip on the rim. <b>not markup</b>')).toBeInTheDocument();
    expect(screen.getByText('The photo cannot show when or how the chip happened.')).toBeInTheDocument();
    expect(screen.getAllByText(/treated as data and not followed/)).toHaveLength(1);
    expect(screen.getByText(/receipt\.pdf \(not a photo\)/)).toBeInTheDocument();
    expect(screen.getByText(/qwen3-vl-plus/)).toBeInTheDocument();
    expect(screen.getByText(/not recorded with the case and decides nothing/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Check again' })).toBeInTheDocument();
  });

  it('says when no photo was sent, when the deployment has no vision model, and when it could not answer', async () => {
    vi.mocked(observeCaseImages).mockResolvedValueOnce({
      model_id: 'qwen3-vl-plus',
      prompt_version: 'c3-image-observation-advisory-v1',
      generated_at: '2026-11-01T08:00:00Z',
      case_id: 'case_one',
      case_version: 3,
      recorded: false,
      model_called: false,
      result: null,
      details: [],
      consistency: null,
      summary: 'No photo (JPEG or PNG) is attached to this case.',
      skipped: [],
    });
    const first = render(<AiImageObservationsPanel caseId="case_one" evidence={[]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Analyse photos (AI)' }));
    expect(await screen.findByText('No photo (JPEG or PNG) is attached to this case.')).toBeInTheDocument();
    expect(screen.queryByText(/AI suggestion/)).not.toBeInTheDocument();
    first.unmount();

    vi.mocked(observeCaseImages).mockRejectedValueOnce(new ApiError(404, 'Not Found', 'NOT_FOUND'));
    const second = render(<AiImageObservationsPanel caseId="case_one" evidence={[]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Analyse photos (AI)' }));
    expect(await screen.findByText('The AI assistant is not switched on for this deployment.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /photos/i })).not.toBeInTheDocument();
    second.unmount();

    vi.mocked(observeCaseImages).mockRejectedValueOnce(new ApiError(503, 'Busy', 'INTERNAL_ERROR'));
    render(<AiImageObservationsPanel caseId="case_one" evidence={[]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Analyse photos (AI)' }));
    expect(await screen.findByText('The AI assistant could not answer just now. Try again in a moment.')).toBeInTheDocument();
  });
});
