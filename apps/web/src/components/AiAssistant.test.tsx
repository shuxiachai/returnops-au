import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { AiReplyDraftPanel, AiTriagePanel, AiWeeklySummaryPanel } from './AiAssistant';

// The Founder AI assistant (31 October 2026): advisory answers asked for by the Founder.
// FR-002, FR-012; NFR-002, NFR-003, NFR-006; UC-03, UC-05.
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return { ...actual, draftCustomerReply: vi.fn(), triageQueue: vi.fn(), summariseRecentCases: vi.fn() };
});

import { ApiError, draftCustomerReply, summariseRecentCases, triageQueue } from '../api/client';

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
});
