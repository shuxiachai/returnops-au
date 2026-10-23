import React, { useState, useEffect } from 'react';
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
  listFounderCaseAudit,
  recordFounderDecision,
  getFounderAnalytics,
  isMockMode,
  ApiError,
} from '../api/client';
import { selectDecisionTarget, describeDecisionError } from '../api/founderDecision';
import { ApprovalScopeSummary } from '../components/ApprovalScopeSummary';
import {
  CaseSummary,
  CaseView,
  CaseStatus,
  AuditEvent,
  AnalyticsQuery,
  AnalyticsSnapshot,
  FounderDecisionType,
  FounderDecisionRequest,
} from '../types/domain';
import { generateIdempotencyKey } from '../utils/idempotency';
import {
  formatDate,
  formatCurrency,
  getStatusBadgeClass,
  getRiskBadgeClass,
  formatCategory,
  formatActor,
} from '../utils/formatters';
import { AdvisoryFactsCard } from '../components/AdvisoryFactsCard';

// Contract CaseStatus values in enum order, for the analytics status filter.
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

export const FounderConsole: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'queue' | 'analytics'>('queue');

  // ---------------------------------------------------------
  // Case Queue State & Pagination (UC-03 / Finding 6)
  // ---------------------------------------------------------
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoadingCases, setIsLoadingCases] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // Selected Case Detail Modal State
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [caseDetail, setCaseDetail] = useState<CaseView | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [detailTab, setDetailTab] = useState<'proposal' | 'order' | 'statements' | 'audit'>('proposal');

  // Decision Modal State (UC-04 / UC-03)
  const [decisionModalOpen, setDecisionModalOpen] = useState(false);
  const [pendingDecision, setPendingDecision] = useState<FounderDecisionType>('APPROVE');
  const [decisionReason, setDecisionReason] = useState('');
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
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

  const loadCases = async () => {
    setIsLoadingCases(true);
    setQueueError(null);
    try {
      const data = await listFounderCases(undefined, 20);
      setCases(data.items);
      setNextCursor(data.next_cursor || null);
    } catch (err: unknown) {
      setQueueError(err instanceof ApiError ? `[${err.code}] ${err.message}` : 'Failed to load case queue');
    } finally {
      setIsLoadingCases(false);
    }
  };

  const loadMoreCases = async () => {
    if (!nextCursor || isLoadingMore) return;
    setIsLoadingMore(true);
    try {
      const data = await listFounderCases(nextCursor, 20);
      setCases((prev) => [...prev, ...data.items]);
      setNextCursor(data.next_cursor || null);
    } catch (err: unknown) {
      setQueueError(err instanceof ApiError ? `[${err.code}] ${err.message}` : 'Failed to load next page');
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
      setAnalyticsError(err instanceof ApiError ? `[${err.code}] ${err.message}` : 'Failed to load analytics');
      setAnalytics(null);
    } finally {
      setIsLoadingAnalytics(false);
    }
  };

  const applyAnalyticsFilters = (e: React.FormEvent) => {
    e.preventDefault();
    // YYYY-MM-DD strings compare correctly as text; the contract needs from < before.
    if (filterFrom && filterBefore && filterFrom >= filterBefore) {
      setFilterError('"Created from" must be earlier than "Created before".');
      return;
    }
    setFilterError(null);
    // Whole UTC days: the window is [from 00:00Z, before 00:00Z).
    const query: AnalyticsQuery = {};
    if (filterFrom) query.created_from = `${filterFrom}T00:00:00Z`;
    if (filterBefore) query.created_before = `${filterBefore}T00:00:00Z`;
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

  const openCaseDetail = async (caseId: string) => {
    setSelectedCaseId(caseId);
    setIsLoadingDetail(true);
    setDetailTab('proposal');
    setAuditError(null);
    try {
      const [detailResult, auditResult] = await Promise.allSettled([
        getFounderCase(caseId),
        listFounderCaseAudit(caseId),
      ]);

      if (detailResult.status === 'fulfilled') {
        setCaseDetail(detailResult.value);
      } else {
        const err = detailResult.reason;
        alert(err instanceof Error ? err.message : 'Failed to fetch case detail');
        setSelectedCaseId(null);
        return;
      }

      if (auditResult.status === 'fulfilled') {
        setAuditEvents(auditResult.value);
        setAuditError(null);
      } else {
        const err = auditResult.reason;
        setAuditEvents([]);
        setAuditError(
          err instanceof ApiError ? `[${err.code}] ${err.message}` : 'Failed to fetch audit events'
        );
      }
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleOpenDecision = (decisionType: FounderDecisionType) => {
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
      await recordFounderDecision(caseDetail.case_id, payload, keyToUse);

      setPendingDecisionKey(null);
      setLastDecisionPayload(null);
      setDecisionModalOpen(false);
      // Reload detail and queue
      await openCaseDetail(caseDetail.case_id);
      loadCases();
    } catch (err: unknown) {
      setDecisionError(describeDecisionError(err));
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

  const filteredCases = cases.filter((c) => {
    const matchesSearch =
      c.case_id.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (c.issue_category && c.issue_category.toLowerCase().includes(searchFilter.toLowerCase()));
    const matchesStatus = statusFilter === 'ALL' || c.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-200 pb-4 gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Founder Console & Governance</h1>
            <span className="bg-sky-100 text-sky-800 text-xs px-2.5 py-0.5 rounded-full font-semibold">
              Store: store_demo
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Authoritative return inspection, governed execution (UC-04) and operations analytics (OF-006)
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
            <span>Case Queue & Review (UC-03/04)</span>
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
            <span>Analytics Dashboard (OF-006)</span>
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
            <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Cases Loaded</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">{cases.length}</div>
            </div>
            <div className="bg-white p-4 rounded-2xl border border-purple-200 shadow-sm">
              <div className="text-xs font-semibold text-purple-700 uppercase tracking-wider">Awaiting Approval</div>
              <div className="text-2xl font-bold text-purple-900 mt-1">
                {cases.filter((c) => c.status === 'AWAITING_APPROVAL').length}
              </div>
            </div>
            <div className="bg-white p-4 rounded-2xl border border-indigo-200 shadow-sm">
              <div className="text-xs font-semibold text-indigo-700 uppercase tracking-wider">Risk Review</div>
              <div className="text-2xl font-bold text-indigo-900 mt-1">
                {cases.filter((c) => c.status === 'RISK_REVIEW').length}
              </div>
            </div>
            <div className="bg-white p-4 rounded-2xl border border-rose-200 shadow-sm">
              <div className="text-xs font-semibold text-rose-700 uppercase tracking-wider">Escalated / Blocked</div>
              <div className="text-2xl font-bold text-rose-900 mt-1">
                {cases.filter((c) => c.status === 'ESCALATED').length}
              </div>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="relative flex-1 w-full">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Filter by Case ID or Category..."
                className="w-full pl-10 pr-4 py-2 text-sm bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 font-mono"
              />
            </div>

            <div className="flex items-center space-x-2 w-full sm:w-auto">
              <select
                value={statusFilter}
                onChange={(e) => handleStatusFilterChange(e.target.value)}
                className="text-xs font-semibold px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-700 focus:ring-2 focus:ring-sky-500"
              >
                <option value="ALL">All Statuses</option>
                <option value="AWAITING_APPROVAL">Awaiting Approval</option>
                <option value="RISK_REVIEW">Risk Review</option>
                <option value="AWAITING_INFORMATION">Awaiting Information</option>
                <option value="UNDER_INVESTIGATION">Under Investigation</option>
                <option value="ESCALATED">Escalated</option>
                <option value="APPROVED">Approved</option>
                <option value="COMPLETED">Completed</option>
              </select>

              <button
                onClick={() => loadCases()}
                disabled={isLoadingCases}
                className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors"
                title="Refresh Queue"
              >
                <RefreshCw className={`w-4 h-4 ${isLoadingCases ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {queueError && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-sm flex items-center space-x-2">
              <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
              <span>{queueError}</span>
            </div>
          )}

          {/* Cases Table */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3.5">Case ID</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-4 py-3.5">Category</th>
                  <th className="px-4 py-3.5">Risk Outcome</th>
                  <th className="px-4 py-3.5">Version</th>
                  <th className="px-4 py-3.5">Updated</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {filteredCases.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-8 text-center text-slate-400">
                      {isLoadingCases ? 'Loading case queue...' : 'No matching cases found.'}
                    </td>
                  </tr>
                ) : (
                  filteredCases.map((c) => (
                    <tr key={c.case_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-6 py-4 font-mono font-bold text-slate-900 whitespace-nowrap">
                        {c.case_id}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <span
                          className={`px-2.5 py-0.5 rounded-full font-semibold border ${getStatusBadgeClass(
                            c.status
                          )}`}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-slate-700 whitespace-nowrap font-medium">
                        {formatCategory(c.issue_category)}
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
                      <td className="px-4 py-4 font-mono text-slate-500">
                        v{c.case_version} / in{c.input_version}
                      </td>
                      <td className="px-4 py-4 text-slate-500 whitespace-nowrap">{formatDate(c.updated_at)}</td>
                      <td className="px-6 py-4 text-right whitespace-nowrap">
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
                  <span>{isLoadingMore ? 'Loading Next Page...' : 'Load Next Page (Next Cursor)'}</span>
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
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          {isLoadingDetail || !caseDetail ? (
            <div className="bg-white rounded-2xl p-8 flex items-center space-x-3 shadow-2xl">
              <RefreshCw className="w-5 h-5 text-sky-600 animate-spin" />
              <span className="text-sm font-semibold text-slate-700">Loading case details...</span>
            </div>
          ) : (
            <div className="bg-white rounded-2xl max-w-4xl w-full shadow-2xl border border-slate-200 max-h-[90vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50 flex-shrink-0">
              <div className="flex items-center space-x-3">
                <span className="font-mono text-lg font-bold text-slate-900">{caseDetail.case_id}</span>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadgeClass(
                    caseDetail.status
                  )}`}
                >
                  {caseDetail.status}
                </span>
                <span className="text-xs text-slate-500 font-mono">v{caseDetail.case_version}</span>
              </div>
              <button
                onClick={() => setSelectedCaseId(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Nav Tabs */}
            <div className="px-6 border-b border-slate-200 bg-white flex space-x-6 text-xs font-semibold flex-shrink-0">
              <button
                onClick={() => setDetailTab('proposal')}
                className={`py-3 border-b-2 transition-all flex items-center space-x-1.5 ${
                  detailTab === 'proposal'
                    ? 'border-sky-600 text-sky-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <Activity className="w-4 h-4" />
                <span>AI Proposal & Risk Review</span>
              </button>
              <button
                onClick={() => setDetailTab('order')}
                className={`py-3 border-b-2 transition-all flex items-center space-x-1.5 ${
                  detailTab === 'order'
                    ? 'border-sky-600 text-sky-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <Package className="w-4 h-4" />
                <span>Order & Facts Projection</span>
              </button>
              <button
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
                onClick={() => setDetailTab('audit')}
                className={`py-3 border-b-2 transition-all flex items-center space-x-1.5 ${
                  detailTab === 'audit'
                    ? 'border-sky-600 text-sky-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <Lock className="w-4 h-4" />
                <span>Tamper-Evident Audit Chain</span>
              </button>
            </div>

            {/* Modal Content Scroll Area */}
            <div className="p-6 overflow-y-auto flex-1 space-y-6">
              {/* Tab: Proposal & Risk */}
              {detailTab === 'proposal' && (
                <div className="space-y-6">
                  {/* Current Proposal Card */}
                  {caseDetail.current_proposal ? (
                    <div className="bg-slate-50 rounded-2xl p-5 border border-slate-200 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Activity className="w-5 h-5 text-indigo-600" />
                          <h4 className="font-bold text-slate-900 text-sm">
                            Autonomous Assessment Proposal (Member A)
                          </h4>
                        </div>
                        <span className="font-mono text-xs bg-slate-200 text-slate-700 px-2 py-0.5 rounded">
                          Proposal v{caseDetail.current_proposal.proposal_version}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-white p-3.5 rounded-xl border border-slate-200 text-xs">
                        <div>
                          <div className="text-slate-400 font-semibold uppercase">Proposed Outcome</div>
                          <div className="text-sm font-bold text-slate-900 mt-0.5">
                            {caseDetail.current_proposal.recommended_action || 'N/A'}
                          </div>
                        </div>
                        <div>
                          <div className="text-slate-400 font-semibold uppercase">Refund Amount</div>
                          <div className="text-sm font-bold text-slate-900 mt-0.5">
                            {caseDetail.current_proposal.refund_amount_cents !== undefined &&
                            caseDetail.current_proposal.refund_amount_cents !== null
                              ? formatCurrency(caseDetail.current_proposal.refund_amount_cents)
                              : '—'}
                          </div>
                        </div>
                        <div>
                          <div className="text-slate-400 font-semibold uppercase">Return Label Required</div>
                          <div className="text-sm font-bold text-slate-900 mt-0.5">
                            {caseDetail.current_proposal.return_label_required === undefined
                              ? '—'
                              : caseDetail.current_proposal.return_label_required
                                ? 'Yes (Australia Post)'
                                : 'No (Waived)'}
                          </div>
                        </div>
                        <div>
                          <div className="text-slate-400 font-semibold uppercase">AI Confidence</div>
                          <div className="text-sm font-bold text-indigo-600 mt-0.5">
                            {(() => {
                              const conf = caseDetail.current_proposal.confidence;
                              return typeof conf === 'number' && Number.isFinite(conf)
                                ? `${(conf * 100).toFixed(0)}%`
                                : '—';
                            })()}
                          </div>
                        </div>
                      </div>

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
                    </div>
                  ) : (
                    <div className="p-6 bg-slate-50 rounded-2xl border border-slate-200 text-center text-xs text-slate-400">
                      No active proposal generated for this case yet.
                    </div>
                  )}

                  {/* Risk Review Card (Member C) */}
                  {caseDetail.current_review && (
                    <div className="bg-slate-50 rounded-2xl p-5 border border-slate-200 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <ShieldCheck className="w-5 h-5 text-purple-600" />
                          <h4 className="font-bold text-slate-900 text-sm">
                            Independent Risk Review (Member C)
                          </h4>
                        </div>
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getRiskBadgeClass(
                            caseDetail.current_review.outcome || 'PASS'
                          )}`}
                        >
                          {caseDetail.current_review.outcome || '—'}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-4 bg-white p-3.5 rounded-xl border border-slate-200 text-xs">
                        <div>
                          <div className="text-slate-400 font-semibold uppercase">Risk Score</div>
                          <div className="text-sm font-bold text-slate-900 mt-0.5">
                            {caseDetail.current_review.risk_score !== undefined && caseDetail.current_review.risk_score !== null
                              ? `${(caseDetail.current_review.risk_score * 100).toFixed(1)} / 100`
                              : 'N/A'}
                          </div>
                        </div>
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

                      {caseDetail.current_review.policy_citations && (
                        <div>
                          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                            Statutory & Policy Citations
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
                        <h4 className="font-bold text-sky-950 text-sm">
                          Governed Execution Preview (UC-04 / Operations Service)
                        </h4>
                      </div>
                      <div className="bg-white p-3.5 rounded-xl border border-sky-200">
                        <ApprovalScopeSummary preview={caseDetail.action_preview} />
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
                </div>
              )}

              {/* Tab: Statements */}
              {detailTab === 'statements' && (
                <div className="space-y-3">
                  {caseDetail.statements.map((stmt, idx) => (
                    <div key={stmt.statement_id} className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-2">
                      <div className="flex items-center justify-between text-slate-500">
                        <span className="font-semibold text-slate-700">
                          #{idx + 1} {stmt.kind === 'ORIGINAL' ? 'Original Lodgement' : 'Clarification Statement'}
                        </span>
                        <span>{formatDate(stmt.submitted_at)}</span>
                      </div>
                      <p className="text-sm text-slate-800 whitespace-pre-wrap">{stmt.raw_text}</p>
                    </div>
                  ))}
                </div>
              )}

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
                        Recorded Audit Events: each event shows its recorded SHA-256 hash and, where present, its previous-hash link. This view does not recompute or verify the chain.
                      </span>
                    </div>
                  ) : (
                    <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-slate-500 text-xs text-center">
                      No audit events recorded for this case.
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
                    Escalated Case: Direct approval blocked.{' '}
                    {caseDetail.current_proposal
                      ? 'Manual takeover or revision required.'
                      : 'Manual takeover required.'}
                  </span>
                ) : decisionUnavailable('APPROVE') ? (
                  <span className="text-amber-700 font-semibold">{decisionUnavailable('APPROVE')}</span>
                ) : (
                  <span>Governed Decision Controls · Approval Guard Active</span>
                )}
                {!isMockMode() && (
                  <div>
                    Live Mode: decisions are sent to the server, which applies its own guards and may refuse them.
                  </div>
                )}
              </div>

              <div className="flex items-center space-x-2">
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
                  <span>Approve Return (UC-04)</span>
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
            aria-labelledby="decision-dialog-title"
            className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden"
          >
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <h4 id="decision-dialog-title" className="font-bold text-slate-900 text-sm">
                Confirm Founder Decision: {pendingDecision}
              </h4>
              <button
                onClick={() => setDecisionModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
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
                  Case Target:{' '}
                  <strong className="font-mono text-slate-900">{caseDetail.case_id}</strong> (v{caseDetail.case_version})
                </div>
                {caseDetail.current_proposal && (
                  <div>
                    Bound Proposal:{' '}
                    <strong className="font-mono text-slate-900">
                      {caseDetail.current_proposal.proposal_id}
                    </strong>
                  </div>
                )}
              </div>

              {pendingDecision === 'APPROVE' && caseDetail.action_preview && (
                <div className="p-3.5 bg-sky-50 border border-sky-200 rounded-xl space-y-2">
                  <div className="text-xs font-bold uppercase tracking-wider text-sky-900">
                    Approval scope: this is all the approval authorises
                  </div>
                  <ApprovalScopeSummary preview={caseDetail.action_preview} />
                </div>
              )}

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
                  Mandatory Governance Rationale <span className="text-rose-500">*</span>
                </label>
                <textarea
                  rows={3}
                  required
                  maxLength={2000}
                  value={decisionReason}
                  onChange={(e) => setDecisionReason(e.target.value)}
                  placeholder="Record justification for statutory audit and customer notification..."
                  className="w-full text-xs p-3 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:bg-white resize-none"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setDecisionModalOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingDecision || decisionReason.trim().length === 0}
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
          {/* Contract query filters: created_from, created_before and one status */}
          <form
            onSubmit={applyAnalyticsFilters}
            className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-end gap-3 text-xs"
          >
            <label className="flex flex-col gap-1 font-semibold text-slate-600">
              Created from (UTC, inclusive)
              <input
                type="date"
                value={filterFrom}
                onChange={(e) => setFilterFrom(e.target.value)}
                disabled={isMockMode()}
                className="px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl font-normal text-slate-700 disabled:opacity-50"
              />
            </label>
            <label className="flex flex-col gap-1 font-semibold text-slate-600">
              Created before (UTC, exclusive)
              <input
                type="date"
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
                    {status}
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
              Mock Mode shows one fixed synthetic snapshot, so the filters are disabled; the live server applies them.
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
                    Total Case Volume
                  </div>
                  <div className="text-3xl font-extrabold text-slate-900 mt-2">
                    {analytics.case_count}
                  </div>
                </div>

                <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Unreviewed Cases
                  </div>
                  <div className="text-3xl font-extrabold text-amber-600 mt-2">
                    {analytics.cases_without_current_review}
                  </div>
                </div>

                <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    p50 Median Latency
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
                    p95 Latency SLA
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
                  <span>Case Status Distribution</span>
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
                          <span className="font-medium text-slate-700">{status}</span>
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
                  <span>Risk Review Outcome Distribution</span>
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
                      <div className="text-xs font-semibold text-slate-600">{outcome}</div>
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
