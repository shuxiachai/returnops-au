import { CaseView, FounderDecisionRequest, FounderDecisionType } from '../types/domain';
import { ApiError } from './client';
import { decisionStateRefusal } from './decisionStates';

// The target fields of a FounderDecisionRequest. The contract allows exactly one
// target: the current proposal, a processing failure, or an order-lookup block.
export type DecisionTarget = Pick<
  FounderDecisionRequest,
  | 'proposal_id'
  | 'proposal_version'
  | 'preview_id'
  | 'scope_fingerprint'
  | 'processing_failure_id'
  | 'order_lookup_block_id'
>;

export type DecisionTargetResult = { target: DecisionTarget } | { unavailable: string };

/**
 * Chooses the decision target from the case view the server returned. Every
 * identifier is copied from that view and none is invented: when a required
 * value is missing, the decision is unavailable and the message says why.
 */
export function selectDecisionTarget(
  view: CaseView,
  decision: FounderDecisionType,
  now: number = Date.now()
): DecisionTargetResult {
  const proposal = view.current_proposal;

  // The same state rules as the server, so no button offers a decision it would refuse.
  const refusal = decisionStateRefusal(view.status, decision);
  if (refusal) return { unavailable: refusal };

  // #122 item 12: an approval whose preview has expired is refused by the server,
  // so the button must not stay enabled. The case view is re-read every 5 s, which
  // is what puts a fresh preview in front of the Founder.
  if (decision === 'APPROVE' && view.action_preview?.scope?.expires_at) {
    const expiresAt = Date.parse(view.action_preview.scope.expires_at);
    if (Number.isFinite(expiresAt) && expiresAt <= now) {
      return {
        unavailable:
          `The approval preview expired at ${view.action_preview.scope.expires_at}. The server will not accept it; wait for the case to be read again and check the new preview.`,
      };
    }
  }

  if (decision === 'APPROVE') {
    // The server shows action_preview only while the preview for the current
    // proposal is valid, so its absence means approval is not possible now.
    const preview = view.action_preview;
    if (!proposal || !preview) {
      return {
        unavailable:
          'Approval needs the current proposal and its action preview (preview ID and scope fingerprint) from the server. This case view has none, so approval is unavailable.',
      };
    }
    return {
      target: {
        proposal_id: proposal.proposal_id,
        proposal_version: proposal.proposal_version,
        preview_id: preview.preview_id,
        scope_fingerprint: preview.scope_fingerprint,
      },
    };
  }

  if (proposal) {
    return { target: { proposal_id: proposal.proposal_id, proposal_version: proposal.proposal_version } };
  }

  // Only manual handling may target a failure or a block, only when there is no
  // current proposal, and only while the case is ESCALATED (the server's rule in
  // manual_decision.py); afterwards the view may still show the block or failure.
  if (decision === 'MANUAL_HANDLING') {
    const target: DecisionTarget | null = view.processing_failure
      ? { processing_failure_id: view.processing_failure.failure_id }
      : view.order_lookup_block
        ? { order_lookup_block_id: view.order_lookup_block.block_id }
        : null;
    if (!target) {
      return {
        unavailable:
          'Manual handling needs a current proposal, processing failure or order-lookup block. This case view has none.',
      };
    }
    if (view.status !== 'ESCALATED') {
      return {
        unavailable:
          'This case is no longer escalated, so its processing failure or order-lookup block cannot be decided again.',
      };
    }
    return { target };
  }

  return { unavailable: 'This decision needs a current proposal. This case view has none.' };
}

/**
 * Text for a failed decision request. A 4xx refusal is shown as the server sent
 * it. Status 0 (no usable reply) or any 5xx leaves the outcome unknown: the
 * Vite dev proxy answers an unreachable or dropped API with an empty 500, and a
 * 503 can follow a commit. The text then says so instead of claiming that
 * nothing was recorded.
 */
export function describeDecisionError(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return 'Decision submission failed and no receipt was returned.';
  }
  const text = err.code ? `[${err.code}] ${err.message}` : err.message;
  if (err.status === 0 || err.status >= 500) {
    return `${text} The outcome is unknown: the server may have recorded the decision. Reopen the case to check its status before deciding again. Submitting the same rationale again reuses the same request key.`;
  }
  return text;
}
