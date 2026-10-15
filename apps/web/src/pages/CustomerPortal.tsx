import React, { useState, useEffect } from 'react';
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
  ApiError,
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
} from '../utils/formatters';
import { generateIdempotencyKey } from '../utils/idempotency';

export const CustomerPortal: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'lodge' | 'track'>('lodge');

  // ---------------------------------------------------------
  // Sub-Tab 1: Lodge Request Form State (UC-01)
  // ---------------------------------------------------------
  const [originalMessage, setOriginalMessage] = useState('');
  const [orderReference, setOrderReference] = useState('');
  const [requestedOutcome, setRequestedOutcome] = useState<RequestedOutcome>('REFUND');
  const [selectedFiles, setSelectedFiles] = useState<
    Array<{ file: File; description: string; staged?: StagedEvidence; uploading?: boolean; idempotencyKey: string }>
  >([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [createdCaseResult, setCreatedCaseResult] = useState<CustomerCaseView | null>(null);
  // Idempotency state for case lodgement
  const [pendingLodgementKey, setPendingLodgementKey] = useState<string | null>(null);
  const [lastSubmittedLodgementPayload, setLastSubmittedLodgementPayload] = useState<string | null>(null);

  // ---------------------------------------------------------
  // Sub-Tab 2: Track & Clarify State (UC-01E)
  // ---------------------------------------------------------
  const [searchCaseId, setSearchCaseId] = useState('case_demo_001');
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
  const [pendingClarifyKey, setPendingClarifyKey] = useState<string | null>(null);
  const [lastClarifyPayload, setLastClarifyPayload] = useState<string | null>(null);

  // Protected Evidence Download State (Finding 5)
  const [downloadingEvId, setDownloadingEvId] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Auto-load initial demo case on mount
  useEffect(() => {
    if (activeSubTab === 'track' && searchCaseId) {
      loadCase(searchCaseId);
    }
  }, [activeSubTab]);

  const loadCase = async (caseId: string) => {
    if (!caseId.trim()) return;
    setIsLoadingCase(true);
    setCaseError(null);
    setClarifySuccessMsg(null);
    setClarifyErrorMsg(null);
    try {
      const data = await getCustomerCase(caseId.trim());
      setCurrentCase(data);
      // Initialize answer fields if clarification exists
      if (data.clarification?.questions) {
        const initialAnswers: Record<string, string> = {};
        data.clarification.questions.forEach((q) => {
          initialAnswers[q.question_id] = '';
        });
        setAnswers(initialAnswers);
      }
    } catch (err: unknown) {
      setCurrentCase(null);
      setCaseError(err instanceof ApiError ? `${err.code}: ${err.message}` : 'Failed to fetch case details');
    } finally {
      setIsLoadingCase(false);
    }
  };

  // ---------------------------------------------------------
  // File Upload Handlers
  // ---------------------------------------------------------
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const newFiles = Array.from(e.target.files).map((f) => ({
      file: f,
      description: '',
      // Binding the key at selection time means a lost-response retry of the
      // same file intent reuses the original key (Finding 1).
      idempotencyKey: generateIdempotencyKey('ev_idem'),
    }));
    setSelectedFiles((prev) => [...prev, ...newFiles]);
  };

  const handleStageFile = async (index: number) => {
    const item = selectedFiles[index];
    if (!item || item.staged || item.uploading) return;

    const updated = [...selectedFiles];
    updated[index].uploading = true;
    setSelectedFiles(updated);

    try {
      const staged = await stageEvidence(item.file, item.description || undefined, item.idempotencyKey);
      updated[index].staged = staged;
      updated[index].uploading = false;
      setSelectedFiles([...updated]);
    } catch (err: unknown) {
      updated[index].uploading = false;
      setSelectedFiles([...updated]);
      alert(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
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

    // Reuse idempotency key on lost response/retry if payload is identical (Finding 1)
    let keyToUse = pendingLodgementKey;
    if (!keyToUse || payloadStr !== lastSubmittedLodgementPayload) {
      keyToUse = generateIdempotencyKey('case_idem');
      setPendingLodgementKey(keyToUse);
      setLastSubmittedLodgementPayload(payloadStr);
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const newCase = await createCase(payloadObj, keyToUse);
      setCreatedCaseResult(newCase);
      // Reset form and idempotency state
      setOriginalMessage('');
      setOrderReference('');
      setSelectedFiles([]);
      setPendingLodgementKey(null);
      setLastSubmittedLodgementPayload(null);
    } catch (err: unknown) {
      setSubmitError(err instanceof ApiError ? `[${err.code}] ${err.message}` : 'Failed to lodge return case.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ---------------------------------------------------------
  // Clarification File Upload Handlers (UC-01E / Finding 8)
  // ---------------------------------------------------------
  const handleClarificationFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const newFiles = Array.from(e.target.files).map((f) => ({
      file: f,
      description: '',
      // Same identity handling as UC-01 uploads (Finding 1).
      idempotencyKey: generateIdempotencyKey('ev_idem'),
    }));
    setClarificationFiles((prev) => [...prev, ...newFiles]);
  };

  const handleStageClarificationFile = async (index: number) => {
    const item = clarificationFiles[index];
    if (!item || item.staged || item.uploading) return;

    const updated = [...clarificationFiles];
    updated[index].uploading = true;
    setClarificationFiles(updated);

    try {
      const staged = await stageEvidence(item.file, item.description || undefined, item.idempotencyKey);
      updated[index].staged = staged;
      updated[index].uploading = false;
      setClarificationFiles([...updated]);
    } catch (err: unknown) {
      updated[index].uploading = false;
      setClarificationFiles([...updated]);
      alert(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const handleRemoveClarificationFile = (index: number) => {
    setClarificationFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // ---------------------------------------------------------
  // Clarification Submission (UC-01E / Finding 1 & 8)
  // ---------------------------------------------------------
  const handleSubmitClarification = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentCase || !currentCase.clarification) return;

    const answerList: ClarificationAnswer[] = Object.entries(answers)
      .filter(([_, text]) => text.trim().length > 0)
      .map(([question_id, text]) => ({
        question_id,
        text: text.trim(),
      }));

    if (answerList.length === 0) {
      setClarifyErrorMsg('Please provide an answer to at least one question.');
      return;
    }

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

    try {
      const updated = await submitClarification(currentCase.case_id, wirePayload, keyToUse);
      setCurrentCase(updated);
      setClarifySuccessMsg('Clarification successfully admitted (HTTP 202). Case moved to re-evaluation.');
      setClarificationFiles([]);
      setPendingClarifyKey(null);
      setLastClarifyPayload(null);
    } catch (err: unknown) {
      setClarifyErrorMsg(
        err instanceof ApiError ? `[${err.code}] ${err.message}` : 'Failed to submit clarification.'
      );
    } finally {
      setIsSubmittingClarify(false);
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
      setDownloadError(
        err instanceof ApiError ? `[${err.code}] ${err.message}` : 'Failed to download evidence content'
      );
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
            Lodge return requests with natural language and submit clarification evidence (UC-01 / UC-01E)
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
            Lodge Return (UC-01)
          </button>
          <button
            onClick={() => setActiveSubTab('track')}
            className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all ${
              activeSubTab === 'track'
                ? 'bg-white text-sky-700 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Track & Clarify (UC-01E)
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
                    Your statement has been securely registered in the ReturnOps intake pipeline (HTTP 201 Created).
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-white/80 p-4 rounded-xl border border-emerald-200">
                <div>
                  <div className="text-xs text-slate-500 font-semibold uppercase">Case ID</div>
                  <div className="text-sm font-mono font-bold text-slate-900">{createdCaseResult.case_id}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 font-semibold uppercase">Status</div>
                  <span
                    className={`inline-block mt-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadgeClass(
                      createdCaseResult.status
                    )}`}
                  >
                    {createdCaseResult.status}
                  </span>
                </div>
                <div>
                  <div className="text-xs text-slate-500 font-semibold uppercase">Case Version</div>
                  <div className="text-sm font-mono text-slate-800">v{createdCaseResult.case_version}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 font-semibold uppercase">Submitted At</div>
                  <div className="text-xs text-slate-800">{formatDate(createdCaseResult.created_at)}</div>
                </div>
              </div>

              <div className="flex items-center space-x-3 pt-2">
                <button
                  onClick={() => {
                    setSearchCaseId(createdCaseResult.case_id);
                    setActiveSubTab('track');
                    loadCase(createdCaseResult.case_id);
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
              {submitError && (
                <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm flex items-center space-x-2">
                  <ShieldAlert className="w-5 h-5 text-rose-600 flex-shrink-0" />
                  <span>{submitError}</span>
                </div>
              )}

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
                  onChange={(e) => setOriginalMessage(e.target.value)}
                  placeholder="Tell us what happened with your purchase in your own words (e.g., 'I received a damaged wool sweater with a broken zipper yesterday; ordered size M in Blue')..."
                  className="w-full text-sm p-4 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:bg-white transition-all resize-y"
                />
                <p className="text-xs text-slate-500 mt-1.5 flex items-center space-x-1">
                  <Sparkles className="w-3.5 h-3.5 text-sky-500" />
                  <span>
                    Our autonomous Coordinator & Assessment agents will extract your claim facts and verify order details automatically.
                  </span>
                </p>
              </div>

              {/* Optional Fields Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Order Reference */}
                <div>
                  <label className="block text-sm font-bold text-slate-900 mb-1.5">
                    Order Reference <span className="text-xs font-normal text-slate-500">(Optional)</span>
                  </label>
                  <input
                    type="text"
                    value={orderReference}
                    onChange={(e) => setOrderReference(e.target.value)}
                    placeholder="e.g. ORD-2026-9042"
                    className="w-full text-sm px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:bg-white transition-all font-mono"
                  />
                  <span className="text-[11px] text-slate-400 mt-1 block">
                    If missing, our intake processor can request clarification or search by email.
                  </span>
                </div>

                {/* Requested Outcome */}
                <div>
                  <label className="block text-sm font-bold text-slate-900 mb-1.5">
                    Requested Outcome
                  </label>
                  <select
                    value={requestedOutcome}
                    onChange={(e) => setRequestedOutcome(e.target.value as RequestedOutcome)}
                    className="w-full text-sm px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:bg-white transition-all font-medium text-slate-800"
                  >
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
                      Files are securely staged under F.01 contracts (max 10MB per file, up to 10 files).
                    </p>
                  </div>
                  <label className="cursor-pointer px-3.5 py-1.5 bg-sky-50 hover:bg-sky-100 text-sky-700 text-xs font-semibold rounded-xl border border-sky-200 transition-colors flex items-center space-x-1">
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add File</span>
                    <input
                      type="file"
                      multiple
                      accept="image/jpeg,image/png,application/pdf"
                      onChange={handleFileSelect}
                      className="hidden"
                    />
                  </label>
                </div>

                {selectedFiles.length === 0 ? (
                  <div className="border-2 border-dashed border-slate-200 rounded-xl p-6 text-center text-slate-400 text-xs bg-slate-50/50">
                    No files attached yet. Click "Add File" to attach photos of damaged items, packaging, or receipts.
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {selectedFiles.map((item, idx) => (
                      <div
                        key={idx}
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
                              <span>Staged: {item.staged.evidence_id}</span>
                            </span>
                          ) : (
                            <button
                              type="button"
                              disabled={item.uploading}
                              onClick={() => handleStageFile(idx)}
                              className="px-2.5 py-1 bg-sky-600 hover:bg-sky-700 text-white rounded-lg font-medium text-xs disabled:opacity-50"
                            >
                              {item.uploading ? 'Uploading...' : 'Stage File'}
                            </button>
                          )}

                          <button
                            type="button"
                            onClick={() => handleRemoveFile(idx)}
                            aria-label={`Remove ${item.file.name}`}
                            className="text-slate-400 hover:text-rose-600 p-1"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

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
                      <span>Submit Return Request (HTTP 201)</span>
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
          {/* Lookup Bar */}
          <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex-1 w-full flex items-center space-x-2">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type="text"
                  value={searchCaseId}
                  onChange={(e) => setSearchCaseId(e.target.value)}
                  placeholder="Enter Case ID (e.g. case_demo_001)..."
                  className="w-full pl-10 pr-4 py-2 text-sm bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 font-mono"
                />
              </div>
              <button
                onClick={() => loadCase(searchCaseId)}
                disabled={isLoadingCase || !searchCaseId.trim()}
                className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold rounded-xl transition-colors flex items-center space-x-1.5 disabled:opacity-50"
              >
                {isLoadingCase ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                <span>Lookup</span>
              </button>
            </div>

            {/* Quick Demo Case Selector */}
            <div className="flex items-center space-x-1.5 text-xs text-slate-500">
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
                  <div className="flex items-center space-x-3">
                    <span className="font-mono text-xl font-bold text-slate-900">{currentCase.case_id}</span>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-semibold border ${getStatusBadgeClass(
                        currentCase.status
                      )}`}
                    >
                      {currentCase.status}
                    </span>
                  </div>
                  <div className="flex items-center space-x-4 text-xs text-slate-500">
                    <span>
                      Case Version: <strong className="font-mono text-slate-700">v{currentCase.case_version}</strong>
                    </span>
                    <span>
                      Input Version: <strong className="font-mono text-slate-700">v{currentCase.input_version}</strong>
                    </span>
                    <button
                      onClick={() => loadCase(currentCase.case_id)}
                      className="p-1 hover:text-sky-600 rounded-lg hover:bg-slate-100"
                      title="Refresh Case"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {currentCase.outcome_message && (
                  <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-900 text-sm">
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
                          Supplementary Clarification Requested (UC-01E)
                        </h2>
                        <p className="text-xs text-amber-800 mt-0.5">
                          Question Set ID:{' '}
                          <code className="font-mono font-bold bg-amber-100 px-1 py-0.5 rounded">
                            {currentCase.clarification.question_set_id}
                          </code>
                          {' · '}Please provide additional details to complete your return assessment.
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
                          <span className="text-[10px] bg-slate-100 text-slate-500 font-mono px-1.5 py-0.5 rounded">
                            {q.question_id}
                          </span>
                        </div>
                        {q.reason && (
                          <p className="text-xs text-amber-800 bg-amber-50/80 p-2 rounded-lg border border-amber-100 italic">
                            Reason: {q.reason}
                          </p>
                        )}
                        <textarea
                          rows={2}
                          required
                          value={answers[q.question_id] || ''}
                          onChange={(e) =>
                            setAnswers((prev) => ({
                              ...prev,
                              [q.question_id]: e.target.value,
                            }))
                          }
                          placeholder="Your answer..."
                          className="w-full text-xs p-3 bg-slate-50 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 focus:bg-white"
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
                        <label className="cursor-pointer px-3 py-1 bg-amber-50 hover:bg-amber-100 text-amber-800 text-xs font-semibold rounded-lg border border-amber-200 transition-colors flex items-center space-x-1">
                          <Plus className="w-3 h-3" />
                          <span>Add File</span>
                          <input
                            type="file"
                            multiple
                            accept="image/jpeg,image/png,application/pdf"
                            onChange={handleClarificationFileSelect}
                            className="hidden"
                          />
                        </label>
                      </div>

                      {clarificationFiles.length > 0 && (
                        <div className="space-y-2">
                          {clarificationFiles.map((item, idx) => (
                            <div
                              key={idx}
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
                                    disabled={item.uploading}
                                    onClick={() => handleStageClarificationFile(idx)}
                                    className="px-2 py-0.5 bg-amber-600 hover:bg-amber-700 text-white rounded font-medium text-xs disabled:opacity-50"
                                  >
                                    {item.uploading ? 'Uploading...' : 'Stage File'}
                                  </button>
                                )}
                                <button
                                  type="button"
                                  onClick={() => handleRemoveClarificationFile(idx)}
                                  aria-label={`Remove ${item.file.name}`}
                                  className="text-slate-400 hover:text-rose-600 p-1"
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
                            <span>Submit Supplementary Clarification (HTTP 202)</span>
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
                          #{idx + 1} {stmt.kind === 'ORIGINAL' ? 'Original Lodgement' : 'Supplementary Clarification'}
                        </span>
                        <span>{formatDate(stmt.submitted_at)}</span>
                      </div>
                      <p className="text-sm text-slate-800 whitespace-pre-wrap">{stmt.raw_text}</p>
                      {stmt.order_reference && (
                        <div className="text-slate-500">
                          Order Ref: <strong className="font-mono text-slate-800">{stmt.order_reference}</strong>
                        </div>
                      )}
                      {stmt.requested_outcome && (
                        <div className="text-slate-500">
                          Requested Outcome: <strong className="text-slate-800">{stmt.requested_outcome}</strong>
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
                            {ev.media_type} · {(((ev.size_bytes ?? ev.byte_size) || 0) / 1024).toFixed(1)} KB
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
