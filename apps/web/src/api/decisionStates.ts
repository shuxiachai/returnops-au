import { CaseStatus, FounderDecisionType } from '../types/domain';

// The case states in which the server accepts each Founder decision (#104 item 1):
// APPROVE and REJECT only while the case awaits approval (approval admission,
// reject_sources.py); REQUEST_REVISION and a proposal-targeted MANUAL_HANDLING
// while it is escalated or awaits approval (revision_decision.py,
// manual_decision.py). Manual handling of a failure or block needs ESCALATED;
// selectDecisionTarget checks that narrower rule.
export const DECISION_STATES: Record<FounderDecisionType, readonly CaseStatus[]> = {
  APPROVE: ['AWAITING_APPROVAL'],
  REJECT: ['AWAITING_APPROVAL'],
  REQUEST_REVISION: ['ESCALATED', 'AWAITING_APPROVAL'],
  MANUAL_HANDLING: ['ESCALATED', 'AWAITING_APPROVAL'],
};

const LABELS: Record<FounderDecisionType, string> = {
  APPROVE: 'Approval',
  REJECT: 'Rejection',
  REQUEST_REVISION: 'A revision request',
  MANUAL_HANDLING: 'Manual takeover',
};

/** Why the server would refuse this decision in this state, or null if the state allows it. */
export function decisionStateRefusal(status: CaseStatus, decision: FounderDecisionType): string | null {
  const states = DECISION_STATES[decision];
  if (states.includes(status)) return null;
  const allowed = states.length === 1 ? `a case in ${states[0]}` : `a case in ${states.join(' or ')}`;
  return `${LABELS[decision]} is accepted only for ${allowed}; this case is ${status}.`;
}
