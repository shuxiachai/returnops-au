import React, { useState, useEffect, useRef } from 'react';
import {
  ShieldCheck,
  BarChart3,
  Search,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileText,
  Package,
  Activity,
  Lock,
  Eye,
  RefreshCw,
  X,
  TrendingUp,
} from 'lucide-react';
import {
  listFounderCases,
  getFounderCase,
  listFounderCaseAuditPage,
  recordFounderDecision,
  getFounderAnalytics,
  downloadEvidence,
  isMockMode,
  ApiError,
  formatApiError,
} from '../api/client';
import { selectDecisionTarget, describeDecisionError } from '../api/founderDecision';
import { ApprovalScopeExplained } from '../components/ApprovalScopeSummary';
import {
  CaseSummary,
  CaseView,
  CaseStatus,
  AuditEvent,
  AnalyticsQuery,
  AnalyticsSnapshot,
  AiTriage,
  FounderDecisionType,
  FounderDecisionRequest,
} from '../types/domain';
import { generateIdempotencyKey } from '../utils/idempotency';
import { isFinalStatus, usePolling, useRefreshOnReturn } from '../utils/autoRefresh';
import {
  formatDate,
  formatCurrency,
  getStatusBadgeClass,
  getRiskBadgeClass,
  formatActor,
  formatStatusLabel,
  formatRecommendation,
  describeProposalSource,
  formatRequestedOutcome,
} from '../utils/formatters';
import { AdvisoryFactsCard } from '../components/AdvisoryFactsCard';
import {
  AiReplyDraftPanel,
  AiTriagePanel,
  AiWeeklySummaryPanel,
  URGENCY_CLASS,
  URGENCY_LABEL,
} from '../components/AiAssistant';
import { CaseOutcomePanel } from '../components/CaseOutcomePanel';

const AUDIT_PAGE_LIMIT = 50;
const AUDIT_MAX_PAGES = 20;

type DetailTab = 'proposal' | 'order' | 'statements' | 'outcome' | 'audit';

// Contract CaseStatus values in enum order, for the queue and analytics status filters.
const CASE_STATUSES: CaseStatus[] = [
  'SUBMITTED',
  'AWAITING_INFORMATION',
  'UNDER_INVESTIGATION',
  'POLICY_ASSESSMENT',
  'RISK_REVIEW',
  'AWAITING_APPROVAL',
  'APPROVED',
  'ACTION_IN_PROGRESS',
  'ACTION_FAILED',
  'RECONCILING',
  'ESCALATED',
  'NOTIFICATION_PENDING',
  'NOTIFICATION_FAILED',
  'COMPLETED',
  'REJECTED',
  'MANUAL_HANDLED',
];

// The words a decision goes by on screen (31 October 2026); the wire value stays the code.
const DECISION_LABEL: Record<FounderDecisionType, string> = {
  APPROVE: 'Approve return',
  REJECT: 'Reject',
  REQUEST_REVISION: 'Request revision',
  MANUAL_HANDLING: 'Manual takeover',
};

// The two states that wait for the Founder: the queue lists them first and marks them.
const NEEDS_FOUNDER: CaseStatus[] = ['AWAITING_APPROVAL', 'ESCALATED'];

// Who the case is waiting on, in one sentence at the top of the case window.
function nextStep(status: CaseStatus): string {
  switch (status) {
    case 'AWAITING_APPROVAL':
      return 'Your decision is needed.';
    case 'ESCALATED':
      return 'Your decision is needed: nothing automatic may decide this case.';
    case 'AWAITING_INFORMATION':
      return "Waiting for the customer's answers.";
    case 'SUBMITTED':
    case 'UNDER_INVESTIGATION':
    case 'POLICY_ASSESSMENT':
      return 'The system is preparing the case; nothing is needed from you yet.';
    case 'RISK_REVIEW':
      // Gate 1 has no independent reviewer yet (docs/46), so such a case waits here.
      return 'Waiting for the independent risk review, which this version does not run yet (Gate 2); nothing is needed from you.';
    case 'APPROVED':
    case 'ACTION_IN_PROGRESS':
    case 'RECONCILING':
      return 'Your decision is being carried out.';
    case 'NOTIFICATION_PENDING':
      return 'The customer is being notified.';
    case 'ACTION_FAILED':
    case 'NOTIFICATION_FAILED':
      return 'A step after the decision failed; see Decision & Outcome.';
    default:
      return 'Closed.';
  }
}

function excerpt(text: string, limit = 160): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  return flat.length > limit ? `${flat.slice(0, limit - 1)}…` : flat;
}

// The analytics dates are typed as YYYY-MM-DD: the browser's own date picker shows
// its format in the browser's language (年/月/日 in a Chinese browser).
function isUtcDate(text: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return false;
  const day = new Date(`${text}T00:00:00Z`);
  return !Number.isNaN(day.getTime()) && day.toISOString().slice(0, 10) === text;
}

