import { CaseStatus, RiskOutcome, IssueCategory, ActorProvenance } from '../types/domain';

export function formatDate(isoStr?: string): string {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString('en-AU', {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch {
    return isoStr;
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
    case 'UNCLEAR':
      return 'Unclear Statement';
    case 'OUT_OF_SCOPE':
      return 'Out of Scope';
    default:
      return cat || 'Uncategorised';
  }
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
