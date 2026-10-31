import React, { useState, useEffect, useRef } from 'react';
import {
  FileText,
  Upload,
  Send,
  Search,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  FileCheck,
  Download,
  RefreshCw,
  Plus,
  Trash2,
  Sparkles,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import {
  createCase,
  getCustomerCase,
  submitClarification,
  stageEvidence,
  downloadEvidence,
  isMockMode,
  ApiError,
  formatApiError,
} from '../api/client';
import {
  CustomerCaseView,
  RequestedOutcome,
  StagedEvidence,
  ClarificationAnswer,
  EvidenceAttachment,
  ClarificationRequest,
} from '../types/domain';
import {
  formatDate,
  getStatusBadgeClass,
  formatCustomerStatus,
  formatRequestedOutcome,
} from '../utils/formatters';
import { generateIdempotencyKey } from '../utils/idempotency';
import { isFinalStatus, usePolling, useRefreshOnReturn } from '../utils/autoRefresh';
import { MyCasesList } from '../components/MyCasesList';

// #122 item 7: the lodgement idempotency key and the payload it was minted for are
// kept for the tab's session. A reload or a tab switch after an uncertain failure
// then re-sends the same request instead of creating a second case. The key is
// scoped to the tab on purpose: a second tab is a different intent.
const LODGEMENT_KEY_STORAGE = 'returnops_lodgement_idempotency';

function readStoredLodgementKey(): { key: string; payload: string } | null {
  try {
    const raw = sessionStorage.getItem(LODGEMENT_KEY_STORAGE);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { key?: unknown; payload?: unknown };
    if (typeof parsed.key !== 'string' || typeof parsed.payload !== 'string') return null;
    return { key: parsed.key, payload: parsed.payload };
  } catch {
    // Storage disabled, quota exceeded or a corrupt value: behave as if absent.
    return null;
  }
}

function rememberLodgementKey(key: string, payload: string): void {
  try {
    sessionStorage.setItem(LODGEMENT_KEY_STORAGE, JSON.stringify({ key, payload }));
  } catch {
    // The key still works for this page; only the reload guarantee is lost.
  }
}

function forgetLodgementKey(): void {
  try {
    sessionStorage.removeItem(LODGEMENT_KEY_STORAGE);
  } catch {
    // Nothing to clean up.
  }
}

// #122 item 7: the envelope says whether the same request can be retried. Saying
// so is what stops a customer from resending a request the server has already
// refused on its content.
function describeSubmitError(err: unknown, fallback: string): string {
  if (!(err instanceof ApiError)) return fallback;
  const base = err.code ? `[${err.code}] ${err.message}` : err.message;
  if (err.retryable === false) {
    return `${base} This request cannot succeed as it stands; change it before sending again.`;
  }
  if (err.retryable === true) {
    return `${base} This may be retried; sending the same request again reuses the same key.`;
  }
  return base;
}

// The contract's limits on attached files (EvidenceAttachment, CreateCaseRequest and
// ClarificationRequest): JPEG, PNG or PDF, 1 byte to 10 MiB each, at most 10 per
// request. A file outside them is refused here, with the reason, instead of being
// uploaded and refused by the server, or sent and refused as "Request fields are invalid".
const ATTACHABLE_TYPES = ['image/jpeg', 'image/png', 'application/pdf'];
const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
const MAX_ATTACHMENTS = 10;
// CreateCaseRequest.order_reference allows at most 120 characters.
const MAX_ORDER_REFERENCE = 120;

function admitAttachments(alreadySelected: number, picked: File[]): { admitted: File[]; refused: string | null } {
  const admitted: File[] = [];
  const reasons: string[] = [];
  for (const file of picked) {
    if (!ATTACHABLE_TYPES.includes(file.type)) reasons.push(`${file.name} is not a JPEG, PNG or PDF file.`);
    else if (file.size === 0) reasons.push(`${file.name} is empty.`);
    else if (file.size > MAX_ATTACHMENT_BYTES) reasons.push(`${file.name} is larger than 10 MB.`);
    else if (alreadySelected + admitted.length >= MAX_ATTACHMENTS) reasons.push(`${file.name} was not added: at most ${MAX_ATTACHMENTS} files can be attached.`);
    else admitted.push(file);
  }
  return { admitted, refused: reasons.length > 0 ? `Not attached: ${reasons.join(' ')}` : null };
}

// A customer reads plain words for the two lookups that are the customer's to fix;
// any other refusal keeps the server's code.
function describeLookupError(err: unknown): string {
  if (!(err instanceof ApiError)) return 'Failed to fetch case details';
  if (err.status === 404) return 'No case with this ID was found for your account. Check the ID and try again.';
  if (err.status === 422) return 'This is not a valid case ID. Use the ID shown when your request was lodged.';
  return err.code ? `${err.code}: ${err.message}` : err.message;
}

export const CustomerPortal: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'lodge' | 'track'>('lodge');

  // ---------------------------------------------------------
  // Sub-Tab 1: Lodge Request Form State (UC-01)
  // ---------------------------------------------------------
  const [originalMessage, setOriginalMessage] = useState('');
  const [orderReference, setOrderReference] = useState('');
  const [requestedOutcome, setRequestedOutcome] = useState<RequestedOutcome>('UNSPECIFIED');
  const [selectedFiles, setSelectedFiles] = useState<
    Array<{ file: File; description: string; staged?: StagedEvidence; uploading?: boolean; idempotencyKey: string }>
  >([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  // Files refused on selection, with the reason (type, size or count).
  const [fileNotice, setFileNotice] = useState<string | null>(null);
  const [createdCaseResult, setCreatedCaseResult] = useState<CustomerCaseView | null>(null);
  // Idempotency state for case lodgement
  const [pendingLodgementKey, setPendingLodgementKey] = useState<string | null>(null);
  const [lastSubmittedLodgementPayload, setLastSubmittedLodgementPayload] = useState<string | null>(null);
  const activeLodgementUploads = useRef(new Set<string>());

  // ---------------------------------------------------------
  // Sub-Tab 2: Track & Clarify State (UC-01E)
  // ---------------------------------------------------------
  // Demo case IDs exist only in Mock Mode (#111 item 3).
  const [searchCaseId, setSearchCaseId] = useState(() => (isMockMode() ? 'case_demo_001' : ''));
  const [currentCase, setCurrentCase] = useState<CustomerCaseView | null>(null);
  const [isLoadingCase, setIsLoadingCase] = useState(false);
  const [caseError, setCaseError] = useState<string | null>(null);

  // Clarification form & attachment state (UC-01E / Finding 8)
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [clarificationFiles, setClarificationFiles] = useState<
    Array<{ file: File; description: string; staged?: StagedEvidence; uploading?: boolean; idempotencyKey: string }>
  >([]);
  const [isSubmittingClarify, setIsSubmittingClarify] = useState(false);
  const [clarifySuccessMsg, setClarifySuccessMsg] = useState<string | null>(null);
  const [clarifyErrorMsg, setClarifyErrorMsg] = useState<string | null>(null);
  const [clarificationFileNotice, setClarificationFileNotice] = useState<string | null>(null);
  const [pendingClarifyKey, setPendingClarifyKey] = useState<string | null>(null);
  const [lastClarifyPayload, setLastClarifyPayload] = useState<string | null>(null);
  const activeClarificationUploads = useRef(new Set<string>());
  const activeCaseId = useRef<string | null>(null);
  const clarificationScope = useRef<string | null>(null);
  const clarificationGeneration = useRef(0);
  const latestCaseLoad = useRef(0);
  // Number of clarification POSTs not yet settled; quiet refreshes wait for zero.
  const clarifyInFlight = useRef(0);

  // Protected Evidence Download State (Finding 5)
  const [downloadingEvId, setDownloadingEvId] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Auto-load initial demo case on mount
  useEffect(() => {
    if (activeSubTab === 'track' && searchCaseId) {
      loadCase(searchCaseId);
    }
  }, [activeSubTab]);

  const resetClarificationDraft = () => {
    clarificationGeneration.current += 1;
    clarificationScope.current = null;
    activeClarificationUploads.current.clear();
    setAnswers({});
    setClarificationFiles([]);
    setPendingClarifyKey(null);
    setLastClarifyPayload(null);
    setIsSubmittingClarify(false);
    setClarificationFileNotice(null);
    // The "answers were received" confirmation is not part of the draft: it stays
    // through the 5 s refresh and Refresh, and goes only on a case switch or a new lodgement.
    setClarifyErrorMsg(null);
  };

  const getClarificationScope = (view: CustomerCaseView) =>
    JSON.stringify([view.case_id, view.case_version, view.clarification?.question_set_id ?? null]);

  // Returns the case view it loaded, or null if it loaded none.
  const loadCase = async (caseId: string): Promise<CustomerCaseView | null> => {
    const requestedCaseId = caseId.trim();
    if (!requestedCaseId) return null;
    const request = ++latestCaseLoad.current;
    // A case switch invalidates pending callbacks immediately, before GET returns.
    if (activeCaseId.current !== requestedCaseId) {
      activeCaseId.current = requestedCaseId;
      resetClarificationDraft();
      setClarifySuccessMsg(null);
      setCurrentCase(null);
    }
    setIsLoadingCase(true);
    setCaseError(null);
    setClarifyErrorMsg(null);
    try {
      const data = await getCustomerCase(requestedCaseId);
      if (request !== latestCaseLoad.current) return null;
      const nextScope = getClarificationScope(data);
      if (clarificationScope.current !== nextScope) {
        resetClarificationDraft();
        clarificationScope.current = nextScope;
      }
      activeCaseId.current = data.case_id;
      setCurrentCase(data);
      return data;
    } catch (err: unknown) {
      if (request !== latestCaseLoad.current) return null;
      if (err instanceof ApiError && [401, 403, 404].includes(err.status)) {
        activeCaseId.current = null;
        resetClarificationDraft();
      }
      // A transient read failure hides the view without discarding an uncertain
      // POST's retry identity. Recovery must confirm the same scope to reuse it.
      setCurrentCase(null);
      setCaseError(describeLookupError(err));
      return null;
    } finally {
      if (request === latestCaseLoad.current) setIsLoadingCase(false);
    }
  };

  // #111 item 2: reads the tracked case again without the loading state and
  // without clearing messages. A failed read keeps the view on screen (a 401
  // shows the session banner). The same scope rule as loadCase applies, so an
  // unchanged question set keeps the customer's draft.
  const refreshCaseQuietly = async (caseId: string) => {
    if (clarifyInFlight.current > 0) return;
    const request = ++latestCaseLoad.current;
    try {
      const data = await getCustomerCase(caseId);
      // An answer submitted meanwhile owns the next view (its receipt and message).
      if (request !== latestCaseLoad.current || activeCaseId.current !== caseId || clarifyInFlight.current > 0) return;
      const nextScope = getClarificationScope(data);
      if (clarificationScope.current !== nextScope) {
        resetClarificationDraft();
        clarificationScope.current = nextScope;
      }
      setCurrentCase(data);
    } catch {
      // Keep the current view; the next tick or a manual Refresh tries again.
    }
  };

  // Nothing is read while a lookup or an answer is in flight, so neither can be
  // overtaken by a quiet read.
  const canRefreshQuietly =
    activeSubTab === 'track' &&
    currentCase !== null &&
    activeCaseId.current === currentCase.case_id &&
    !isLoadingCase &&
    !isSubmittingClarify;

  // Polls every 5 s while the shop is working on the case: not while the shop
  // waits for the customer's answers, and not once the case is final.
  const pollingTrackedCase =
    canRefreshQuietly &&
    currentCase !== null &&
    !currentCase.clarification &&
    currentCase.status !== 'AWAITING_INFORMATION' &&
    !isFinalStatus(currentCase.status);
  usePolling(() => {
    if (currentCase) refreshCaseQuietly(currentCase.case_id);
  }, pollingTrackedCase);

  useRefreshOnReturn(() => {
    if (canRefreshQuietly && currentCase) refreshCaseQuietly(currentCase.case_id);
  });

  // ---------------------------------------------------------
  // File Upload Handlers
  // ---------------------------------------------------------
  // While a POST is pending its draft is frozen (#88): the form's inputs, Add File,
  // Stage and Remove are disabled and their change and click handlers return early,
  // so the success reset can only clear what was actually submitted.
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || isSubmitting) return;
    const { admitted, refused } = admitAttachments(selectedFiles.length, Array.from(e.target.files));
    setFileNotice(refused);
    // The same file can be picked again after it was refused or removed.
    e.target.value = '';
    const newFiles = admitted.map((f) => ({
      file: f,
      description: '',
      // Binding the key at selection time means a lost-response retry of the
      // same file intent reuses the original key (Finding 1).
      idempotencyKey: generateIdempotencyKey('ev_idem'),
    }));
    setSelectedFiles((prev) => [...prev, ...newFiles]);
  };

  const handleStageFile = async (fileKey: string) => {
    const item = selectedFiles.find((file) => file.idempotencyKey === fileKey);
    if (isSubmitting || !item || item.staged || activeLodgementUploads.current.has(fileKey)) return;

    activeLodgementUploads.current.add(fileKey);
    setSelectedFiles((files) => files.map((file) =>
      file.idempotencyKey === fileKey ? { ...file, uploading: true } : file
    ));

    try {
      // #122 item 11: the server serves at most two uploads at once and answers the
      // rest with a retryable 503. Retry the same file under the same key instead of
      // making the customer press the button again.
      const stageWithRetry = async (tries: number): Promise<StagedEvidence> => {
        try {
          return await stageEvidence(item.file, item.description || undefined, item.idempotencyKey);
        } catch (err: unknown) {
          if (tries > 1 && err instanceof ApiError && (err.retryable === true || err.status === 503)) {
            await new Promise((resolve) => setTimeout(resolve, 400));
            return stageWithRetry(tries - 1);
          }
          throw err;
        }
      };
      const staged = await stageWithRetry(3);
      if (!activeLodgementUploads.current.delete(fileKey)) return;
      setSelectedFiles((files) => files.map((file) =>
        file.idempotencyKey === fileKey ? { ...file, staged, uploading: false } : file
      ));
    } catch (err: unknown) {
      if (!activeLodgementUploads.current.delete(fileKey)) return;
      setSelectedFiles((files) => files.map((file) =>
        file.idempotencyKey === fileKey ? { ...file, uploading: false } : file
      ));
      alert(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const handleRemoveFile = (fileKey: string) => {
    if (isSubmitting) return;
    activeLodgementUploads.current.delete(fileKey);
    setSelectedFiles((files) => files.filter((file) => file.idempotencyKey !== fileKey));
  };

  // ---------------------------------------------------------
  // Case Submission (UC-01)
  // ---------------------------------------------------------
  const handleSubmitCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!originalMessage.trim()) {
      setSubmitError('Please describe your return request.');
      return;
    }

    // Block case submission while selected evidence is unstaged or uploading (Finding 7)
    if (selectedFiles.some((f) => f.uploading)) {
      setSubmitError('Please wait for selected evidence files to finish uploading before submitting.');
      return;
    }
    if (selectedFiles.some((f) => !f.staged)) {
      setSubmitError('All selected evidence files must be staged before submitting, or removed from the list.');
      return;
    }

    // Gather staged evidence IDs
    const evidence_ids = selectedFiles
      .map((f) => f.staged?.evidence_id)
      .filter((id): id is string => Boolean(id));

    const payloadObj = {
      original_message: originalMessage.trim(),
      order_reference: orderReference.trim() || undefined,
      requested_outcome: requestedOutcome,
      evidence_ids: evidence_ids.length > 0 ? evidence_ids : undefined,
    };
    const payloadStr = JSON.stringify(payloadObj);

    // #122 item 7: the key is also kept in sessionStorage, so a reload or a tab
    // switch inside the same session cannot mint a second key for the same intent
    // and create a duplicate case after an uncertain failure.
    const storedLodgement = readStoredLodgementKey();
    let keyToUse = pendingLodgementKey ?? storedLodgement?.key;
    const lastPayload = lastSubmittedLodgementPayload ?? storedLodgement?.payload ?? null;
    if (!keyToUse || payloadStr !== lastPayload) {
      keyToUse = generateIdempotencyKey('case_idem');
      setPendingLodgementKey(keyToUse);
      setLastSubmittedLodgementPayload(payloadStr);
    }
    rememberLodgementKey(keyToUse, payloadStr);

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const newCase = await createCase(payloadObj, keyToUse);
      setCreatedCaseResult(newCase);
      // Reset form and idempotency state. The outcome is reset too, so the next
      // case never inherits this one's choice unseen.
      setOriginalMessage('');
      setOrderReference('');
      setRequestedOutcome('UNSPECIFIED');
      setSelectedFiles([]);
      setFileNotice(null);
      // A confirmation for answers on an earlier case does not belong to this one.
      setClarifySuccessMsg(null);
      setPendingLodgementKey(null);
      setLastSubmittedLodgementPayload(null);
      // The intent is accepted, so the next lodgement is a new one.
      forgetLodgementKey();
    } catch (err: unknown) {
      setSubmitError(describeSubmitError(err, 'Failed to lodge return case.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // ---------------------------------------------------------
  // Clarification File Upload Handlers (UC-01E / Finding 8)
  // ---------------------------------------------------------
  const handleClarificationFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || isSubmittingClarify) return;
    const { admitted, refused } = admitAttachments(clarificationFiles.length, Array.from(e.target.files));
    setClarificationFileNotice(refused);
    e.target.value = '';
    const newFiles = admitted.map((f) => ({
      file: f,
      description: '',
      // Same identity handling as UC-01 uploads (Finding 1).
      idempotencyKey: generateIdempotencyKey('ev_idem'),
    }));
    setClarificationFiles((prev) => [...prev, ...newFiles]);
  };

  const handleStageClarificationFile = async (fileKey: string) => {
    const item = clarificationFiles.find((file) => file.idempotencyKey === fileKey);
    if (isSubmittingClarify || !item || item.staged || activeClarificationUploads.current.has(fileKey)) return;
    const generation = clarificationGeneration.current;

    activeClarificationUploads.current.add(fileKey);
    setClarificationFiles((files) => files.map((file) =>
      file.idempotencyKey === fileKey ? { ...file, uploading: true } : file
    ));

    try {
      const staged = await stageEvidence(item.file, item.description || undefined, item.idempotencyKey);
      if (generation !== clarificationGeneration.current || !activeClarificationUploads.current.delete(fileKey)) return;
      setClarificationFiles((files) => files.map((file) =>
        file.idempotencyKey === fileKey ? { ...file, staged, uploading: false } : file
      ));
    } catch (err: unknown) {
      if (generation !== clarificationGeneration.current || !activeClarificationUploads.current.delete(fileKey)) return;
      setClarificationFiles((files) => files.map((file) =>
        file.idempotencyKey === fileKey ? { ...file, uploading: false } : file
      ));
      alert(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const handleRemoveClarificationFile = (fileKey: string) => {
    if (isSubmittingClarify) return;
    activeClarificationUploads.current.delete(fileKey);
    setClarificationFiles((files) => files.filter((file) => file.idempotencyKey !== fileKey));
  };

  // ---------------------------------------------------------
  // Clarification Submission (UC-01E / Finding 1 & 8)
  // ---------------------------------------------------------
  const handleSubmitClarification = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentCase || !currentCase.clarification || isLoadingCase || isSubmittingClarify) return;
    const generation = clarificationGeneration.current;

    const answerList: ClarificationAnswer[] = Object.entries(answers)
      .filter(([_, text]) => text.trim().length > 0)
      .map(([question_id, text]) => ({
        question_id,
        text: text.trim(),
      }));

    // Validate supplementary clarification files
    if (clarificationFiles.some((f) => f.uploading)) {
      setClarifyErrorMsg('Please wait for supplementary evidence files to finish uploading before submitting.');
      return;
    }
    if (clarificationFiles.some((f) => !f.staged)) {
      setClarifyErrorMsg('All selected supplementary evidence files must be staged before submitting, or removed.');
      return;
    }

    const clarifyEvidenceIds = clarificationFiles
      .map((f) => f.staged?.evidence_id)
      .filter((id): id is string => Boolean(id));

    if (answerList.length === 0 && clarifyEvidenceIds.length === 0) {
      setClarifyErrorMsg('Please provide an answer or supplementary evidence.');
      return;
    }

    const wirePayload: ClarificationRequest = {
      expected_case_version: currentCase.case_version,
      question_set_id: currentCase.clarification.question_set_id,
      answers: answerList,
      evidence_ids: clarifyEvidenceIds,
    };
    const payloadStr = JSON.stringify(wirePayload);

    // Reuse idempotency key on retry if payload is identical
    let keyToUse = pendingClarifyKey;
    if (!keyToUse || payloadStr !== lastClarifyPayload) {
      keyToUse = generateIdempotencyKey('clarify_idem');
      setPendingClarifyKey(keyToUse);
      setLastClarifyPayload(payloadStr);
    }

    setIsSubmittingClarify(true);
    setClarifyErrorMsg(null);
    setClarifySuccessMsg(null);
    clarifyInFlight.current += 1;

    try {
      const receipt = await submitClarification(currentCase.case_id, wirePayload, keyToUse);
      if (generation !== clarificationGeneration.current) return;
      // A read begun before this accepted submission must not restore an old view.
      latestCaseLoad.current += 1;
      // #122 item 10: the POST receipt is not the current case (docs/09 line 186).
      // Read the case again and show that; the receipt stays as the fallback when
      // the read fails, because it is still better than showing nothing.
      let updated = receipt;
      const read = ++latestCaseLoad.current;
      try {
        updated = await getCustomerCase(currentCase.case_id);
      } catch {
        updated = receipt;
      }
      if (generation !== clarificationGeneration.current) return;
      if (activeCaseId.current !== currentCase.case_id) return;
      // A later lookup wins; this read must not overwrite it.
      if (read !== latestCaseLoad.current) return;
      setIsLoadingCase(false);
      resetClarificationDraft();
      clarificationScope.current = getClarificationScope(updated);
      setCurrentCase(updated);
      setClarifySuccessMsg('Thank you. Your answers were received and the shop will continue reviewing your case.');
    } catch (err: unknown) {
      if (generation !== clarificationGeneration.current) return;
      if (err instanceof ApiError && err.code === 'STALE_CASE_VERSION') {
        // #122 item 2 (docs/09 error table): the case moved on since this page read
        // it, so it is reloaded. Typed answers are kept when the questions are the
        // same; nothing is sent again without the customer.
        const caseId = currentCase.case_id;
        const typedAnswers = { ...answers };
        const reloaded = await loadCase(caseId);
        if (!reloaded || activeCaseId.current !== caseId) return;
        const sameQuestions = reloaded.clarification?.question_set_id === wirePayload.question_set_id;
        if (reloaded.clarification && sameQuestions) {
          setAnswers(typedAnswers);
          setClarifyErrorMsg(
            'Your case changed while you were answering, so the page was reloaded. Check the questions and send your answers again.'
          );
        } else if (reloaded.clarification) {
          setClarifyErrorMsg(
            'Your case changed while you were answering, so the page was reloaded. The shop has new questions for you.'
          );
        } else {
          setCaseError('Your case changed while you were answering, so the page was reloaded. Please check its current status.');
        }
        return;
      }
      setClarifyErrorMsg(describeSubmitError(err, 'Failed to submit clarification.'));
    } finally {
      clarifyInFlight.current -= 1;
      if (generation === clarificationGeneration.current) setIsSubmittingClarify(false);
    }
  };

  // ---------------------------------------------------------
  // Protected Evidence Download (Finding 5)
  // ---------------------------------------------------------
  const handleDownloadEvidence = async (ev: EvidenceAttachment) => {
    setDownloadingEvId(ev.evidence_id);
    setDownloadError(null);
    try {
      await downloadEvidence(ev.evidence_id, ev.filename);
    } catch (err: unknown) {
      setDownloadError(err instanceof ApiError ? formatApiError(err) : 'Failed to download evidence content');
    } finally {
      setDownloadingEvId(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 sm:px-6 space-y-6">
      {/* Sub-Tabs Header */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Customer Service Portal</h1>
          <p className="text-sm text-slate-500 mt-1">
            Describe your problem in your own words, then track your return and answer any follow-up questions.
          </p>
        </div>

        <div className="flex bg-slate-100 p-1 rounded-xl">
          <button
            onClick={() => setActiveSubTab('lodge')}
            className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all ${
              activeSubTab === 'lodge'
                ? 'bg-white text-sky-700 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Lodge Return
          </button>
          <button
            onClick={() => setActiveSubTab('track')}
            className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all ${
              activeSubTab === 'track'
                ? 'bg-white text-sky-700 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Track & Clarify
          </button>
        </div>
      </div>

      {/* ========================================================= */}
      {/* SUB-TAB 1: Lodge Request Form (UC-01 / AH-01)            */}
      {/* ========================================================= */}
      {activeSubTab === 'lodge' && (
        <div className="space-y-6">
          {createdCaseResult ? (
            <div className="bg-emerald-50 border border-emerald-300 rounded-2xl p-6 text-emerald-900 space-y-4 shadow-sm animate-fade-in">
              <div className="flex items-center space-x-3">
                <div className="bg-emerald-600 text-white p-2 rounded-full">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-bold">Return Request Submitted Successfully!</h3>
                  <p className="text-sm text-emerald-700">
                    We have received your request. Keep the case ID below to track it.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 bg-white/80 p-4 rounded-xl border border-emerald-200">
                <div>
                  <div className="text-xs text-slate-500 font-semibold uppercase">Case ID</div>
                  {/* A server case ID is 37 characters with no break point; it wraps instead of running into the badge. */}
                  <div className="text-sm font-mono font-bold text-slate-900 break-all">{createdCaseResult.case_id}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 font-semibold uppercase">Status</div>
                  <span
                    className={`inline-block mt-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadgeClass(
                      createdCaseResult.status
                    )}`}
                  >
                    {formatCustomerStatus(createdCaseResult.status)}
                  </span>
                </div>
                <div>
                  <div className="text-xs text-slate-500 font-semibold uppercase">Submitted At</div>
                  <div className="text-xs text-slate-800">{formatDate(createdCaseResult.created_at)}</div>
                </div>
              </div>

              <div className="flex items-center space-x-3 pt-2">
                <button
                  onClick={() => {
                    // Switching to Track reads the case once, through the effect above;
                    // reading it here as well sent a second GET.
                    setSearchCaseId(createdCaseResult.case_id);
                    setActiveSubTab('track');
                  }}
                  className="px-5 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-semibold rounded-xl shadow-sm flex items-center space-x-2 transition-colors"
                >
                  <span>Track This Case & View Status</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setCreatedCaseResult(null)}
                  className="px-4 py-2.5 bg-white hover:bg-emerald-100 text-emerald-800 border border-emerald-300 text-sm font-medium rounded-xl transition-colors"
                >
                  Lodge Another Return
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmitCase} className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
              {/* Natural Language Statement */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-bold text-slate-900 flex items-center space-x-1">
                    <span>Describe Your Issue or Return Reason</span>
                    <span className="text-rose-500">*</span>
                  </label>
                  <span className="text-xs text-slate-400 font-mono">
                    {originalMessage.length} / 12,000 chars
                  </span>
                </div>
                <textarea
                  rows={5}
                  required
                  value={originalMessage}
                  disabled={isSubmitting}
                  onChange={(e) => {
                    if (!isSubmitting) setOriginalMessage(e.target.value);
                  }}
                  placeholder="Tell us what happened with your purchase in your own words (e.g., 'I received a damaged wool sweater with a broken zipper yesterday; ordered size M in Blue')..."
                  className="w-full text-sm p-4 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:bg-white transition-all resize-y disabled:opacity-50 disabled:cursor-not-allowed"
                />
                <p className="text-xs text-slate-500 mt-1.5 flex items-center space-x-1">
                  <Sparkles className="w-3.5 h-3.5 text-sky-500" />
                  <span>
                    We will check your order and ask you if anything is missing.
                  </span>
                </p>
              </div>

              {/* Optional Fields Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Order Reference */}
                <div>
                  <label className="block text-sm font-bold text-slate-900 mb-1.5">
                    Order Reference <span className="text-xs font-normal text-slate-500">(Optional, up to 120 characters)</span>
                  </label>
                  <input
                    type="text"
                    value={orderReference}
                    disabled={isSubmitting}
                    onChange={(e) => {
                      if (!isSubmitting) setOrderReference(e.target.value);
                    }}
                    placeholder="e.g. SYN-1001"
                    maxLength={MAX_ORDER_REFERENCE}
                    className="w-full text-sm px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:bg-white transition-all font-mono disabled:opacity-50 disabled:cursor-not-allowed"
                  />
                  <span className="text-[11px] text-slate-400 mt-1 block">
                    If you do not have it, we will ask you for it or for other details of your purchase.
                  </span>
                </div>

                {/* Requested Outcome */}
                <div>
                  <label className="block text-sm font-bold text-slate-900 mb-1.5">
                    Requested Outcome
                  </label>
                  <select
                    value={requestedOutcome}
                    disabled={isSubmitting}
                    onChange={(e) => {
                      if (!isSubmitting) setRequestedOutcome(e.target.value as RequestedOutcome);
                    }}
                    className="w-full text-sm px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:bg-white transition-all font-medium text-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <option value="UNSPECIFIED">Not sure - let the shop advise</option>
                    <option value="REFUND">Refund to Original Payment Method</option>
                    <option value="REPLACEMENT">Replacement Item</option>
                    <option value="REPAIR">Repair Service</option>
                    <option value="RETURN">Standard Return / Store Credit</option>
                    <option value="INFORMATION">Information / Inquiry Only</option>
                    <option value="OTHER">Other Resolution</option>
                  </select>
                </div>
              </div>

              {/* Staged Evidence Section */}
              <div className="border-t border-slate-100 pt-5">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-1.5">
                      <Upload className="w-4 h-4 text-sky-600" />
                      <span>Attach Supporting Evidence (JPEG / PNG / PDF)</span>
                    </h3>
                    <p className="text-xs text-slate-500">
                      JPEG, PNG or PDF, up to 10 MB each and 10 files in total.
                    </p>
                  </div>
                  <label className={`px-3.5 py-1.5 bg-sky-50 text-sky-700 text-xs font-semibold rounded-xl border border-sky-200 transition-colors flex items-center space-x-1 focus-within:ring-2 focus-within:ring-sky-500 ${isSubmitting ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-sky-100'}`}>
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add File</span>
                    {/* Visually hidden, not display:none, so the keyboard can reach it;
                        the label shows the focus ring. */}
                    <input
                      type="file"
                      multiple
                      accept="image/jpeg,image/png,application/pdf"
                      disabled={isSubmitting}
                      onChange={handleFileSelect}
                      className="sr-only"
                    />
                  </label>
                </div>

                {fileNotice && (
                  <p role="alert" className="mb-3 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs break-words">
                    {fileNotice}
                  </p>
                )}

                {selectedFiles.length === 0 ? (
                  <div className="border-2 border-dashed border-slate-200 rounded-xl p-6 text-center text-slate-400 text-xs bg-slate-50/50">
                    No files attached yet. Click "Add File" to attach photos of damaged items, packaging, or receipts.
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {selectedFiles.map((item) => (
                      <div
                        key={item.idempotencyKey}
                        className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs"
                      >
                        <div className="flex items-center space-x-3 overflow-hidden">
                          <FileText className="w-4 h-4 text-slate-500 flex-shrink-0" />
                          <div className="truncate">
                            <span className="font-semibold text-slate-800 truncate block">
                              {item.file.name}
                            </span>
                            <span className="text-slate-400 font-mono">
                              {(item.file.size / 1024).toFixed(1)} KB
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center space-x-2">
                          {item.staged ? (
                            <span className="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-mono text-[11px] font-semibold flex items-center space-x-1">
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              <span data-evidence-id={item.staged.evidence_id}>Staged</span>
                            </span>
                          ) : (
                            <button
                              type="button"
                              disabled={item.uploading || isSubmitting}
                              onClick={() => handleStageFile(item.idempotencyKey)}
                              className="px-2.5 py-1 bg-sky-600 hover:bg-sky-700 text-white rounded-lg font-medium text-xs disabled:opacity-50"
                            >
                              {item.uploading ? 'Uploading...' : 'Stage File'}
                            </button>
                          )}

                          <button
                            type="button"
                            disabled={isSubmitting}
                            onClick={() => handleRemoveFile(item.idempotencyKey)}
                            aria-label={`Remove ${item.file.name}`}
                            className="text-slate-400 hover:text-rose-600 p-1 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* A refusal is shown next to the button that sent the request, not at the top of a long form. */}
              {submitError && (
                <div
                  role="alert"
                  className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm flex items-center space-x-2 break-words"
                >
                  <ShieldAlert className="w-5 h-5 text-rose-600 flex-shrink-0" />
                  <span className="min-w-0">{submitError}</span>
                </div>
              )}

              {/* Submit Button */}
              <div className="border-t border-slate-100 pt-4 flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="text-xs">
                  {selectedFiles.some((f) => f.uploading) && (
                    <span className="text-sky-700 font-medium">Uploading evidence files... please wait.</span>
                  )}
                  {selectedFiles.some((f) => !f.staged && !f.uploading) && (
                    <span className="text-amber-700 font-medium">Please stage or remove all selected evidence files before submitting.</span>
                  )}
                </div>
                <button
                  type="submit"
                  disabled={
                    isSubmitting ||
                    !originalMessage.trim() ||
                    selectedFiles.some((f) => !f.staged || f.uploading)
                  }
                  className="px-6 py-3 bg-sky-600 hover:bg-sky-700 text-white font-semibold text-sm rounded-xl shadow-md transition-all flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Lodging Return Case...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      <span>Submit Return Request</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* SUB-TAB 2: Track & Clarify (UC-01E)                       */}
      {/* ========================================================= */}
      {activeSubTab === 'track' && (
        <div className="space-y-6">
          {/* The signed-in customer's own requests (31 October 2026); a row opens the case
              as Lookup does, and the list folds away while a case is open. */}
          <MyCasesList
            openCaseId={currentCase ? currentCase.case_id : isLoadingCase && searchCaseId.trim() ? searchCaseId.trim() : null}
            openCase={currentCase}
            onOpen={(caseId) => {
              setSearchCaseId(caseId);
              loadCase(caseId);
            }}
          />

          {/* Lookup Bar */}
          {/* Stacked below 1024 px, so Mock Mode's demo buttons never squeeze the case ID box. */}
          <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-3">
            {/* A form, so Enter in the box looks the case up as the button does; while a
                lookup runs the button is disabled and Enter sends nothing more. */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!isLoadingCase && searchCaseId.trim()) loadCase(searchCaseId);
              }}
              className="flex-1 w-full flex items-center space-x-2"
            >
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type="text"
                  aria-label="Case ID"
                  value={searchCaseId}
                  onChange={(e) => setSearchCaseId(e.target.value)}
                  placeholder={isMockMode() ? 'Enter Case ID (e.g. case_demo_001)...' : 'Enter your case ID...'}
                  className="w-full pl-10 pr-4 py-2 text-sm bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 font-mono"
                />
              </div>
              <button
                type="submit"
                disabled={isLoadingCase || !searchCaseId.trim()}
                className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold rounded-xl transition-colors flex items-center space-x-1.5 disabled:opacity-50"
              >
                {isLoadingCase ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                <span>Lookup</span>
              </button>
            </form>

            {/* Quick Demo Case Selector: Mock Mode only (#111 item 3); wraps on a phone. */}
            {isMockMode() && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
              <span>Demo Cases:</span>
              <button
                onClick={() => {
                  setSearchCaseId('case_demo_001');
                  loadCase('case_demo_001');
                }}
                className="px-2.5 py-1 bg-amber-50 text-amber-800 border border-amber-200 rounded-lg font-mono hover:bg-amber-100"
              >
                case_demo_001 (Clarification Ready)
              </button>
              <button
                onClick={() => {
                  setSearchCaseId('case_demo_002');
                  loadCase('case_demo_002');
                }}
                className="px-2.5 py-1 bg-blue-50 text-blue-800 border border-blue-200 rounded-lg font-mono hover:bg-blue-100"
              >
                case_demo_002 (Under Investigation)
              </button>
            </div>
            )}
          </div>

          {caseError && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-sm flex items-center space-x-2">
              <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
              <span>{caseError}</span>
            </div>
          )}

          {currentCase && (
            <div className="space-y-6 animate-fade-in">
              {/* Case Overview Card */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-2">
                  {/* The 37-character case ID and the status wrap on a phone instead of leaving the card. */}
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2 min-w-0">
                    <span className="font-mono text-xl font-bold text-slate-900 break-all">{currentCase.case_id}</span>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-semibold border ${getStatusBadgeClass(
                        currentCase.status
                      )}`}
                    >
                      {formatCustomerStatus(currentCase.status)}
                    </span>
                  </div>
                  <div className="flex items-center space-x-4 text-xs text-slate-500">
                    {pollingTrackedCase && (
                      <span className="text-[11px] text-slate-400">This page updates by itself</span>
                    )}
                    <button
                      onClick={() => loadCase(currentCase.case_id)}
                      className="px-2 py-1 hover:text-sky-600 rounded-lg hover:bg-slate-100 flex items-center space-x-1"
                      title="Refresh Case"
                    >
                      <RefreshCw className="w-4 h-4" />
                      <span>Refresh</span>
                    </button>
                  </div>
                </div>

                {currentCase.outcome_message && (
                  <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-900 text-sm break-words">
                    <strong>Final Outcome: </strong>
                    {currentCase.outcome_message}
                  </div>
                )}

                {/* Key Timestamps */}
                <div className="grid grid-cols-2 gap-4 text-xs text-slate-500">
                  <div>
                    Created: <span className="font-medium text-slate-800">{formatDate(currentCase.created_at)}</span>
                  </div>
                  <div>
                    Last Updated:{' '}
                    <span className="font-medium text-slate-800">{formatDate(currentCase.updated_at)}</span>
                  </div>
                </div>
              </div>

              {/* ========================================================= */}
              {/* TARGETED CLARIFICATION SECTION (UC-01E)                   */}
              {/* ========================================================= */}
              {clarifySuccessMsg && (
                <div className="p-4 bg-emerald-100 border border-emerald-300 text-emerald-900 text-sm rounded-2xl flex items-center space-x-2 animate-fade-in shadow-sm">
                  <CheckCircle2 className="w-5 h-5 text-emerald-700 flex-shrink-0" />
                  <span>{clarifySuccessMsg}</span>
                </div>
              )}

              {currentCase.clarification && currentCase.clarification.questions?.length > 0 && (
                <div className="bg-amber-50/70 border-2 border-amber-300 rounded-2xl p-6 shadow-sm space-y-5">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-2.5">
                      <div className="p-2 bg-amber-500 text-white rounded-xl shadow-sm">
                        <HelpCircle className="w-5 h-5" />
                      </div>
                      <div>
                        <h2 className="text-base font-bold text-amber-950">
                          A few questions for you
                        </h2>
                        <p className="text-xs text-amber-800 mt-0.5">
                          Please answer what you can, so the shop can continue reviewing your return.
                        </p>
                      </div>
                    </div>
                  </div>

                  {clarifyErrorMsg && (
                    <div className="p-3.5 bg-rose-100 border border-rose-300 text-rose-900 text-xs rounded-xl flex items-center space-x-2">
                      <AlertTriangle className="w-4 h-4 text-rose-700 flex-shrink-0" />
                      <span>{clarifyErrorMsg}</span>
                    </div>
                  )}

                  <form onSubmit={handleSubmitClarification} className="space-y-4">
                    {currentCase.clarification.questions.map((q, idx) => (
                      <div key={q.question_id} className="bg-white p-4 rounded-xl border border-amber-200 shadow-sm space-y-2">
                        <div className="flex items-start justify-between">
                          <label className="text-sm font-semibold text-slate-900">
                            Question {idx + 1}: {q.text}
                          </label>
                        </div>
                        {q.reason && (
                          <p className="text-xs text-amber-800 bg-amber-50/80 p-2 rounded-lg border border-amber-100 italic">
                            Reason: {q.reason}
                          </p>
                        )}
                        <textarea
                          rows={2}
                          value={answers[q.question_id] || ''}
                          disabled={isSubmittingClarify}
                          onChange={(e) => {
                            if (isSubmittingClarify) return;
                            setAnswers((prev) => ({
                              ...prev,
                              [q.question_id]: e.target.value,
                            }));
                          }}
                          placeholder="Your answer..."
                          className="w-full text-xs p-3 bg-slate-50 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 focus:bg-white disabled:opacity-50 disabled:cursor-not-allowed"
                        />
                      </div>
                    ))}

                    {/* Supplementary Evidence Attachment for Clarification (UC-01E / Finding 8) */}
                    <div className="bg-white p-4 rounded-xl border border-amber-200 shadow-sm space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <label className="text-xs font-bold text-slate-900 flex items-center space-x-1">
                            <Upload className="w-3.5 h-3.5 text-amber-600" />
                            <span>Attach Supplementary Evidence (Optional)</span>
                          </label>
                          <p className="text-[11px] text-slate-500">
                            Upload photos, barcode images, or receipts requested in clarification.
                          </p>
                        </div>
                        <label className={`px-3 py-1 bg-amber-50 text-amber-800 text-xs font-semibold rounded-lg border border-amber-200 transition-colors flex items-center space-x-1 focus-within:ring-2 focus-within:ring-amber-500 ${isSubmittingClarify ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-amber-100'}`}>
                          <Plus className="w-3 h-3" />
                          <span>Add File</span>
                          {/* Keyboard-reachable, as on the lodgement form. */}
                          <input
                            type="file"
                            multiple
                            accept="image/jpeg,image/png,application/pdf"
                            disabled={isSubmittingClarify}
                            onChange={handleClarificationFileSelect}
                            className="sr-only"
                          />
                        </label>
                      </div>

                      {clarificationFileNotice && (
                        <p role="alert" className="p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-xs break-words">
                          {clarificationFileNotice}
                        </p>
                      )}

                      {clarificationFiles.length > 0 && (
                        <div className="space-y-2">
                          {clarificationFiles.map((item) => (
                            <div
                              key={item.idempotencyKey}
                              className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between text-xs"
                            >
                              <div className="truncate mr-2">
                                <div className="font-semibold text-slate-800 truncate">{item.file.name}</div>
                                <div className="text-[10px] text-slate-400">
                                  {(item.file.size / 1024).toFixed(1)} KB
                                </div>
                              </div>
                              <div className="flex items-center space-x-2">
                                {item.staged ? (
                                  <span className="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full text-[11px] font-semibold flex items-center space-x-1">
                                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                                    <span>Staged</span>
                                  </span>
                                ) : (
                                  <button
                                    type="button"
                                    disabled={item.uploading || isSubmittingClarify}
                                    onClick={() => handleStageClarificationFile(item.idempotencyKey)}
                                    className="px-2 py-0.5 bg-amber-600 hover:bg-amber-700 text-white rounded font-medium text-xs disabled:opacity-50"
                                  >
                                    {item.uploading ? 'Uploading...' : 'Stage File'}
                                  </button>
                                )}
                                <button
                                  type="button"
                                  disabled={isSubmittingClarify}
                                  onClick={() => handleRemoveClarificationFile(item.idempotencyKey)}
                                  aria-label={`Remove ${item.file.name}`}
                                  className="text-slate-400 hover:text-rose-600 p-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
                      <div className="text-xs">
                        {clarificationFiles.some((f) => f.uploading) && (
                          <span className="text-sky-700 font-medium">Uploading supplementary files...</span>
                        )}
                        {clarificationFiles.some((f) => !f.staged && !f.uploading) && (
                          <span className="text-amber-700 font-medium">Please stage or remove all selected files before submitting.</span>
                        )}
                      </div>
                      <button
                        type="submit"
                        disabled={
                          isSubmittingClarify ||
                          isLoadingCase ||
                          clarificationFiles.some((f) => !f.staged || f.uploading)
                        }
                        className="px-6 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold rounded-xl shadow-sm transition-colors flex items-center space-x-2 disabled:opacity-50"
                      >
                        {isSubmittingClarify ? (
                          <>
                            <RefreshCw className="w-4 h-4 animate-spin" />
                            <span>Submitting Clarification...</span>
                          </>
                        ) : (
                          <>
                            <Send className="w-4 h-4" />
                            <span>Submit Answers</span>
                          </>
                        )}
                      </button>
                    </div>
                  </form>
                </div>
              )}

              {/* Statements & History */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
                <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
                  <FileText className="w-5 h-5 text-sky-600" />
                  <span>Customer Statements ({currentCase.statements.length})</span>
                </h3>

                <div className="space-y-3">
                  {currentCase.statements.map((stmt, idx) => (
                    <div
                      key={stmt.statement_id}
                      className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-2"
                    >
                      <div className="flex items-center justify-between text-slate-500">
                        <span className="font-semibold text-slate-700">
                          #{idx + 1} {stmt.kind === 'ORIGINAL' ? 'Your original request' : 'Your additional information'}
                        </span>
                        <span>{formatDate(stmt.submitted_at)}</span>
                      </div>
                      {/* The customer's own words: a long unbroken word wraps, and right-to-left text sets its own direction. */}
                      <p dir="auto" className="text-sm text-slate-800 whitespace-pre-wrap break-words">
                        {stmt.raw_text}
                      </p>
                      {stmt.order_reference && (
                        <div className="text-slate-500">
                          {/* Demo extension (#122 item 5): the contract's CustomerStatement
                              carries no order reference, so this only appears on fixture data. */}
                          Order Ref: <strong className="font-mono text-slate-800">{stmt.order_reference}</strong>{' '}
                          <span className="text-[10px] text-slate-400">(mock fixture)</span>
                        </div>
                      )}
                      {stmt.requested_outcome && (
                        <div className="text-slate-500">
                          Requested Outcome: <strong className="text-slate-800">{formatRequestedOutcome(stmt.requested_outcome)}</strong>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Evidence Files */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
                <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
                  <FileCheck className="w-5 h-5 text-sky-600" />
                  <span>Attached Evidence ({currentCase.evidence.length})</span>
                </h3>

                {downloadError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-xs flex items-center space-x-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>{downloadError}</span>
                  </div>
                )}

                {currentCase.evidence.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No files attached to this case.</p>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {currentCase.evidence.map((ev) => (
                      <div
                        key={ev.evidence_id}
                        className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-xs"
                      >
                        <div className="truncate mr-2">
                          <div className="font-semibold text-slate-800 truncate">{ev.filename}</div>
                          <div className="text-[11px] text-slate-400 font-mono">
                            {ev.media_type} · {((ev.size_bytes || 0) / 1024).toFixed(1)} KB
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleDownloadEvidence(ev)}
                          disabled={downloadingEvId === ev.evidence_id}
                          className="px-2.5 py-1 bg-white hover:bg-slate-100 disabled:opacity-50 text-sky-700 border border-slate-300 rounded-lg flex items-center space-x-1 transition-colors"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>{downloadingEvId === ev.evidence_id ? 'Downloading...' : 'Download'}</span>
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
