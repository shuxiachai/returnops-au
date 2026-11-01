import { CaseStatus, RiskOutcome, IssueCategory, ActorProvenance, RequestedOutcome } from '../types/domain';

export function formatDate(isoStr?: string): string {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  // `new Date('garbage')` does not throw, it yields an Invalid Date that would
  // otherwise render as the literal string "Invalid Date".
  if (Number.isNaN(d.getTime())) return '—';
  try {
    return d.toLocaleString('en-AU', {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch {
    return '—';
  }
}

export function formatCurrency(cents?: number): string {
  if (cents === undefined || cents === null) return '—';
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
  }).format(cents / 100);
}

export function getStatusBadgeClass(status?: CaseStatus): string {
  switch (status) {
    case 'SUBMITTED':
      return 'bg-blue-100 text-blue-800 border-blue-200';
    case 'AWAITING_INFORMATION':
      return 'bg-amber-100 text-amber-800 border-amber-300 animate-pulse';
    case 'UNDER_INVESTIGATION':
    case 'POLICY_ASSESSMENT':
      return 'bg-indigo-100 text-indigo-800 border-indigo-200';
    case 'RISK_REVIEW':
    case 'AWAITING_APPROVAL':
      return 'bg-purple-100 text-purple-800 border-purple-200';
    case 'APPROVED':
    case 'COMPLETED':
      return 'bg-emerald-100 text-emerald-800 border-emerald-300';
    case 'REJECTED':
      return 'bg-rose-100 text-rose-800 border-rose-300';
    case 'ESCALATED':
    case 'ACTION_FAILED':
    case 'NOTIFICATION_FAILED':
      return 'bg-red-100 text-red-800 border-red-300';
    case 'MANUAL_HANDLED':
      return 'bg-slate-200 text-slate-800 border-slate-300';
    case 'ACTION_IN_PROGRESS':
    case 'RECONCILING':
    case 'NOTIFICATION_PENDING':
      return 'bg-cyan-100 text-cyan-800 border-cyan-200';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200';
  }
}

export function getRiskBadgeClass(risk?: RiskOutcome): string {
  switch (risk) {
    case 'PASS':
      return 'bg-emerald-100 text-emerald-800 border-emerald-300';
    case 'PASS_WITH_WARNING':
      return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    case 'REVISE':
    case 'NEEDS_INFORMATION':
      return 'bg-amber-100 text-amber-800 border-amber-300';
    case 'ESCALATE':
      return 'bg-red-100 text-red-800 border-red-300';
    default:
      return 'bg-gray-100 text-gray-700 border-gray-200';
  }
}

export function formatCategory(cat?: IssueCategory): string {
  switch (cat) {
    case 'FAULTY_OR_QUALITY_ISSUE':
      return 'Faulty / Quality Issue';
    case 'WRONG_ITEM':
      return 'Wrong Item Sent';
    case 'CHANGE_OF_MIND':
      return 'Change of Mind';
    // Gate 1 runs no classifier: the server's case summary always carries UNCLEAR as
    // a placeholder (founder_queries.summary), so it says nothing about the statement.
    case 'UNCLEAR':
      return 'Not yet classified';
    case 'OUT_OF_SCOPE':
      return 'Out of Scope';
    default:
      return cat || 'Uncategorised';
  }
}

// A contract CaseStatus in words for the Founder's filters
// ('AWAITING_APPROVAL' -> 'Awaiting Approval').
export function formatStatusLabel(status: CaseStatus): string {
  return status
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function formatActor(actor?: string | ActorProvenance): string {
  if (!actor) return '—';
  if (typeof actor === 'string') return actor;
  if (actor.kind === 'HUMAN') {
    return `${actor.principal_id} (${actor.role})`;
  }
  if (actor.kind === 'MODEL') {
    const run = actor.model_run;
    const model = run?.model_id || run?.provider || 'AI Model';
    return `Model: ${model}`;
  }
  if (actor.kind === 'SERVICE') {
    return `Service: ${actor.component_id}`;
  }
  return 'System';
}

// Customer screens show plain words, not internal status names (#111 item 6).
export function formatCustomerStatus(status?: CaseStatus): string {
  switch (status) {
    case 'SUBMITTED':
      return 'Received';
    case 'AWAITING_INFORMATION':
      return 'We need a bit more information';
    case 'UNDER_INVESTIGATION':
    case 'POLICY_ASSESSMENT':
    case 'RISK_REVIEW':
      return 'Being reviewed';
    case 'AWAITING_APPROVAL':
      return "Waiting for the shop's decision";
    case 'APPROVED':
    case 'ACTION_IN_PROGRESS':
    case 'RECONCILING':
      return 'Approved, being processed';
    // Rejection and manual handling pass through this status too, so it names no outcome.
    case 'NOTIFICATION_PENDING':
      return 'The shop has decided; a notice is on its way';
    case 'COMPLETED':
      return 'Completed';
    case 'REJECTED':
      return 'Not approved';
    case 'MANUAL_HANDLED':
      return 'The shop is handling this personally';
    case 'ESCALATED':
    case 'ACTION_FAILED':
    case 'NOTIFICATION_FAILED':
      return 'The shop is looking into this';
    default:
      return status || 'Unknown';
  }
}

export function formatRequestedOutcome(outcome?: RequestedOutcome): string {
  switch (outcome) {
    case 'REFUND':
      return 'Refund';
    case 'REPLACEMENT':
      return 'Replacement';
    case 'REPAIR':
      return 'Repair';
    case 'RETURN':
      return 'Return or store credit';
    case 'INFORMATION':
      return 'Information only';
    case 'OTHER':
      return 'Other';
    case 'UNSPECIFIED':
      return 'Not sure';
    default:
      return outcome || '—';
  }
}

// A contract Recommendation in words for the Founder's proposal card; the raw value
// REFER_FOR_MANUAL_HANDLING is one long word that ran into the next tile.
export function formatRecommendation(action?: string): string {
  switch (action) {
    case 'PROPOSE_RETURN':
      return 'Return';
    case 'PROPOSE_REFUND':
      return 'Refund';
    case 'PROPOSE_REPLACEMENT':
      return 'Replacement';
    case 'PROPOSE_REPAIR':
      return 'Repair';
    case 'REQUEST_INFORMATION':
      return 'Request more information';
    case 'REFER_FOR_MANUAL_HANDLING':
      return 'Refer for manual handling';
    case 'PROPOSE_REJECTION':
      return 'Rejection';
    default:
      return action || 'N/A';
  }
}

// Who produced a proposal (#111 item 4). The fixed Gate 1 proposal reports this model ID and is not a model.
export const FIXED_PROPOSAL_MODEL_ID = 'fixture-no-live-model';

export function describeProposalSource(modelRun?: { model_id?: string; prompt_version?: string }): {
  label: string;
  isModel: boolean;
} {
  const modelId = modelRun?.model_id;
  if (!modelId) return { label: 'Not recorded', isModel: false };
  if (modelId === FIXED_PROPOSAL_MODEL_ID) return { label: 'Fixed rule-based proposal (no model)', isModel: false };
  return {
    label: modelRun?.prompt_version ? `Model ${modelId} (prompt ${modelRun.prompt_version})` : `Model ${modelId}`,
    isModel: true,
  };
}

// The controlled PASS review of Gate 1 (pass_review_sources.py) is fixed, not a model, so
// the review card says so wherever its outcome is shown (1 November 2026).
export const CONTROLLED_REVIEW_MODEL_ID = 'controlled-synthetic-pass';

export function describeReviewSource(modelRun?: { provider_id?: string; model_id?: string }): string {
  const modelId = modelRun?.model_id;
  if (!modelId) return 'Not recorded';
  if (modelId === CONTROLLED_REVIEW_MODEL_ID || modelRun?.provider_id === FIXED_PROPOSAL_MODEL_ID) {
    return 'Controlled review (fixed, no model)';
  }
  return `Model ${modelId}`;
}