export const FounderConsole: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'queue' | 'analytics'>('queue');

  // ---------------------------------------------------------
  // Case Queue State & Pagination (UC-03 / Finding 6)
  // ---------------------------------------------------------
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  // The server binds a cursor to the page size it was issued with (founder_queries.resume),
  // so the next page is read with the limit that produced nextCursor, not a fixed 20.
  const [nextCursorLimit, setNextCursorLimit] = useState(20);
  const [isLoadingCases, setIsLoadingCases] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  // The Founder AI assistant's triage (31 October 2026): advisory marks and an optional group filter.
  const [aiTriage, setAiTriage] = useState<AiTriage | null>(null);
  const [aiGroup, setAiGroup] = useState<{ label: string; caseIds: string[] } | null>(null);
  // The triage panel lives on the queue tab; leaving it ends the triage and its group filter,
  // which would otherwise keep hiding cases with no way to clear it (runtime review).
  useEffect(() => {
    if (activeSubTab !== 'queue') {
      setAiTriage(null);
      setAiGroup(null);
    }
  }, [activeSubTab]);

  // Selected Case Detail Modal State
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [caseDetail, setCaseDetail] = useState<CaseView | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [auditError, setAuditError] = useState<string | null>(null);
  // The chain is longer than this view reads; the events shown are still real.
  const [auditOverflow, setAuditOverflow] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [detailTab, setDetailTab] = useState<DetailTab>('proposal');
  // A case that cannot be opened is reported on the page, not in a browser alert.
  const [caseOpenError, setCaseOpenError] = useState<string | null>(null);
  // An accepted decision whose follow-up read failed: the decision still stands.
  const [decisionNotice, setDecisionNotice] = useState<string | null>(null);
  // Only the latest read of the open case may update it (#111 item 2).
  const selectedCaseRef = useRef<string | null>(null);
  const detailLoad = useRef(0);
  const detailPollBusy = useRef(false);
  // Customer evidence download (#122 item 5): the list is useless without it.
  const [downloadingEvidence, setDownloadingEvidence] = useState<string | null>(null);
  const [evidenceDownloadError, setEvidenceDownloadError] = useState<string | null>(null);

  // Decision Modal State (UC-04 / UC-03)
  const [decisionModalOpen, setDecisionModalOpen] = useState(false);
  const [pendingDecision, setPendingDecision] = useState<FounderDecisionType>('APPROVE');
  const [decisionReason, setDecisionReason] = useState('');
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  // This browser's reading of the preview's expiry. Only APPROVE depends on a
  // preview: reject, revision and manual takeover are still valid on the same
  // case, so this must never disable them (review round 2, finding 1).
  const previewExpiresAt = caseDetail?.action_preview?.scope?.expires_at;
  const previewExpired = Boolean(previewExpiresAt) && Date.parse(previewExpiresAt as string) <= Date.now();
  // Idempotency state for the decision POST, as in the customer intake form
  const [pendingDecisionKey, setPendingDecisionKey] = useState<string | null>(null);
  const [lastDecisionPayload, setLastDecisionPayload] = useState<string | null>(null);

  // ---------------------------------------------------------
  // Operations Analytics State (OF-006)
  // ---------------------------------------------------------
  const [analytics, setAnalytics] = useState<AnalyticsSnapshot | null>(null);
  const [isLoadingAnalytics, setIsLoadingAnalytics] = useState(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  // Applied query, plus the filter form fields (dates are YYYY-MM-DD or '')
  const [analyticsQuery, setAnalyticsQuery] = useState<AnalyticsQuery>({});
  const [filterFrom, setFilterFrom] = useState('');
  const [filterBefore, setFilterBefore] = useState('');
  const [filterStatus, setFilterStatus] = useState<CaseStatus | ''>('');
  const [filterError, setFilterError] = useState<string | null>(null);

  useEffect(() => {
    if (activeSubTab === 'queue') {
      loadCases();
    } else {
      loadAnalytics(analyticsQuery);
    }
  }, [activeSubTab]);

  // Each queue read is numbered; a reply that a newer read has overtaken is dropped, so an
  // older list can never replace a newer one (runtime review, 31 October 2026).
  const queueLoad = useRef(0);

  const loadCases = async (limit = 20) => {
    const load = ++queueLoad.current;
    setIsLoadingCases(true);
    setQueueError(null);
    try {
      const data = await listFounderCases(undefined, limit);
      if (load !== queueLoad.current) return;
      setCases(data.items);
      setNextCursor(data.next_cursor || null);
      setNextCursorLimit(limit);
    } catch (err: unknown) {
      if (load !== queueLoad.current) return;
      setQueueError(err instanceof ApiError ? formatApiError(err) : 'Failed to load case queue');
    } finally {
      if (load === queueLoad.current) setIsLoadingCases(false);
    }
  };

  const loadMoreCases = async () => {
    if (!nextCursor || isLoadingMore) return;
    setIsLoadingMore(true);
    const limit = nextCursorLimit;
    const load = queueLoad.current;
    try {
      const data = await listFounderCases(nextCursor, limit);
      // A reload started meanwhile: this page belongs to the old list.
      if (load !== queueLoad.current) return;
      setCases((prev) => [...prev, ...data.items]);
      setNextCursor(data.next_cursor || null);
      setNextCursorLimit(limit);
    } catch (err: unknown) {
      setQueueError(err instanceof ApiError ? formatApiError(err) : 'Failed to load next page');
    } finally {
      setIsLoadingMore(false);
    }
  };

  const handleStatusFilterChange = (newStatus: string) => {
    setStatusFilter(newStatus);
  };

  const loadAnalytics = async (query: AnalyticsQuery) => {
    setIsLoadingAnalytics(true);
    setAnalyticsError(null);
    try {
      const data = await getFounderAnalytics(query);
      setAnalytics(data);
    } catch (err: unknown) {
      setAnalyticsError(err instanceof ApiError ? formatApiError(err) : 'Failed to load analytics');
      setAnalytics(null);
    } finally {
      setIsLoadingAnalytics(false);
    }
  };

  const applyAnalyticsFilters = (e: React.FormEvent) => {
    e.preventDefault();
    const from = filterFrom.trim();
    const before = filterBefore.trim();
    for (const [label, text] of [['Created from', from], ['Created before', before]] as const) {
      if (text && !isUtcDate(text)) {
        setFilterError(`"${label}" must be a date written as YYYY-MM-DD, for example 2026-11-01.`);
        return;
      }
    }
    // YYYY-MM-DD strings compare correctly as text; the contract needs from < before.
    if (from && before && from >= before) {
      setFilterError('"Created from" must be earlier than "Created before".');
      return;
    }
    setFilterError(null);
    // Whole UTC days: the window is [from 00:00Z, before 00:00Z).
    const query: AnalyticsQuery = {};
    if (from) query.created_from = `${from}T00:00:00Z`;
    if (before) query.created_before = `${before}T00:00:00Z`;
    if (filterStatus) query.status = filterStatus;
    setAnalyticsQuery(query);
    loadAnalytics(query);
  };

  const clearAnalyticsFilters = () => {
    setFilterFrom('');
    setFilterBefore('');
    setFilterStatus('');
    setFilterError(null);
    setAnalyticsQuery({});
    loadAnalytics({});
  };

  const describeApiError = (err: unknown, fallback: string) =>
    err instanceof ApiError ? formatApiError(err) : err instanceof Error ? err.message : fallback;

  // #122 item 13: read every page of the chain, with a bound, so a long case is
  // not silently truncated to its first page. Overflow is shown as an error rather
  // than passed off as the whole chain.
  const loadWholeAuditChain = async (
    caseId: string
  ): Promise<{ events: AuditEvent[]; overflow: boolean }> => {
    const events: AuditEvent[] = [];
    let cursor: string | undefined;
    for (let page = 0; page < AUDIT_MAX_PAGES; page += 1) {
      const result = await listFounderCaseAuditPage(caseId, cursor, AUDIT_PAGE_LIMIT);
      events.push(...(result.items ?? []));
      const next = result.next_cursor;
      // A repeated cursor or a page that adds nothing ends the read instead of
      // spending the whole bound on the same page.
      if (!next || next === cursor || (result.items ?? []).length === 0) {
        return { events, overflow: false };
      }
      cursor = next;
    }
    // Longer than this view reads: say so, and keep the events already shown rather
    // than replacing them with an error.
    return { events, overflow: true };
  };

  const applyAuditResult = (
    auditResult: PromiseSettledResult<{ events: AuditEvent[]; overflow: boolean }>
  ) => {
    if (auditResult.status === 'fulfilled') {
      setAuditEvents(auditResult.value.events);
      setAuditOverflow(auditResult.value.overflow);
      setAuditError(null);
    } else {
      setAuditEvents([]);
      setAuditOverflow(false);
      setAuditError(describeApiError(auditResult.reason, 'Failed to fetch audit events'));
    }
  };

  // Resolves to why the case could not be opened, or null once it is shown (or a
  // later open has taken over).
  const openCaseDetail = async (caseId: string, tab: DetailTab = 'proposal'): Promise<string | null> => {
    const load = ++detailLoad.current;
    selectedCaseRef.current = caseId;
    setSelectedCaseId(caseId);
    setCaseOpenError(null);
    setDecisionNotice(null);
    setIsLoadingDetail(true);
    setDetailTab(tab);
    setAuditError(null);
    setAuditEvents([]);
    setAuditOverflow(false);
    setEvidenceDownloadError(null);
    try {
      const [detailResult, auditResult] = await Promise.allSettled([
        getFounderCase(caseId),
        loadWholeAuditChain(caseId),
      ]);
      if (load !== detailLoad.current) return null;

      if (detailResult.status === 'fulfilled') {
        setCaseDetail(detailResult.value);
      } else {
        const reason = describeApiError(detailResult.reason, 'Failed to fetch case detail');
        setCaseOpenError(`Could not open ${caseId}: ${reason}`);
        selectedCaseRef.current = null;
        setSelectedCaseId(null);
        return reason;
      }
      applyAuditResult(auditResult);
      return null;
    } finally {
      if (load === detailLoad.current) setIsLoadingDetail(false);
    }
  };

  // Customer evidence download (#122 item 5). A refused download is shown on the
  // page with the server's code, as everywhere else in this console.
  const handleDownloadEvidence = async (evidenceId: string, filename: string) => {
    setDownloadingEvidence(evidenceId);
    setEvidenceDownloadError(null);
    try {
      await downloadEvidence(evidenceId, filename);
    } catch (err: unknown) {
      const text = err instanceof ApiError ? formatApiError(err) : 'The evidence file could not be downloaded.';
      setEvidenceDownloadError(`${filename}: ${text}`);
    } finally {
      setDownloadingEvidence(null);
    }
  };

  // Reads the open case again without the loading screen, keeping the current
  // tab. Returns whether the case view was updated.
  const reloadCaseDetail = async (caseId: string): Promise<boolean> => {
    const load = ++detailLoad.current;
    const [detailResult, auditResult] = await Promise.allSettled([
      getFounderCase(caseId),
      loadWholeAuditChain(caseId),
    ]);
    if (load !== detailLoad.current || selectedCaseRef.current !== caseId) return false;
    if (detailResult.status !== 'fulfilled') return false;
    setCaseDetail(detailResult.value);
    applyAuditResult(auditResult);
    return true;
  };

  const closeCaseDetail = () => {
    detailLoad.current += 1;
    selectedCaseRef.current = null;
    setSelectedCaseId(null);
    // Escape can close the window while it is still loading; the discarded read
    // must not leave the next case stuck on the loading screen.
    setIsLoadingDetail(false);
  };

  // Escape closes the top window: the decision dialog first, then the case. It does
  // nothing while a decision is being sent, so its outcome cannot be hidden.
  useEffect(() => {
    if (!selectedCaseId && !decisionModalOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || isSubmittingDecision) return;
      if (decisionModalOpen) setDecisionModalOpen(false);
      else closeCaseDetail();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectedCaseId, decisionModalOpen, isSubmittingDecision]);

  // #111 item 2: the open case is read again every 5 s until it reaches a final
  // status. Polling pauses while a decision is being confirmed, so the version the
  // Founder confirms is the one on screen.
  const refreshOpenCase = () => {
    if (!selectedCaseId || !caseDetail || isLoadingDetail || decisionModalOpen || isSubmittingDecision) return;
    if (detailPollBusy.current) return;
    detailPollBusy.current = true;
    reloadCaseDetail(selectedCaseId).finally(() => {
      detailPollBusy.current = false;
    });
  };

  const pollingOpenCase =
    selectedCaseId !== null &&
    caseDetail !== null &&
    caseDetail.case_id === selectedCaseId &&
    !isLoadingDetail &&
    !decisionModalOpen &&
    !isSubmittingDecision &&
    !isFinalStatus(caseDetail.status);
  usePolling(refreshOpenCase, pollingOpenCase);

  // Coming back to the window reloads the queue (a case lodged meanwhile appears)
  // and the open case.
  useRefreshOnReturn(() => {
    if (activeSubTab === 'queue' && !isLoadingCases && !isLoadingMore) {
      loadCases(Math.min(100, Math.max(20, cases.length)));
    }
    refreshOpenCase();
  });

  const handleOpenDecision = (decisionType: FounderDecisionType) => {
    // The confirmation binds the case view on screen now. A background read still
    // in flight is discarded, so it cannot replace that view behind the dialog
    // (C's review of #130); a changed case then comes back as a 409 and reloads.
    detailLoad.current += 1;
    setPendingDecision(decisionType);
    setDecisionReason('');
    setDecisionError(null);
    setDecisionModalOpen(true);
  };

  const handleConfirmDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseDetail) return;
    if (!decisionReason.trim()) {
      setDecisionError('Please provide a decision rationale.');
      return;
    }

    const selected = selectDecisionTarget(caseDetail, pendingDecision);
    if ('unavailable' in selected) {
      setDecisionError(selected.unavailable);
      return;
    }
    const payload: FounderDecisionRequest = {
      expected_case_version: caseDetail.case_version,
      decision: pendingDecision,
      reason: decisionReason.trim(),
      ...selected.target,
    };

    // Reuse the key while the case and body are unchanged (a retry after a lost
    // response or a 503); mint a new one when the intent changes.
    const payloadStr = JSON.stringify({ case_id: caseDetail.case_id, payload });
    let keyToUse = pendingDecisionKey;
    if (!keyToUse || payloadStr !== lastDecisionPayload) {
      keyToUse = generateIdempotencyKey('decision_idem');
      setPendingDecisionKey(keyToUse);
      setLastDecisionPayload(payloadStr);
    }

    setIsSubmittingDecision(true);
    setDecisionError(null);

    try {
      const receipt = await recordFounderDecision(caseDetail.case_id, payload, keyToUse);

      setPendingDecisionKey(null);
      setLastDecisionPayload(null);
      setDecisionModalOpen(false);
      // Reload detail and queue; the Founder lands on what the decision produced.
      const reloadFailure = await openCaseDetail(caseDetail.case_id, 'outcome');
      if (reloadFailure) {
        // The receipt is the server's acceptance. A failed read after it must not
        // read as a failed decision, or invite the Founder to decide again.
        setCaseOpenError(null);
        setDecisionNotice(
          `Decision recorded: the server accepted ${receipt.decision} on ${receipt.case_id} (decision ${receipt.decision_id}). The case view could not be refreshed: ${reloadFailure} Open the case again to see its current state.`
        );
      }
      loadCases();
    } catch (err: unknown) {
      if (err instanceof ApiError && err.code === 'STALE_CASE_VERSION') {
        // #122 item 2 (docs/09 error table, docs/08 B2.04): a stale window's refused
        // decision reloads the current case and its audit behind the dialog.
        const reloaded = await reloadCaseDetail(caseDetail.case_id);
        setDecisionError(
          `${describeDecisionError(err)} ${
            reloaded
              ? 'The case changed; the view was reloaded. Check it and decide again.'
              : 'The case changed, but reloading it failed. Close this dialog and open the case again.'
          }`
        );
        if (reloaded) loadCases(Math.min(100, Math.max(20, cases.length)));
      } else {
        setDecisionError(describeDecisionError(err));
      }
    } finally {
      setIsSubmittingDecision(false);
    }
  };

  // Why a decision cannot be built from the current case view, or null if it can.
  const decisionUnavailable = (decision: FounderDecisionType): string | null => {
    if (!caseDetail) return 'No case is loaded.';
    const selected = selectDecisionTarget(caseDetail, decision);
    return 'unavailable' in selected ? selected.unavailable : null;
  };

  const searchText = searchFilter.trim().toLowerCase();
  const aiUrgency = new Map((aiTriage?.cases ?? []).map((item) => [item.case_id, item]));
  const filteredCases = cases
    .filter((c) => {
      // The status matches by its value and by the words the table shows for it.
      const matchesSearch =
        c.case_id.toLowerCase().includes(searchText) ||
        c.status.toLowerCase().includes(searchText) ||
        formatStatusLabel(c.status).toLowerCase().includes(searchText);
      const matchesStatus = statusFilter === 'ALL' || c.status === statusFilter;
      const matchesGroup = !aiGroup || aiGroup.caseIds.includes(c.case_id);
      return matchesSearch && matchesStatus && matchesGroup;
    })
    // Cases that wait for the Founder first, then the most recently updated (31 October 2026).
    .map((c, index) => ({ c, index }))
    .sort((a, b) => {
      const waiting = Number(NEEDS_FOUNDER.includes(b.c.status)) - Number(NEEDS_FOUNDER.includes(a.c.status));
      if (waiting !== 0) return waiting;
      const updated = Date.parse(b.c.updated_at) - Date.parse(a.c.updated_at);
      return Number.isNaN(updated) || updated === 0 ? a.index - b.index : updated;
    })
    .map(({ c }) => c);

  // The four tiles filter the queue; each shows how many loaded cases it holds.
  const tiles: { label: string; filter: string; count: number; tone: string }[] = [
    { label: 'All cases', filter: 'ALL', count: cases.length, tone: 'border-slate-200 text-slate-500 text-slate-900' },
    {
      label: 'Needs your approval',
      filter: 'AWAITING_APPROVAL',
      count: cases.filter((c) => c.status === 'AWAITING_APPROVAL').length,
      tone: 'border-purple-200 text-purple-700 text-purple-900',
    },
    {
      label: 'In risk review',
      filter: 'RISK_REVIEW',
      count: cases.filter((c) => c.status === 'RISK_REVIEW').length,
      tone: 'border-indigo-200 text-indigo-700 text-indigo-900',
    },
    {
      label: 'Escalated',
      filter: 'ESCALATED',
      count: cases.filter((c) => c.status === 'ESCALATED').length,
      tone: 'border-rose-200 text-rose-700 text-rose-900',
    },
  ];

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-200 pb-4 gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Founder Console</h1>
            {isMockMode() && (
              <span className="bg-sky-100 text-sky-800 text-xs px-2.5 py-0.5 rounded-full font-semibold">
                Sample store
              </span>
            )}
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Review cases, record decisions and follow the operations numbers for your store.
          </p>
        </div>

        {/* Sub-Tabs */}
        <div className="flex bg-slate-100 p-1 rounded-xl">
          <button
            onClick={() => setActiveSubTab('queue')}
            className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all flex items-center space-x-1.5 ${
              activeSubTab === 'queue' ? 'bg-white text-sky-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>Case Queue & Review</span>
          </button>
          <button
            onClick={() => setActiveSubTab('analytics')}
            className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all flex items-center space-x-1.5 ${
              activeSubTab === 'analytics'
                ? 'bg-white text-sky-700 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            <span>Analytics Dashboard</span>
          </button>
        </div>
      </div>

      {/* ========================================================= */}
      {/* SUB-TAB 1: Case Queue & Review (UC-03 / UC-05 / UC-04)     */}
      {/* ========================================================= */}
      {activeSubTab === 'queue' && (
        <div className="space-y-6">
          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {tiles.map((tile) => {
              const [border, labelColour, countColour] = tile.tone.split(' ');
              const active = statusFilter === tile.filter;
              return (
                <button
                  key={tile.filter}
                  type="button"
                  onClick={() => handleStatusFilterChange(tile.filter)}
                  aria-pressed={active}
                  className={`text-left bg-white p-4 rounded-2xl border shadow-sm transition-colors hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-sky-500 ${border} ${
                    active ? 'ring-2 ring-sky-500' : ''
                  }`}
                >
                  <div className={`text-xs font-semibold uppercase tracking-wider ${labelColour}`}>{tile.label}</div>
                  <div className={`text-2xl font-bold mt-1 ${countColour}`}>
                    {tile.count}
                    {tile.filter === 'ALL' && nextCursor ? '+' : ''}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Filter Bar */}
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="relative flex-1 w-full">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Search by case ID or status..."
                aria-label="Search the queue by case ID or status"
                className="w-full pl-10 pr-4 py-2 text-sm bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500"
              />
            </div>

            <div className="flex items-center space-x-2 w-full sm:w-auto">
              <select
                value={statusFilter}
                onChange={(e) => handleStatusFilterChange(e.target.value)}
                aria-label="Filter the queue by status"
                className="text-xs font-semibold px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-700 focus:ring-2 focus:ring-sky-500"
              >
                <option value="ALL">All Statuses</option>
                {/* All sixteen contract statuses, so a case in any state can be found
                    (#111 item 9); the old list offered seven. */}
                {CASE_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {formatStatusLabel(status)}
                  </option>
                ))}
              </select>

              <button
                onClick={() => loadCases()}
                disabled={isLoadingCases || isLoadingMore}
                className="px-3 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition-colors flex items-center space-x-1.5"
                title="Refresh the queue (it also refreshes when you come back to this window)"
              >
                <RefreshCw className={`w-4 h-4 ${isLoadingCases ? 'animate-spin' : ''}`} />
                <span>Refresh</span>
              </button>
            </div>
          </div>

          {queueError && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-sm flex items-center space-x-2">
              <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
              <span>{queueError}</span>
            </div>
          )}

          {caseOpenError && (
            <div
              role="alert"
              className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-sm flex items-center justify-between gap-3"
            >
              <span className="flex items-center space-x-2">
                <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
                <span>{caseOpenError}</span>
              </span>
              <button
                type="button"
                onClick={() => setCaseOpenError(null)}
                aria-label="Dismiss"
                className="text-rose-500 hover:text-rose-700 p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {decisionNotice && (
            <div
              role="status"
              className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-emerald-900 text-sm flex items-center justify-between gap-3"
            >
              <span className="flex items-center space-x-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <span>{decisionNotice}</span>
              </span>
              <button
                type="button"
                onClick={() => setDecisionNotice(null)}
                aria-label="Dismiss"
                className="text-emerald-600 hover:text-emerald-800 p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          <AiTriagePanel
            onTriage={(triage) => {
              setAiTriage(triage);
              setAiGroup(null);
            }}
            activeGroup={aiGroup?.label ?? null}
            onGroup={(label, caseIds) => setAiGroup(label && caseIds ? { label, caseIds } : null)}
            onInspect={(caseId) => openCaseDetail(caseId)}
          />

          {aiGroup && (
            <div role="status" className="px-4 py-2 bg-violet-50 border border-violet-200 rounded-xl text-xs text-violet-900 flex flex-wrap items-center justify-between gap-2">
              <span>
                Showing only the AI group {aiGroup.label} ({filteredCases.length} of {cases.length} cases).
              </span>
              <button
                type="button"
                onClick={() => setAiGroup(null)}
                className="px-2 py-1 font-semibold rounded-lg hover:bg-violet-100"
              >
                Show all cases
              </button>
            </div>
          )}

          {/* Cases Table */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            {/* The table scrolls sideways inside the card and the Actions column stays
                pinned, so a narrow window never hides Inspect. */}
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="px-6 py-3.5">Case ID</th>
                    <th className="px-4 py-3.5">Status</th>
                    <th className="px-4 py-3.5">Risk Outcome</th>
                    <th className="px-4 py-3.5">Updated</th>
                    <th className="px-6 py-3.5 text-right sticky right-0 bg-slate-50">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {filteredCases.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-8 text-center text-slate-400">
                        {isLoadingCases
                          ? 'Loading case queue...'
                          : cases.length > 0
                            ? 'No matching cases found.'
                            : queueError
                              ? 'The queue could not be read; see the message above.'
                              : 'No cases in the queue yet.'}
                      </td>
                    </tr>
                  ) : (
                    filteredCases.map((c) => (
                      <tr
                        key={c.case_id}
                        className={`group transition-colors ${
                          NEEDS_FOUNDER.includes(c.status) ? 'bg-amber-50/60 hover:bg-amber-50' : 'hover:bg-slate-50/80'
                        }`}
                      >
                        <td
                          className={`px-6 py-4 font-mono font-bold text-slate-900 whitespace-nowrap border-l-4 ${
                            NEEDS_FOUNDER.includes(c.status) ? 'border-amber-400' : 'border-transparent'
                          }`}
                        >
                          {/* A server case ID is 37 characters; the full ID is on hover and in the case window. */}
                          <span className="block max-w-[12rem] truncate" title={c.case_id}>
                            {c.case_id}
                          </span>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span
                            title={c.status}
                            className={`px-2.5 py-0.5 rounded-full font-semibold border ${getStatusBadgeClass(
                              c.status
                            )}`}
                          >
                            {formatStatusLabel(c.status)}
                          </span>
                          {NEEDS_FOUNDER.includes(c.status) && (
                            <span className="ml-2 text-[11px] font-semibold text-amber-700">Needs you</span>
                          )}
                          {aiUrgency.has(c.case_id) && (
                            <span
                              title={`AI triage: ${aiUrgency.get(c.case_id)!.reason}`}
                              className={`ml-2 px-2 py-0.5 rounded-full border text-[11px] font-semibold ${
                                URGENCY_CLASS[aiUrgency.get(c.case_id)!.urgency]
                              }`}
                            >
                              AI: {URGENCY_LABEL[aiUrgency.get(c.case_id)!.urgency]}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          {c.current_risk_outcome ? (
                            <span
                              className={`px-2 py-0.5 rounded-full font-semibold border text-[11px] ${getRiskBadgeClass(
                                c.current_risk_outcome
                              )}`}
                            >
                              {c.current_risk_outcome}
                            </span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                        <td className="px-4 py-4 text-slate-500 whitespace-nowrap">{formatDate(c.updated_at)}</td>
                        <td
                          className={`px-6 py-4 text-right whitespace-nowrap sticky right-0 ${
                            NEEDS_FOUNDER.includes(c.status) ? 'bg-amber-50 group-hover:bg-amber-50' : 'bg-white group-hover:bg-slate-50'
                          }`}
                        >
                          <button
                            onClick={() => openCaseDetail(c.case_id)}
                            className="px-3.5 py-1.5 bg-sky-50 hover:bg-sky-100 text-sky-700 font-semibold rounded-lg border border-sky-200 transition-colors flex items-center space-x-1 ml-auto"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>Inspect</span>
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls (Finding 6) */}
            <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-500">
              <div>
                Showing <strong className="text-slate-700">{filteredCases.length}</strong> of{' '}
                <strong className="text-slate-700">{cases.length}</strong> loaded case(s)
                {(statusFilter !== 'ALL' || searchFilter.trim().length > 0) && ' matching the active filter'}
                {nextCursor
                  ? ' · more records available in store (load the next page to search them)'
                  : ' · all cases loaded'}
              </div>
              {nextCursor && (
                <button
                  type="button"
                  onClick={loadMoreCases}
                  disabled={isLoadingMore}
                  className="px-4 py-1.5 bg-white hover:bg-slate-100 disabled:opacity-50 text-sky-700 font-semibold border border-slate-300 rounded-lg flex items-center space-x-1.5 transition-colors shadow-sm"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoadingMore ? 'animate-spin' : ''}`} />
                  <span>{isLoadingMore ? 'Loading more cases...' : 'Load more cases'}</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* CASE INSPECTION MODAL (UC-03 / UC-05 / UC-04)             */}
      {/* ========================================================= */}
      {selectedCaseId && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Case ${selectedCaseId}`}
          className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4"
        >
          {isLoadingDetail || !caseDetail ? (
            <div className="bg-white rounded-2xl p-8 flex items-center space-x-3 shadow-2xl">
              <RefreshCw className="w-5 h-5 text-sky-600 animate-spin" />
              <span className="text-sm font-semibold text-slate-700">Loading case details...</span>
            </div>
          ) : (
            // min-w-0 lets the window shrink to a phone screen instead of growing to its widest row.
            <div className="bg-white rounded-2xl max-w-4xl w-full min-w-0 shadow-2xl border border-slate-200 max-h-[90vh] flex flex-col overflow-hidden">
            {/* Modal Header: the 37-character case ID and the badges wrap on a narrow screen. */}
            <div className="px-6 py-4 border-b border-slate-100 flex items-start justify-between gap-3 bg-slate-50 flex-shrink-0">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 min-w-0">
                <span className="font-mono text-lg font-bold text-slate-900 break-all">{caseDetail.case_id}</span>
                <span
                  title={caseDetail.status}
                  className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadgeClass(
                    caseDetail.status
                  )}`}
                >
                  {formatStatusLabel(caseDetail.status)}
                </span>
                {pollingOpenCase && (
                  <span className="flex items-center gap-1 text-[11px] text-emerald-700" title="Updates every 5 seconds">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
                    <span aria-hidden="true">Live</span>
                    <span className="sr-only">Updates every 5 seconds</span>
                  </span>
                )}
              </div>
              <button
                onClick={closeCaseDetail}
                aria-label="Close case"
                // Keyboard focus starts inside the window rather than on the queue behind it.
                autoFocus
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* What the case is and who it waits on, before any tab (31 October 2026). */}
            <div className="px-6 py-3 border-b border-slate-100 bg-white text-sm space-y-1 flex-shrink-0">
              <p className="text-slate-800">
                <span className="font-semibold">Next step:</span> {nextStep(caseDetail.status)}
              </p>
              {(() => {
                const original = caseDetail.statements.find((s) => s.kind === 'ORIGINAL');
                if (!original) return null;
                const wants = original.requested_outcome && original.requested_outcome !== 'UNSPECIFIED'
                  ? formatRequestedOutcome(original.requested_outcome)
                  : null;
                return (
                  <p className="text-slate-600 break-words" dir="auto">
                    <span className="font-semibold text-slate-700">Customer wrote:</span>{' '}
                    <span>{`“${excerpt(original.raw_text)}”`}</span>
                    {wants && <span className="text-slate-500">{` · wants ${wants.toLowerCase()}`}</span>}
                  </p>
                );
              })()}
              {caseDetail.order_snapshot && (
                <p className="text-slate-600">
                  <span className="font-semibold text-slate-700">Order:</span>
                  {` ${caseDetail.order_snapshot.order_id}, bought ${formatDate(caseDetail.order_snapshot.purchased_at)}`}
                </p>
              )}
            </div>

            {/* Modal Nav Tabs: a tablist that scrolls sideways when it is wider than the screen. */}
            <div
              role="tablist"
              aria-label="Case views"
              className="px-6 border-b border-slate-200 bg-white flex space-x-6 text-xs font-semibold flex-shrink-0 overflow-x-auto"
            >
              <button
                type="button"
                role="tab"
                aria-selected={detailTab === 'proposal'}
                onClick={() => setDetailTab('proposal')}
                className={`py-3 border-b-2 transition-all flex items-center space-x-1.5 ${
                  detailTab === 'proposal'
                    ? 'border-sky-600 text-sky-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <Activity className="w-4 h-4" />
                <span>Proposal & Risk Review</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={detailTab === 'order'}
                onClick={() => setDetailTab('order')}
                className={`py-3 border-b-2 transition-all flex items-center space-x-1.5 ${
                  detailTab === 'order'
                    ? 'border-sky-600 text-sky-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <Package className="w-4 h-4" />
                <span>Order & Facts</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={detailTab === 'statements'}
                onClick={() => setDetailTab('statements')}
                className={`py-3 border-b-2 transition-all flex items-center space-x-1.5 ${
                  detailTab === 'statements'
                    ? 'border-sky-600 text-sky-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <FileText className="w-4 h-4" />
                <span>Customer Statements ({caseDetail.statements.length})</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={detailTab === 'outcome'}
                onClick={() => setDetailTab('outcome')}
                className={`py-3 border-b-2 transition-all flex items-center space-x-1.5 ${
                  detailTab === 'outcome'
                    ? 'border-sky-600 text-sky-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Decision & Outcome</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={detailTab === 'audit'}
                onClick={() => setDetailTab('audit')}
                className={`py-3 border-b-2 transition-all flex items-center space-x-1.5 ${
                  detailTab === 'audit'
                    ? 'border-sky-600 text-sky-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <Lock className="w-4 h-4" />
                <span>Audit History</span>
              </button>
            </div>

            {/* Modal Content Scroll Area */}
            <div className="p-6 overflow-y-auto flex-1 space-y-6">
              {/* Tab: Proposal & Risk */}
              {detailTab === 'proposal' && (
                <div className="space-y-6">
                  {/* Why an escalated case has no proposal (contract OrderLookupBlock / ProcessingFailure).
                      The server's message is shown as plain text. */}
                  {caseDetail.order_lookup_block && (
                    <div className="p-4 bg-rose-50 rounded-2xl border border-rose-200 text-xs space-y-1.5">
                      <div className="flex items-center space-x-2 text-rose-900 font-bold text-sm">
                        <AlertTriangle className="w-4 h-4 text-rose-600" />
                        <span>
                          Order lookup blocked:{' '}
                          {caseDetail.order_lookup_block.status === 'CONFLICT'
                            ? 'the order reference matches more than one order'
                            : 'the store may not read this order'}
                        </span>
                      </div>
                      <p className="text-rose-800">{caseDetail.order_lookup_block.message}</p>
                      {caseDetail.status === 'ESCALATED' && (
                        <p className="text-rose-700">
                          No proposal is made for this case. Only the Founder can decide it: manual takeover.
                        </p>
                      )}
                    </div>
                  )}
                  {caseDetail.processing_failure && (
                    <div className="p-4 bg-rose-50 rounded-2xl border border-rose-200 text-xs space-y-1.5">
                      <div className="flex items-center space-x-2 text-rose-900 font-bold text-sm">
                        <AlertTriangle className="w-4 h-4 text-rose-600" />
                        <span>Processing failed at stage {caseDetail.processing_failure.stage}</span>
                      </div>
                      <p className="text-rose-800">{caseDetail.processing_failure.error?.error?.message}</p>
                      {caseDetail.status === 'ESCALATED' && (
                        <p className="text-rose-700">
                          No proposal is made for this case. Only the Founder can decide it: manual takeover.
                        </p>
                      )}
                    </div>
                  )}

                  {/* Current Proposal Card */}
                  {caseDetail.current_proposal ? (
                    <div className="bg-slate-50 rounded-2xl p-5 border border-slate-200 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Activity className="w-5 h-5 text-indigo-600" />
                          <h4 className="font-bold text-slate-900 text-sm">
                            Assessment Proposal
                          </h4>
                        </div>
                        <span className="font-mono text-xs bg-slate-200 text-slate-700 px-2 py-0.5 rounded">
                          Proposal v{caseDetail.current_proposal.proposal_version}
                        </span>
                      </div>

                      {(() => {
                        // #111 item 4: say who produced the proposal; the fixed Gate 1 proposal is not a model
                        // and shows no confidence. #111 item 3: tiles without a value are not shown.
                        // The outcome is shown in words (raw value on hover), and break-words keeps a long
                        // value such as a model ID inside its own tile.
                        const proposal = caseDetail.current_proposal;
                        const source = describeProposalSource(proposal.model_run);
                        const conf = proposal.confidence;
                        const confidence =
                          source.isModel && typeof conf === 'number' && Number.isFinite(conf)
                            ? `${(conf * 100).toFixed(0)}%`
                            : null;
                        return (
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-white p-3.5 rounded-xl border border-slate-200 text-xs break-words">
                            <div>
                              <div className="text-slate-400 font-semibold uppercase">Proposed Outcome</div>
                              <div className="text-sm font-bold text-slate-900 mt-0.5" title={proposal.recommended_action}>
                                {formatRecommendation(proposal.recommended_action)}
                              </div>
                            </div>
                            {proposal.refund_amount_cents !== undefined && proposal.refund_amount_cents !== null && (
                              <div>
                                <div className="text-slate-400 font-semibold uppercase">Refund Amount</div>
                                <div className="text-sm font-bold text-slate-900 mt-0.5">
                                  {formatCurrency(proposal.refund_amount_cents)}
                                </div>
                              </div>
                            )}
                            {proposal.return_label_required !== undefined && (
                              <div>
                                <div className="text-slate-400 font-semibold uppercase">Return Label Required</div>
                                <div className="text-sm font-bold text-slate-900 mt-0.5">
                                  {proposal.return_label_required ? 'Yes (Australia Post)' : 'No (Waived)'}
                                </div>
                              </div>
                            )}
                            <div>
                              <div className="text-slate-400 font-semibold uppercase">Source</div>
                              <div className="text-sm font-bold text-slate-900 mt-0.5">{source.label}</div>
                            </div>
                            {confidence && (
                              <div>
                                <div className="text-slate-400 font-semibold uppercase">Model Confidence</div>
                                <div className="text-sm font-bold text-indigo-600 mt-0.5">{confidence}</div>
                              </div>
                            )}
                          </div>
                        );
                      })()}

                      {caseDetail.current_proposal.rationale && (
                        <div>
                          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                            Assessment Rationale
                          </div>
                          <p className="text-xs bg-white p-3 rounded-xl border border-slate-200 text-slate-800 leading-relaxed">
                            {caseDetail.current_proposal.rationale}
                          </p>
                        </div>
                      )}

                      {/* #122 item 5: what the proposal conditions its advice on, and
                          what it could not settle. Server text, rendered as plain text. */}
                      {caseDetail.current_proposal.conditions &&
                        caseDetail.current_proposal.conditions.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                              Conditions ({caseDetail.current_proposal.conditions.length})
                            </div>
                            <ul className="text-xs bg-white p-3 rounded-xl border border-slate-200 text-slate-800 space-y-1 list-disc list-inside leading-relaxed">
                              {caseDetail.current_proposal.conditions.map((condition, i) => (
                                <li key={i}>{condition}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                      {caseDetail.current_proposal.unresolved_questions &&
                        caseDetail.current_proposal.unresolved_questions.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold text-amber-700 uppercase tracking-wider mb-1">
                              Unresolved questions ({caseDetail.current_proposal.unresolved_questions.length})
                            </div>
                            <ul className="text-xs bg-amber-50 p-3 rounded-xl border border-amber-200 text-amber-900 space-y-1 list-disc list-inside leading-relaxed">
                              {caseDetail.current_proposal.unresolved_questions.map((question, i) => (
                                <li key={i}>{question}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                      {/* #122 item 5: the contract's own citations, resolved against the
                          passages the case view carries. Before this, the console showed
                          only the mock-only `policy_citations` chips, so a live case
                          view displayed no citations at all. */}
                      {(() => {
                        const citations = caseDetail.current_proposal?.citations ?? [];
                        if (citations.length === 0) return null;
                        const byPassage = new Map((caseDetail.cited_passages ?? []).map((p) => [p.passage_id, p]));
                        return (
                          <div>
                            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                              Citations ({citations.length})
                            </div>
                            <div className="space-y-1.5">
                              {citations.map((citation) => {
                                const passage = byPassage.get(citation.passage_id);
                                return (
                                  <div
                                    key={citation.citation_id}
                                    className="p-2.5 bg-white rounded-xl border border-slate-200 text-xs space-y-1"
                                  >
                                    <div className="flex items-start justify-between gap-2">
                                      <span className="font-semibold text-slate-800">
                                        {passage ? passage.title : citation.document_id}
                                      </span>
                                      <span className="font-mono text-[10px] text-slate-500 shrink-0">
                                        {citation.location}
                                      </span>
                                    </div>
                                    {passage && (
                                      <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
                                        {passage.content}
                                      </p>
                                    )}
                                    <p className="text-[10px] text-slate-500">
                                      {[citation.source_version ? `version ${citation.source_version}` : null,
                                        `corpus ${citation.corpus_version}`,
                                        passage?.is_synthetic ? 'synthetic corpus' : null,
                                        passage ? null : 'passage not included in this case view',
                                      ]
                                        .filter(Boolean)
                                        .join(' · ')}
                                    </p>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  ) : (
                    <div className="p-6 bg-slate-50 rounded-2xl border border-slate-200 text-center text-xs text-slate-400">
                      No active proposal generated for this case yet.
                    </div>
                  )}

                  {/* Risk Review Card */}
                  {caseDetail.current_review && (
                    <div className="bg-slate-50 rounded-2xl p-5 border border-slate-200 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <ShieldCheck className="w-5 h-5 text-purple-600" />
                          <h4 className="font-bold text-slate-900 text-sm">
                            Risk Review
                          </h4>
                        </div>
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getRiskBadgeClass(
                            caseDetail.current_review.outcome
                          )}`}
                        >
                          {caseDetail.current_review.outcome || '—'}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-4 bg-white p-3.5 rounded-xl border border-slate-200 text-xs">
                        {caseDetail.current_review.risk_score !== undefined && caseDetail.current_review.risk_score !== null && (
                          <div>
                            <div className="text-slate-400 font-semibold uppercase">Risk Score</div>
                            <div className="text-sm font-bold text-slate-900 mt-0.5">
                              {`${(caseDetail.current_review.risk_score * 100).toFixed(1)} / 100`}
                            </div>
                          </div>
                        )}
                        <div>
                          <div className="text-slate-400 font-semibold uppercase">Review Date</div>
                          <div className="text-xs text-slate-700 mt-1">
                            {formatDate(caseDetail.current_review.reviewed_at || '')}
                          </div>
                        </div>
                      </div>

                      {caseDetail.current_review.summary && (
                        <div className="space-y-1">
                          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                            Reviewer Summary
                          </div>
                          <p className="text-xs bg-white p-3 rounded-xl border border-slate-200 text-slate-800 leading-relaxed">
                            {caseDetail.current_review.summary}
                          </p>
                        </div>
                      )}

                      {caseDetail.current_review.findings && caseDetail.current_review.findings.length > 0 && (
                        <div className="space-y-2">
                          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                            Risk Findings ({caseDetail.current_review.findings.length})
                          </div>
                          <div className="space-y-1.5">
                            {caseDetail.current_review.findings.map((f, i) => (
                              <div key={i} className="p-2.5 bg-white rounded-xl border border-slate-200 text-xs flex items-start space-x-2">
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                  f.severity === 'BLOCK' ? 'bg-rose-100 text-rose-800 border border-rose-300' :
                                  f.severity === 'WARNING' ? 'bg-amber-100 text-amber-800 border border-amber-300' :
                                  'bg-slate-100 text-slate-700 border border-slate-200'
                                }`}>
                                  {f.severity}
                                </span>
                                <div className="flex-1">
                                  <span className="font-mono font-semibold text-slate-800">{f.category || f.finding_id}: </span>
                                  <span className="text-slate-700">{f.message}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {caseDetail.current_review.revision_requests &&
                        caseDetail.current_review.revision_requests.length > 0 && (
                          <div className="space-y-1">
                            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                              Revision requests ({caseDetail.current_review.revision_requests.length})
                            </div>
                            <ul className="text-xs bg-white p-3 rounded-xl border border-slate-200 text-slate-800 space-y-1 list-disc list-inside leading-relaxed">
                              {caseDetail.current_review.revision_requests.map((request, i) => (
                                <li key={i}>{request}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                      {caseDetail.current_review.questions && caseDetail.current_review.questions.length > 0 && (
                        <div className="space-y-1">
                          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                            Reviewer questions ({caseDetail.current_review.questions.length})
                          </div>
                          <ul className="text-xs bg-white p-3 rounded-xl border border-slate-200 text-slate-800 space-y-1 list-disc list-inside leading-relaxed">
                            {caseDetail.current_review.questions.map((question) => (
                              <li key={question.question_id}>{question.text}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {caseDetail.current_review.policy_citations && (
                        <div>
                          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                            Statutory & Policy Citations{' '}
                            <span className="font-normal normal-case text-slate-400">
                              (mock fixture strings — the server sends `citations`, shown on the proposal card)
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {caseDetail.current_review.policy_citations.map((cite, i) => (
                              <span
                                key={i}
                                className="bg-purple-100/70 text-purple-800 text-[11px] px-2.5 py-1 rounded-lg border border-purple-200"
                              >
                                {cite}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Governed Execution Preview (UC-04) */}
                  {caseDetail.action_preview && (
                    <div className="bg-sky-50 rounded-2xl p-5 border border-sky-200 space-y-3">
                      <div className="flex items-center space-x-2">
                        <Package className="w-5 h-5 text-sky-600" />
                        <h4 className="font-bold text-sky-950 text-sm">What an approval would allow</h4>
                      </div>
                      <div className="bg-white p-3.5 rounded-xl border border-sky-200">
                        <ApprovalScopeExplained preview={caseDetail.action_preview} />
                      </div>
                      {/* Demo-only extension fields: shown only when a fixture carries them */}
                      {(caseDetail.action_preview.operation_type !== undefined ||
                        caseDetail.action_preview.details !== undefined) && (
                        <div className="text-xs bg-white p-3.5 rounded-xl border border-dashed border-slate-300 space-y-1 font-mono">
                          <div className="font-sans font-semibold text-slate-500">
                            Demo-only fixture fields — not part of the approval scope
                          </div>
                          {caseDetail.action_preview.operation_type !== undefined && (
                            <div>
                              <strong>Operation Type:</strong> {caseDetail.action_preview.operation_type}
                            </div>
                          )}
                          {caseDetail.action_preview.details !== undefined && (
                            <div>
                              <strong>Parameters:</strong> {JSON.stringify(caseDetail.action_preview.details)}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Tab: Order & Facts (Finding 2) */}
              {detailTab === 'order' && (
                <div className="space-y-6">
                  {caseDetail.order_snapshot ? (
                    (() => {
                      // Render only the contract-shaped OrderSnapshot (Finding 2):
                      // snapshot_id / order_id / provider_id / snapshot_version /
                      // purchased_at / currency / line_items / retrieved_at.
                      const order = caseDetail.order_snapshot;
                      const lineItems = Array.isArray(order.line_items) ? order.line_items : [];
                      const totalMinor = lineItems.reduce(
                        (acc, item) =>
                          acc +
                          (Number.isFinite(item.unit_price_minor) ? item.unit_price_minor : 0) *
                            (Number.isFinite(item.quantity) ? item.quantity : 0),
                        0
                      );
                      return (
                        <div className="bg-slate-50 rounded-2xl p-5 border border-slate-200 space-y-4">
                          <div className="flex items-center justify-between pb-2 border-b border-slate-200">
                            <div>
                              <span className="font-mono font-bold text-slate-900 text-base">{order.order_id}</span>
                              <span className="text-xs text-slate-500 ml-2">
                                Ordered: {order.purchased_at ? formatDate(order.purchased_at) : '—'}
                              </span>
                              {order.snapshot_version !== undefined && (
                                <span className="text-xs text-slate-400 ml-2 font-mono">
                                  snapshot v{order.snapshot_version}
                                </span>
                              )}
                            </div>
                            <span className="text-sm font-bold text-slate-900">
                              {order.currency || 'AUD'} Total:{' '}
                              {lineItems.length > 0 ? formatCurrency(totalMinor) : '—'}
                            </span>
                          </div>

                          <div className="space-y-2">
                            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                              Purchased Items ({lineItems.length})
                            </div>
                            <div className="divide-y divide-slate-200 bg-white rounded-xl border border-slate-200 overflow-hidden text-xs">
                              {lineItems.length > 0 ? (
                                lineItems.map((item) => (
                                  <div key={item.line_item_id} className="p-3 flex items-center justify-between">
                                    <div>
                                      <span className="font-semibold text-slate-800">{item.description}</span>
                                      <span className="text-slate-400 font-mono ml-2">SKU: {item.sku}</span>
                                    </div>
                                    <div className="text-right">
                                      <div>Qty: {item.quantity}</div>
                                      <div className="font-bold text-slate-700">
                                        {formatCurrency(item.unit_price_minor)}
                                      </div>
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <div className="p-3 text-slate-400">
                                  No line items recorded on this order snapshot.
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })()
                  ) : (
                    <div className="p-6 bg-slate-50 rounded-2xl border border-slate-200 text-center text-xs text-slate-400">
                      No order snapshot projected for this case.
                    </div>
                  )}

                  {caseDetail.facts && (
                    <AdvisoryFactsCard facts={caseDetail.facts} isMock={isMockMode()} />
                  )}

                  {/* A new draft per case: the key resets the panel when another case opens. */}
                  <AiReplyDraftPanel key={caseDetail.case_id} caseId={caseDetail.case_id} />
                </div>
              )}

              {/* Tab: Statements */}
              {detailTab === 'statements' && (
                <div className="space-y-6">
                  <div className="space-y-3">
                    {caseDetail.statements.map((stmt, idx) => (
                      <div key={stmt.statement_id} className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-2">
                        <div className="flex items-center justify-between text-slate-500">
                          <span className="font-semibold text-slate-700">
                            #{idx + 1} {stmt.kind === 'ORIGINAL' ? 'Original Lodgement' : 'Clarification Statement'}
                          </span>
                          <span>{formatDate(stmt.submitted_at)}</span>
                        </div>
                        <p dir="auto" className="text-sm text-slate-800 whitespace-pre-wrap break-words">
                          {stmt.raw_text}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* #122 item 5: the Founder could not see the customer's evidence at
                      all. The list is contract-shaped and every file is downloadable. */}
                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      Customer evidence ({caseDetail.evidence?.length ?? 0})
                    </div>
                    {evidenceDownloadError && (
                      <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs">
                        {evidenceDownloadError}
                      </div>
                    )}
                    {caseDetail.evidence && caseDetail.evidence.length > 0 ? (
                      caseDetail.evidence.map((item) => (
                        <div
                          key={item.evidence_id}
                          className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex items-center justify-between gap-3"
                        >
                          <div className="min-w-0">
                            <div className="font-semibold text-slate-800 truncate">{item.filename}</div>
                            <div className="text-[11px] text-slate-500">
                              {[
                                item.media_type,
                                `${Math.max(0, Math.round(item.size_bytes / 1024))} KB`,
                                item.status ?? null,
                                item.description ?? null,
                              ]
                                .filter(Boolean)
                                .join(' · ')}
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleDownloadEvidence(item.evidence_id, item.filename)}
                            disabled={downloadingEvidence === item.evidence_id}
                            // Several rows share the visible word "Download"; the
                            // accessible name says which file each one fetches.
                            aria-label={`Download ${item.filename}`}
                            className="px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-slate-700 font-medium hover:bg-slate-100 disabled:opacity-60 shrink-0"
                          >
                            {downloadingEvidence === item.evidence_id ? 'Downloading…' : 'Download'}
                          </button>
                        </div>
                      ))
                    ) : (
                      <p className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-500 text-xs">
                        No customer evidence is attached to this case.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Tab: Decision & Outcome (#122 item 4) */}
              {detailTab === 'outcome' && <CaseOutcomePanel caseView={caseDetail} />}

              {/* Tab: Tamper-Evident Audit Chain (Finding 9) */}
              {detailTab === 'audit' && (
                <div className="space-y-4">
                  {auditError ? (
                    <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs flex items-center space-x-2">
                      <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                      <div>
                        <span className="font-semibold">Audit chain retrieval failed:</span> {auditError}
                      </div>
                    </div>
                  ) : auditEvents.length > 0 ? (
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-700 text-xs flex items-center space-x-2">
                      <FileText className="w-4 h-4 text-slate-500 flex-shrink-0" />
                      <span>
                        Recorded Audit Events: each event shows its recorded hash and, where present, its previous-hash link. This view does not recompute or verify the chain. In Mock Mode those hashes are fixture values rather than SHA-256 digests.
                      </span>
                    </div>
                  ) : (
                    <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-slate-500 text-xs text-center">
                      No audit events recorded for this case.
                    </div>
                  )}

                  {auditOverflow && (
                    <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 text-xs">
                      Only the first {AUDIT_MAX_PAGES * AUDIT_PAGE_LIMIT} recorded events were read. The events shown are real; the chain continues past them.
                    </div>
                  )}

                  {!auditError && auditEvents.length > 0 && (
                    <div className="space-y-2.5">
                      {auditEvents.map((evt, idx) => (
                        <div
                          key={evt.event_id || `evt-${idx}`}
                          className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-1.5 font-mono"
                        >
                          <div className="flex items-center justify-between text-slate-500">
                            <span className="font-bold text-slate-800">
                              #{evt.sequence ?? idx + 1} {evt.event_type}
                            </span>
                            <span>{formatDate(evt.occurred_at || '')}</span>
                          </div>
                          <div className="text-[11px] text-slate-600">
                            Actor: <strong>{formatActor(evt.actor)}</strong>
                          </div>
                          <div className="text-[10px] text-slate-400 break-all">
                            Curr Hash: {evt.event_hash || 'N/A'}
                          </div>
                          {evt.previous_event_hash && (
                            <div className="text-[10px] text-slate-400 break-all">
                              Prev Hash: {evt.previous_event_hash}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Modal Footer: Governed Decision Controls (UC-04 / UC-03 / Findings 4 & 11) */}
            <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 flex-shrink-0">
              <div className="text-xs text-slate-500 space-y-1">
                {caseDetail.status === 'ESCALATED' ? (
                  <span className="text-rose-600 font-semibold">
                    {/* The server accepts only REQUEST_REVISION (on the current proposal)
                        and MANUAL_HANDLING for an escalated case. */}
                    Escalated: approval is not possible.{' '}
                    {caseDetail.current_proposal
                      ? 'Take the case over, or request a revision.'
                      : 'Take the case over.'}
                  </span>
                ) : caseDetail.status === 'AWAITING_APPROVAL' && decisionUnavailable('APPROVE') ? (
                  <span className="text-amber-700 font-semibold">{decisionUnavailable('APPROVE')}</span>
                ) : (['APPROVE', 'REQUEST_REVISION', 'REJECT', 'MANUAL_HANDLING'] as FounderDecisionType[]).every(
                    (decision) => decisionUnavailable(decision) !== null
                  ) ? (
                  <span>No decision is open on this case in its current state.</span>
                ) : null}
                {!isMockMode() && <div>The server checks every decision again and may refuse it.</div>}
              </div>

              <div className="flex flex-wrap items-center justify-end gap-2">
                <button
                  type="button"
                  disabled={caseDetail.status === 'ESCALATED' || decisionUnavailable('APPROVE') !== null}
                  onClick={() => handleOpenDecision('APPROVE')}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl text-xs font-bold transition-colors shadow-sm flex items-center space-x-1"
                  title={
                    caseDetail.status === 'ESCALATED'
                      ? 'Approval is blocked for escalated cases'
                      : decisionUnavailable('APPROVE') ?? 'Approve Return'
                  }
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Approve Return</span>
                </button>

                <button
                  type="button"
                  disabled={decisionUnavailable('REQUEST_REVISION') !== null}
                  onClick={() => handleOpenDecision('REQUEST_REVISION')}
                  className="px-3.5 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl text-xs font-bold transition-colors shadow-sm"
                  title={decisionUnavailable('REQUEST_REVISION') ?? 'Request Revision'}
                >
                  Request Revision
                </button>

                <button
                  type="button"
                  disabled={caseDetail.status === 'ESCALATED' || decisionUnavailable('REJECT') !== null}
                  onClick={() => handleOpenDecision('REJECT')}
                  className="px-3.5 py-2 bg-rose-600 hover:bg-rose-700 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl text-xs font-bold transition-colors shadow-sm flex items-center space-x-1"
                  title={
                    caseDetail.status === 'ESCALATED'
                      ? 'Rejection is blocked for escalated cases: the server accepts Reject only for a case awaiting approval'
                      : decisionUnavailable('REJECT') ?? 'Reject'
                  }
                >
                  <XCircle className="w-3.5 h-3.5" />
                  <span>Reject</span>
                </button>

                <button
                  type="button"
                  disabled={decisionUnavailable('MANUAL_HANDLING') !== null}
                  onClick={() => handleOpenDecision('MANUAL_HANDLING')}
                  className="px-3 py-2 bg-slate-600 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl text-xs font-bold transition-colors shadow-sm"
                  title={decisionUnavailable('MANUAL_HANDLING') ?? 'Manual Takeover'}
                >
                  Manual Takeover
                </button>
              </div>
            </div>
          </div>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* DECISION SUBMISSION CONFIRMATION MODAL (UC-04 / UC-03)    */}
      {/* ========================================================= */}
      {decisionModalOpen && caseDetail && (
        <div className="fixed inset-0 z-[60] overflow-y-auto bg-slate-900/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="decision-dialog-title"
            className="bg-white rounded-2xl max-w-lg w-full min-w-0 shadow-2xl border border-slate-200 overflow-hidden"
          >
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <h4 id="decision-dialog-title" className="font-bold text-slate-900 text-sm">
                Confirm: {DECISION_LABEL[pendingDecision]}
              </h4>
              <button
                onClick={() => setDecisionModalOpen(false)}
                disabled={isSubmittingDecision}
                aria-label="Close decision confirmation"
                title={
                  isSubmittingDecision
                    ? 'The decision is being sent. Closing now would hide whether the server accepted it.'
                    : 'Close'
                }
                className="text-slate-400 hover:text-slate-600 p-1 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleConfirmDecision} className="p-6 space-y-4">
              {decisionError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs">
                  {decisionError}
                </div>
              )}

              <div className="text-xs text-slate-600 space-y-1">
                <div>
                  Case:{' '}
                  <strong className="font-mono text-slate-900 break-all">{caseDetail.case_id}</strong> (version{' '}
                  {caseDetail.case_version})
                </div>
                {caseDetail.current_proposal && (
                  <div>
                    Proposal:{' '}
                    <strong className="font-mono text-slate-900 break-all">
                      {caseDetail.current_proposal.proposal_id}
                    </strong>
                  </div>
                )}
                {/* Same precedence as selectDecisionTarget: failure, then order-lookup block. */}
                {!caseDetail.current_proposal && caseDetail.processing_failure && (
                  <div>
                    Processing failure:{' '}
                    <strong className="font-mono text-slate-900 break-all">{caseDetail.processing_failure.failure_id}</strong>
                  </div>
                )}
                {!caseDetail.current_proposal && !caseDetail.processing_failure && caseDetail.order_lookup_block && (
                  <div>
                    Order lookup problem:{' '}
                    <strong className="font-mono text-slate-900 break-all">{caseDetail.order_lookup_block.block_id}</strong>
                  </div>
                )}
              </div>

              {pendingDecision === 'APPROVE' && caseDetail.action_preview && (
                <div className="p-3.5 bg-sky-50 border border-sky-200 rounded-xl space-y-2">
                  <div className="text-xs font-bold uppercase tracking-wider text-sky-900">What this approval allows</div>
                  <ApprovalScopeExplained preview={caseDetail.action_preview} />
                </div>
              )}

              <div>
                <label htmlFor="decision-reason" className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Reason <span className="text-rose-500">*</span>
                </label>
                <p className="text-[11px] text-slate-500 mb-1.5">Required. It is kept with the decision in the case history.</p>
                <textarea
                  id="decision-reason"
                  rows={3}
                  required
                  maxLength={2000}
                  value={decisionReason}
                  onChange={(e) => setDecisionReason(e.target.value)}
                  placeholder="Why are you making this decision?"
                  disabled={isSubmittingDecision}
                  // The rationale is the first thing to type, so focus starts here.
                  autoFocus
                  className="w-full text-xs p-3 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:bg-white resize-none"
                />
              </div>

              {pendingDecision === 'APPROVE' && previewExpired && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 text-xs">
                  This browser reads the approval preview as expired at {previewExpiresAt}. Close this dialog to
                  reload the case and check the current preview. Manual takeover, reject and request revision do not
                  depend on a preview and remain available.
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setDecisionModalOpen(false)}
                  disabled={isSubmittingDecision}
                  title={
                    isSubmittingDecision
                      ? 'The decision is being sent. Closing now would hide whether the server accepted it.'
                      : undefined
                  }
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={
                    isSubmittingDecision ||
                    decisionReason.trim().length === 0 ||
                    (pendingDecision === 'APPROVE' && previewExpired)
                  }
                  className="px-5 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-xl text-xs font-bold transition-colors shadow-sm disabled:opacity-50"
                >
                  {isSubmittingDecision ? 'Submitting...' : 'Record decision'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* SUB-TAB 2: Operations Analytics Dashboard (OF-006)         */}
      {/* ========================================================= */}
      {activeSubTab === 'analytics' && (
        <div className="space-y-6 animate-fade-in">
          <AiWeeklySummaryPanel />

          {/* Contract query filters: created_from, created_before and one status */}
          <form
            onSubmit={applyAnalyticsFilters}
            className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-end gap-3 text-xs"
          >
            <label className="flex flex-col gap-1 font-semibold text-slate-600">
              Created from (UTC date)
              <input
                type="text"
                placeholder="YYYY-MM-DD"
                autoComplete="off"
                spellCheck={false}
                value={filterFrom}
                onChange={(e) => setFilterFrom(e.target.value)}
                disabled={isMockMode()}
                className="px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl font-normal text-slate-700 disabled:opacity-50"
              />
            </label>
            <label className="flex flex-col gap-1 font-semibold text-slate-600">
              Created before (UTC date, not included)
              <input
                type="text"
                placeholder="YYYY-MM-DD"
                autoComplete="off"
                spellCheck={false}
                value={filterBefore}
                onChange={(e) => setFilterBefore(e.target.value)}
                disabled={isMockMode()}
                className="px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl font-normal text-slate-700 disabled:opacity-50"
              />
            </label>
            <label className="flex flex-col gap-1 font-semibold text-slate-600">
              Current status
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value as CaseStatus | '')}
                disabled={isMockMode()}
                className="px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl font-normal text-slate-700 disabled:opacity-50"
              >
                <option value="">All statuses</option>
                {CASE_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {formatStatusLabel(status)}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-2">
              <button
                type="submit"
                disabled={isMockMode() || isLoadingAnalytics}
                className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white rounded-xl font-bold transition-colors shadow-sm"
              >
                Apply Filters
              </button>
              <button
                type="button"
                onClick={clearAnalyticsFilters}
                disabled={isMockMode() || isLoadingAnalytics}
                className="px-3 py-2 text-slate-600 hover:text-slate-900 disabled:opacity-50 font-semibold"
              >
                Clear
              </button>
            </div>
          </form>

          {isMockMode() && (
            <p className="text-xs text-slate-500">
              The sample data is one fixed snapshot, so the filters are off here.
            </p>
          )}

          {filterError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs">{filterError}</div>
          )}

          {analyticsError && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-xs flex items-center space-x-2">
              <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
              <span>{analyticsError}</span>
            </div>
          )}

          {analytics ? (
            <div className="space-y-6">
              {/* KPI Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Total cases
                  </div>
                  <div className="text-3xl font-extrabold text-slate-900 mt-2">
                    {analytics.case_count}
                  </div>
                </div>

                <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Not yet risk-reviewed
                  </div>
                  <div className="text-3xl font-extrabold text-amber-600 mt-2">
                    {analytics.cases_without_current_review}
                  </div>
                </div>

                <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Typical time to proposal
                  </div>
                  <div className="text-3xl font-extrabold text-indigo-600 mt-2">
                    {analytics.proposal_latency.p50_ms !== undefined
                      ? `${(analytics.proposal_latency.p50_ms / 1000).toFixed(2)}s`
                      : '—'}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    {analytics.proposal_latency.p50_ms !== undefined
                      ? `From ${analytics.proposal_latency.sample_count} measured cases`
                      : 'Not measured (no samples)'}
                  </div>
                </div>

                <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    {/* A measured percentile only: no service level is promised. */}
                    Slow cases (95th percentile)
                  </div>
                  <div className="text-3xl font-extrabold text-purple-600 mt-2">
                    {analytics.proposal_latency.p95_ms !== undefined
                      ? `${(analytics.proposal_latency.p95_ms / 1000).toFixed(2)}s`
                      : '—'}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    {analytics.proposal_latency.p95_ms !== undefined
                      ? `From ${analytics.proposal_latency.sample_count} measured cases`
                      : 'Not measured (no samples)'}
                  </div>
                </div>
              </div>

              {/* Latency counts and snapshot basis: measured + failed + unmeasured = total cases */}
              <div className="bg-white px-5 py-3 rounded-2xl border border-slate-200 shadow-sm text-xs text-slate-600 flex flex-wrap gap-x-6 gap-y-1">
                <span>
                  Measured: <strong className="text-slate-900">{analytics.proposal_latency.sample_count}</strong>
                </span>
                <span>
                  Failed: <strong className="text-slate-900">{analytics.proposal_latency.failed_count}</strong>
                </span>
                <span>
                  Unmeasured: <strong className="text-slate-900">{analytics.proposal_latency.unmeasured_count}</strong>
                </span>
                <span>
                  As of:{' '}
                  <strong className="text-slate-900" title={analytics.as_of}>
                    {formatDate(analytics.as_of)}
                  </strong>
                </span>
                <span>
                  Filters applied:{' '}
                  <strong className="text-slate-900">
                    {Object.keys(analytics.filters).length > 0
                      ? Object.entries(analytics.filters)
                          .map(([key, value]) => `${key}=${value}`)
                          .join(', ')
                      : 'none'}
                  </strong>
                </span>
              </div>

              {/* Status Breakdown Bar Chart */}
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                  <TrendingUp className="w-4 h-4 text-sky-600" />
                  <span>Cases by status</span>
                </h3>

                <div className="space-y-3">
                  {analytics.cases_by_status.length === 0 && (
                    <p className="text-xs text-slate-400">No cases in this snapshot.</p>
                  )}
                  {analytics.cases_by_status.map(({ status, count }) => {
                    const pct = analytics.case_count > 0 ? (count / analytics.case_count) * 100 : 0;
                    return (
                      <div key={status} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium text-slate-700" title={status}>
                            {formatStatusLabel(status)}
                          </span>
                          <span className="font-mono text-slate-500">
                            {count} ({pct.toFixed(0)}%)
                          </span>
                        </div>
                        <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                          <div
                            className="bg-sky-600 h-full rounded-full transition-all duration-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
                <p className="text-[11px] text-slate-400">Statuses with no cases are not listed.</p>
              </div>

              {/* Risk Review Distribution */}
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                  <ShieldCheck className="w-4 h-4 text-purple-600" />
                  <span>Cases by risk review outcome</span>
                </h3>

                {analytics.current_risk_counts.length === 0 && (
                  <p className="text-xs text-slate-400">No case has a current risk review in this snapshot.</p>
                )}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  {analytics.current_risk_counts.map(({ outcome, count }) => (
                    <div
                      key={outcome}
                      className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center space-y-1"
                    >
                      <div className="text-xs font-semibold text-slate-600 break-all">{outcome}</div>
                      <div className="text-2xl font-bold text-slate-900">{count}</div>
                    </div>
                  ))}
                </div>
                <p className="text-[11px] text-slate-400">Outcomes with no cases are not listed.</p>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-slate-400">
              {isLoadingAnalytics ? 'Loading operations analytics...' : 'No analytics data available.'}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
