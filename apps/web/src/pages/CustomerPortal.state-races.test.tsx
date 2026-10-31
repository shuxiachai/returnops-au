import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { CustomerPortal } from './CustomerPortal';
import type { CustomerCaseView, StagedEvidence } from '../types/domain';

// FR-001/002/005, NFR-004/006; UC-01/01E, Member B IntakeSession models.
// These boundary mocks observe UI intent; they do not simulate backend authority.
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

const caseAId = 'case_demo_001';
const caseBId = 'case_demo_002';
const originalText = 'Original customer statement retained without replacement.';

function caseView(caseId: string, version = 2, questionSetId = `qset_${caseId}`): CustomerCaseView {
  return {
    case_id: caseId,
    case_version: version,
    input_version: 1,
    status: 'AWAITING_INFORMATION',
    created_at: '2026-10-17T00:00:00Z',
    updated_at: '2026-10-17T00:00:00Z',
    statements: [{
      statement_id: `stmt_${caseId}`,
      kind: 'ORIGINAL',
      raw_text: originalText,
      submitted_at: '2026-10-17T00:00:00Z',
    }],
    evidence: [],
    clarification: {
      question_set_id: questionSetId,
      input_version: 1,
      questions: [
        { question_id: 'q_barcode', text: 'What barcode is on the garment?' },
        { question_id: 'q_parcel', text: 'Was the parcel damaged?' },
      ],
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
    created_at: '2026-10-17T00:00:00Z',
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

async function resolveDeferred<T>(pending: ReturnType<typeof deferred<T>>, value: T) {
  await act(async () => {
    pending.resolve(value);
    await pending.promise;
  });
}

async function rejectDeferred<T>(pending: ReturnType<typeof deferred<T>>, failure: string | Error) {
  await act(async () => {
    pending.reject(typeof failure === 'string' ? new Error(failure) : failure);
    await pending.promise.catch(() => undefined);
  });
}

function attachFile(name: string) {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  expect(input).not.toBeNull();
  fireEvent.change(input!, { target: { files: [new File(['image bytes'], name, { type: 'image/png' })] } });
}

function fileRow(name: string) {
  const remove = screen.getByRole('button', { name: `Remove ${name}` });
  return within(remove.parentElement!.parentElement!);
}

function stageFile(name: string) {
  fireEvent.click(fileRow(name).getByRole('button', { name: /^Stage File$/i }));
}

// The badge reads "Staged"; on the lodge form it carries the staged evidence ID (#111 item 6).
function stagedBadge(mode: 'lodge' | 'clarify', name: string) {
  const badge = fileRow(name).getByText('Staged', { exact: true });
  if (mode === 'lodge') expect(badge).toHaveAttribute('data-evidence-id', staged(name).evidence_id);
  return badge;
}

function submitButton(mode: 'lodge' | 'clarify') {
  return screen.getByRole('button', {
    name: mode === 'lodge' ? /Submit Return Request/i : /Submit Answers/i,
  });
}

function answerAll(text = 'Same supplementary answer') {
  screen.getAllByPlaceholderText('Your answer...').forEach(input =>
    fireEvent.change(input, { target: { value: text } })
  );
}

async function openPortal(mode: 'lodge' | 'clarify') {
  render(<CustomerPortal />);
  if (mode === 'clarify') {
    fireEvent.click(screen.getByRole('button', { name: /Track & Clarify/i }));
    await screen.findByText(caseAId, { exact: true });
    answerAll();
  } else {
    fireEvent.change(screen.getByPlaceholderText(/Tell us what happened with your purchase/i), {
      target: { value: originalText },
    });
  }
}

async function lookup(caseId: string) {
  fireEvent.change(screen.getByLabelText(/case ID/i), { target: { value: caseId } });
  fireEvent.click(screen.getByRole('button', { name: /^Lookup$/ }));
  await screen.findByText(caseId, { exact: true });
  await waitFor(() => expect(screen.getByRole('button', { name: /^Lookup$/ })).toBeEnabled());
}

async function submitAndObserve(mode: 'lodge' | 'clarify', count = 1) {
  fireEvent.click(submitButton(mode));
  const boundary = mode === 'lodge' ? vi.mocked(createCase) : vi.mocked(submitClarification);
  await waitFor(() => expect(boundary).toHaveBeenCalledTimes(count));
  await screen.findByText(/\[NETWORK_ERROR\] response lost/i);
}

function submittedEvidence(mode: 'lodge' | 'clarify') {
  return mode === 'lodge'
    ? vi.mocked(createCase).mock.calls[0][0].evidence_ids
    : vi.mocked(submitClarification).mock.calls[0][1].evidence_ids;
}

beforeEach(() => {
  localStorage.clear();
  vi.resetAllMocks();
  vi.spyOn(window, 'alert').mockImplementation(() => undefined);
  vi.mocked(getCustomerCase).mockImplementation(async id => caseView(id));
  vi.mocked(stageEvidence).mockImplementation(async file => staged(file.name));
  // Unknown response retains form intent for meaningful retry assertions.
  vi.mocked(createCase).mockRejectedValue(new ApiError(0, 'response lost', 'NETWORK_ERROR'));
  vi.mocked(submitClarification).mockRejectedValue(new ApiError(0, 'response lost', 'NETWORK_ERROR'));
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe.each(['lodge', 'clarify'] as const)('%s upload selection identity', mode => {
  it('ignores a removed upload that resolves after a replacement file was selected', async () => {
    const pending = deferred<StagedEvidence>();
    vi.mocked(stageEvidence).mockReturnValueOnce(pending.promise);
    await openPortal(mode);
    attachFile('removed.png');
    stageFile('removed.png');
    fireEvent.click(screen.getByRole('button', { name: 'Remove removed.png' }));
    attachFile('retained.png');

    await resolveDeferred(pending, staged('removed.png'));

    expect(screen.queryByText('removed.png', { exact: true })).not.toBeInTheDocument();
    expect(screen.getByText('retained.png', { exact: true })).toBeInTheDocument();
    expect(submitButton(mode)).toBeDisabled();
    stageFile('retained.png');
    await waitFor(() => expect(stagedBadge(mode, 'retained.png')).toBeInTheDocument());
    await submitAndObserve(mode);
    expect(submittedEvidence(mode)).toEqual([staged('retained.png').evidence_id]);
  });

  it('preserves later selections and both evidence IDs when uploads finish in reverse order', async () => {
    const first = deferred<StagedEvidence>();
    const second = deferred<StagedEvidence>();
    vi.mocked(stageEvidence).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    await openPortal(mode);
    attachFile('first.png');
    stageFile('first.png');
    attachFile('second.png');
    stageFile('second.png');

    await resolveDeferred(second, staged('second.png'));
    expect(stagedBadge(mode, 'second.png')).toBeInTheDocument();
    expect(submitButton(mode)).toBeDisabled();
    await resolveDeferred(first, staged('first.png'));

    expect(stagedBadge(mode, 'first.png')).toBeInTheDocument();
    expect(stagedBadge(mode, 'second.png')).toBeInTheDocument();
    await submitAndObserve(mode);
    expect(submittedEvidence(mode)).toEqual([staged('first.png').evidence_id, staged('second.png').evidence_id]);
  });

  it('ignores errors from removed uploads without restoring rows or showing stale alerts', async () => {
    const pending = deferred<StagedEvidence>();
    vi.mocked(stageEvidence).mockReturnValueOnce(pending.promise);
    await openPortal(mode);
    attachFile('removed.png');
    stageFile('removed.png');
    fireEvent.click(screen.getByRole('button', { name: 'Remove removed.png' }));
    attachFile('retained.png');

    await rejectDeferred(pending, 'Obsolete upload failure');

    expect(window.alert).not.toHaveBeenCalled();
    expect(screen.queryByText('removed.png', { exact: true })).not.toBeInTheDocument();
    expect(fileRow('retained.png').getByRole('button', { name: /^Stage File$/i })).toBeEnabled();
  });

  it('reuses a selected file key after its failed upload is retried', async () => {
    vi.mocked(stageEvidence).mockRejectedValueOnce(new Error('Upload response lost'));
    await openPortal(mode);
    attachFile('retry.png');
    stageFile('retry.png');
    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('Upload response lost'));
    stageFile('retry.png');
    await waitFor(() => expect(stagedBadge(mode, 'retry.png')).toBeInTheDocument());

    const calls = vi.mocked(stageEvidence).mock.calls;
    expect(calls).toHaveLength(2);
    expect(calls[0][2]).toBeTruthy();
    expect(calls[1][2]).toBe(calls[0][2]);
    expect(calls[1][0]).toBe(calls[0][0]);
  });
});

describe('clarification draft scope and pending callbacks', () => {
  it('drops staged case A evidence and answers before submitting case B', async () => {
    await openPortal('clarify');
    attachFile('case-a.png');
    stageFile('case-a.png');
    await screen.findByText('Staged');
    await lookup(caseBId);

    expect(screen.queryByText('case-a.png', { exact: true })).not.toBeInTheDocument();
    screen.getAllByPlaceholderText('Your answer...').forEach(input => expect(input).toHaveValue(''));
    answerAll('Case B answer');
    await submitAndObserve('clarify');
    expect(vi.mocked(submitClarification).mock.calls[0]).toEqual([
      caseBId,
      {
        expected_case_version: 2,
        question_set_id: `qset_${caseBId}`,
        answers: [{ question_id: 'q_barcode', text: 'Case B answer' }, { question_id: 'q_parcel', text: 'Case B answer' }],
        evidence_ids: [],
      },
      expect.any(String),
    ]);
    expect(screen.getByText(originalText, { exact: true })).toBeInTheDocument();
  });

  it.each(['resolve', 'reject'] as const)('ignores a late case A upload %s after switching to B', async outcome => {
    const pending = deferred<StagedEvidence>();
    vi.mocked(stageEvidence).mockReturnValueOnce(pending.promise);
    await openPortal('clarify');
    attachFile('case-a.png');
    stageFile('case-a.png');
    await lookup(caseBId);
    attachFile('case-b.png');
    if (outcome === 'resolve') await resolveDeferred(pending, staged('case-a.png'));
    else await rejectDeferred(pending, 'Obsolete case A upload');

    expect(window.alert).not.toHaveBeenCalled();
    expect(screen.queryByText('case-a.png', { exact: true })).not.toBeInTheDocument();
    expect(fileRow('case-b.png').getByRole('button', { name: /^Stage File$/i })).toBeEnabled();
    stageFile('case-b.png');
    await screen.findByText('Staged');
    answerAll('B response');
    await submitAndObserve('clarify');
    expect(vi.mocked(submitClarification).mock.calls[0][0]).toBe(caseBId);
    expect(submittedEvidence('clarify')).toEqual([staged('case-b.png').evidence_id]);
  });

  it('preserves the exact payload and retry key after refreshing an unchanged case scope', async () => {
    await openPortal('clarify');
    attachFile('retry.png');
    stageFile('retry.png');
    await screen.findByText('Staged');
    await submitAndObserve('clarify');
    const first = vi.mocked(submitClarification).mock.calls[0];

    await lookup(caseAId);
    screen.getAllByPlaceholderText('Your answer...').forEach(input => expect(input).toHaveValue('Same supplementary answer'));
    expect(fileRow('retry.png').getByText('Staged')).toBeInTheDocument();
    await submitAndObserve('clarify', 2);
    expect(vi.mocked(submitClarification).mock.calls[1]).toEqual(first);
  });

  it('does not revive the old retry key after leaving A and returning with the same answers', async () => {
    await openPortal('clarify');
    await submitAndObserve('clarify');
    const first = vi.mocked(submitClarification).mock.calls[0];
    await lookup(caseBId);
    await lookup(caseAId);
    answerAll();
    await submitAndObserve('clarify', 2);
    const second = vi.mocked(submitClarification).mock.calls[1];
    expect(second[0]).toBe(first[0]);
    expect(second[1]).toEqual(first[1]);
    expect(second[2]).not.toBe(first[2]);
  });

  it('preserves an uncertain POST payload and key across a failed refresh and same-scope recovery', async () => {
    const refresh = deferred<CustomerCaseView>();
    await openPortal('clarify');
    attachFile('retry-after-read.png');
    stageFile('retry-after-read.png');
    await screen.findByText('Staged');
    await submitAndObserve('clarify');
    const first = vi.mocked(submitClarification).mock.calls[0];
    vi.mocked(getCustomerCase).mockReturnValueOnce(refresh.promise);
    fireEvent.click(screen.getByRole('button', { name: /^Lookup$/ }));
    await waitFor(() => expect(getCustomerCase).toHaveBeenCalledTimes(2));
    await rejectDeferred(refresh, new ApiError(0, 'Read response lost', 'NETWORK_ERROR'));

    expect(screen.getByText('NETWORK_ERROR: Read response lost')).toBeInTheDocument();
    expect(screen.queryByText(caseAId, { exact: true })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Submit Answers/i })).not.toBeInTheDocument();
    await lookup(caseAId);

    screen.getAllByPlaceholderText('Your answer...').forEach(input => expect(input).toHaveValue('Same supplementary answer'));
    expect(fileRow('retry-after-read.png').getByText('Staged', { exact: true })).toBeInTheDocument();
    await submitAndObserve('clarify', 2);
    expect(vi.mocked(submitClarification).mock.calls[1]).toEqual(first);
  });

  it('discards the preserved draft when failed-read recovery confirms a changed scope', async () => {
    const refresh = deferred<CustomerCaseView>();
    await openPortal('clarify');
    attachFile('obsolete-after-read.png');
    stageFile('obsolete-after-read.png');
    await screen.findByText('Staged');
    await submitAndObserve('clarify');
    const firstKey = vi.mocked(submitClarification).mock.calls[0][2];
    vi.mocked(getCustomerCase).mockReturnValueOnce(refresh.promise);
    fireEvent.click(screen.getByRole('button', { name: /^Lookup$/ }));
    await waitFor(() => expect(getCustomerCase).toHaveBeenCalledTimes(2));
    await rejectDeferred(refresh, new ApiError(503, 'Temporarily unavailable', 'UNAVAILABLE'));
    expect(screen.queryByPlaceholderText('Your answer...')).not.toBeInTheDocument();
    vi.mocked(getCustomerCase).mockResolvedValueOnce(caseView(caseAId, 3, 'qset_recovered'));
    await lookup(caseAId);

    screen.getAllByPlaceholderText('Your answer...').forEach(input => expect(input).toHaveValue(''));
    expect(screen.queryByText('obsolete-after-read.png', { exact: true })).not.toBeInTheDocument();
    answerAll('Recovered scope answer');
    await submitAndObserve('clarify', 2);
    const second = vi.mocked(submitClarification).mock.calls[1];
    expect(second[1]).toEqual({
      expected_case_version: 3,
      question_set_id: 'qset_recovered',
      answers: [{ question_id: 'q_barcode', text: 'Recovered scope answer' }, { question_id: 'q_parcel', text: 'Recovered scope answer' }],
      evidence_ids: [],
    });
    expect(second[2]).not.toBe(firstKey);
  });

  it.each([401, 403, 404])('clears the draft and retry key after an explicit HTTP %i read failure', async status => {
    const refresh = deferred<CustomerCaseView>();
    await openPortal('clarify');
    attachFile('unavailable.png');
    stageFile('unavailable.png');
    await screen.findByText('Staged');
    await submitAndObserve('clarify');
    const firstKey = vi.mocked(submitClarification).mock.calls[0][2];
    vi.mocked(getCustomerCase).mockReturnValueOnce(refresh.promise);
    fireEvent.click(screen.getByRole('button', { name: /^Lookup$/ }));
    await waitFor(() => expect(getCustomerCase).toHaveBeenCalledTimes(2));
    await rejectDeferred(refresh, new ApiError(status, 'Case unavailable', `HTTP_${status}`));
    expect(screen.queryByPlaceholderText('Your answer...')).not.toBeInTheDocument();
    await lookup(caseAId);

    screen.getAllByPlaceholderText('Your answer...').forEach(input => expect(input).toHaveValue(''));
    expect(screen.queryByText('unavailable.png', { exact: true })).not.toBeInTheDocument();
    answerAll();
    await submitAndObserve('clarify', 2);
    const second = vi.mocked(submitClarification).mock.calls[1];
    expect(second[1].evidence_ids).toEqual([]);
    expect(second[2]).not.toBe(firstKey);
  });

  it.each(['version', 'question-set'] as const)('resets the draft when the same case has a changed %s', async change => {
    await openPortal('clarify');
    attachFile('old-scope.png');
    stageFile('old-scope.png');
    await screen.findByText('Staged');
    await submitAndObserve('clarify');
    const firstKey = vi.mocked(submitClarification).mock.calls[0][2];
    const next = caseView(caseAId, change === 'version' ? 3 : 2, change === 'question-set' ? 'qset_new' : `qset_${caseAId}`);
    vi.mocked(getCustomerCase).mockResolvedValueOnce(next);

    await lookup(caseAId);

    expect(screen.queryByText('old-scope.png', { exact: true })).not.toBeInTheDocument();
    screen.getAllByPlaceholderText('Your answer...').forEach(input => expect(input).toHaveValue(''));
    answerAll('Current scope answer');
    await submitAndObserve('clarify', 2);
    const latest = vi.mocked(submitClarification).mock.calls[1];
    expect(latest[1].expected_case_version).toBe(next.case_version);
    expect(latest[1].question_set_id).toBe(next.clarification!.question_set_id);
    expect(latest[1].evidence_ids).toEqual([]);
    expect(latest[2]).not.toBe(firstKey);
  });

  it.each(['resolve', 'reject'] as const)('ignores an older case lookup %s after a newer case loaded', async outcome => {
    const pending = deferred<CustomerCaseView>();
    vi.mocked(getCustomerCase).mockReturnValueOnce(pending.promise);
    render(<CustomerPortal />);
    fireEvent.click(screen.getByRole('button', { name: /Track & Clarify/i }));
    await waitFor(() => expect(getCustomerCase).toHaveBeenCalledWith(caseAId));
    fireEvent.click(screen.getByRole('button', { name: /case_demo_002 \(Under Investigation\)/i }));
    await screen.findByText(caseBId, { exact: true });
    if (outcome === 'resolve') await resolveDeferred(pending, caseView(caseAId));
    else await rejectDeferred(pending, 'Obsolete lookup failed');

    expect(screen.getByText(caseBId, { exact: true })).toBeInTheDocument();
    expect(screen.queryByText(caseAId, { exact: true })).not.toBeInTheDocument();
    expect(screen.queryByText(/Failed to fetch case details/i)).not.toBeInTheDocument();
  });

  it.each(['resolve', 'reject'] as const)('ignores a case A submission %s while case B has its own pending submission', async outcome => {
    const pendingA = deferred<CustomerCaseView>();
    const pendingB = deferred<CustomerCaseView>();
    vi.mocked(submitClarification).mockReturnValueOnce(pendingA.promise).mockReturnValueOnce(pendingB.promise);
    await openPortal('clarify');
    fireEvent.click(submitButton('clarify'));
    await waitFor(() => expect(submitClarification).toHaveBeenCalledTimes(1));
    await lookup(caseBId);
    answerAll('B response');
    fireEvent.click(submitButton('clarify'));
    await waitFor(() => expect(submitClarification).toHaveBeenCalledTimes(2));
    if (outcome === 'resolve') await resolveDeferred(pendingA, { ...caseView(caseAId, 3), status: 'UNDER_INVESTIGATION' });
    else await rejectDeferred(pendingA, 'Obsolete submit failed');

    expect(screen.getByText(caseBId, { exact: true })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Submitting Clarification/i })).toBeDisabled();
    expect(screen.queryByText(/successfully admitted|Failed to submit clarification/i)).not.toBeInTheDocument();
    await rejectDeferred(pendingB, 'Current B failure');
    expect(await screen.findByText('Failed to submit clarification.')).toBeInTheDocument();
    expect(submitButton('clarify')).toBeEnabled();
  });

  it('does not let an older refresh overwrite an accepted clarification response', async () => {
    const submission = deferred<CustomerCaseView>();
    const refresh = deferred<CustomerCaseView>();
    vi.mocked(submitClarification).mockReturnValueOnce(submission.promise);
    await openPortal('clarify');
    fireEvent.click(submitButton('clarify'));
    await waitFor(() => expect(submitClarification).toHaveBeenCalledTimes(1));
    vi.mocked(getCustomerCase).mockReturnValueOnce(refresh.promise);
    // #122 item 10: the page reads the case again once the answers are accepted, and
    // that read is the newest truth, so it must win over the older in-flight refresh.
    vi.mocked(getCustomerCase).mockReturnValueOnce(
      Promise.resolve({ ...caseView(caseAId, 3), status: 'UNDER_INVESTIGATION', clarification: undefined })
    );
    fireEvent.click(screen.getByRole('button', { name: /^Lookup$/ }));
    await waitFor(() => expect(getCustomerCase).toHaveBeenCalledTimes(2));
    await resolveDeferred(submission, { ...caseView(caseAId, 3), status: 'UNDER_INVESTIGATION', clarification: undefined });
    await resolveDeferred(refresh, caseView(caseAId));

    expect(screen.getByText('Being reviewed', { exact: true })).toBeInTheDocument();
    expect(screen.queryByText('UNDER_INVESTIGATION')).not.toBeInTheDocument();
    expect(screen.getByText(/Your answers were received/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Your answer...')).not.toBeInTheDocument();
  });
});

describe('clarification answer-or-evidence contract', () => {
  it('admits evidence-only clarification with current version and question-set binding', async () => {
    await openPortal('clarify');
    answerAll('');
    attachFile('evidence-only.png');
    stageFile('evidence-only.png');
    await screen.findByText('Staged');
    await submitAndObserve('clarify');

    expect(vi.mocked(submitClarification).mock.calls[0][1]).toEqual({
      expected_case_version: 2,
      question_set_id: `qset_${caseAId}`,
      answers: [],
      evidence_ids: [staged('evidence-only.png').evidence_id],
    });
    expect(screen.getByText(originalText, { exact: true })).toBeInTheDocument();
  });

  it('admits one answered question while another remains blank', async () => {
    await openPortal('clarify');
    answerAll('');
    fireEvent.change(screen.getAllByPlaceholderText('Your answer...')[0], { target: { value: '  Barcode 123  ' } });
    await submitAndObserve('clarify');
    expect(vi.mocked(submitClarification).mock.calls[0][1].answers).toEqual([{ question_id: 'q_barcode', text: 'Barcode 123' }]);
    expect(vi.mocked(submitClarification).mock.calls[0][1].evidence_ids).toEqual([]);
  });

  it('rejects a wholly empty or whitespace-only clarification', async () => {
    await openPortal('clarify');
    answerAll('   ');
    fireEvent.click(submitButton('clarify'));
    expect(await screen.findByText('Please provide an answer or supplementary evidence.')).toBeInTheDocument();
    expect(submitClarification).not.toHaveBeenCalled();
  });

  it('keeps unstaged and pending upload gates for evidence-only clarification', async () => {
    const pending = deferred<StagedEvidence>();
    vi.mocked(stageEvidence).mockReturnValueOnce(pending.promise);
    await openPortal('clarify');
    answerAll('');
    attachFile('pending.png');
    expect(submitButton('clarify')).toBeDisabled();
    // Exercise the handler gate as well as the disabled button, without altering HTML validation.
    fireEvent.submit(submitButton('clarify').closest('form')!);
    expect(screen.getByText(/All selected supplementary evidence files must be staged/i)).toBeInTheDocument();
    stageFile('pending.png');
    expect(submitButton('clarify')).toBeDisabled();
    fireEvent.submit(submitButton('clarify').closest('form')!);
    expect(screen.getByText(/Please wait for supplementary evidence files to finish uploading/i)).toBeInTheDocument();
    expect(submitClarification).not.toHaveBeenCalled();
    await resolveDeferred(pending, staged('pending.png'));
    await submitAndObserve('clarify');
    expect(submittedEvidence('clarify')).toEqual([staged('pending.png').evidence_id]);
  });
});

describe('lodgement evidence staging retry (#122 item 11)', () => {
  const busy = () =>
    new ApiError(503, 'Too many uploads in progress', 'SERVICE_UNAVAILABLE', undefined, undefined, true);

  it('retries a busy server twice under the same key, then shows the file as staged', async () => {
    vi.mocked(stageEvidence)
      .mockRejectedValueOnce(busy())
      .mockRejectedValueOnce(busy())
      .mockImplementationOnce(async file => staged(file.name));
    await openPortal('lodge');
    attachFile('busy.png');
    stageFile('busy.png');

    await waitFor(() => stagedBadge('lodge', 'busy.png'), { timeout: 4000 });
    expect(stageEvidence).toHaveBeenCalledTimes(3);
    const keys = vi.mocked(stageEvidence).mock.calls.map(call => call[2]);
    expect(keys[0]).toBeTruthy();
    expect(new Set(keys).size).toBe(1);
    expect(window.alert).not.toHaveBeenCalled();
  });

  it('gives up after the third busy reply and reports it', async () => {
    vi.mocked(stageEvidence).mockRejectedValue(busy());
    await openPortal('lodge');
    attachFile('busy.png');
    stageFile('busy.png');

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('Too many uploads in progress'), { timeout: 4000 });
    expect(stageEvidence).toHaveBeenCalledTimes(3);
    expect(fileRow('busy.png').getByRole('button', { name: /^Stage File$/i })).toBeEnabled();
  });

  it('does not retry a refusal the server marks as not retryable', async () => {
    vi.mocked(stageEvidence).mockRejectedValue(
      new ApiError(422, 'Unsupported file', 'VALIDATION_ERROR', undefined, undefined, false)
    );
    await openPortal('lodge');
    attachFile('refused.png');
    stageFile('refused.png');

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('Unsupported file'));
    expect(stageEvidence).toHaveBeenCalledTimes(1);
  });
});
