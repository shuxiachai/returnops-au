import { describe, it, expect } from 'vitest';
import { selectDecisionTarget, describeDecisionError } from './founderDecision';
import { ApiError } from './client';
import type { ActionPreview, CaseView } from '../types/domain';

const BASE_VIEW: CaseView = {
  case_id: 'case_target',
  case_version: 3,
  input_version: 2,
  status: 'AWAITING_APPROVAL',
  created_at: '2026-10-20T00:00:00Z',
  updated_at: '2026-10-21T00:00:00Z',
  statements: [],
  evidence: [],
};

const PROPOSAL = { proposal_id: 'prop_target', proposal_version: 2, created_at: '2026-10-21T00:00:00Z' };
const PREVIEW: ActionPreview = {
  preview_id: 'preview_target',
  scope_fingerprint: 'a'.repeat(64),
  scope: {
    case_id: 'case_target',
    input_version: 2,
    proposal_id: 'prop_target',
    proposal_version: 2,
    review_id: 'review_target',
    parcel_id: 'parcel_target',
    commands: [],
    currency: 'AUD',
    amount_ceiling_minor: 0,
    expires_at: '2026-10-21T00:05:00Z',
    allowlist_version: 'allowlist-v1',
    environment: 'SIMULATED',
  },
};
// Contract ProcessingFailure and OrderLookupBlock shapes.
const FAILURE = {
  failure_id: 'failure_target',
  case_id: 'case_target',
  input_version: 1,
  stage: 'ORDER_LOOKUP' as const,
  error: {
    error: { code: 'PROVIDER_UNAVAILABLE', message: 'Order lookup failed.', retryable: false, details: [] },
  },
  occurred_at: '2026-10-21T00:00:00Z',
};

const BLOCK = {
  block_id: 'block_target',
  case_id: 'case_target',
  input_version: 1,
  status: 'CONFLICT' as const,
  message: 'The authorized order reference is ambiguous.',
  occurred_at: '2026-10-21T00:00:00Z',
};

describe('selectDecisionTarget', () => {
  it('binds APPROVE to the current proposal and the server preview exactly as returned', () => {
    const view: CaseView = { ...BASE_VIEW, current_proposal: PROPOSAL, action_preview: PREVIEW };

    expect(selectDecisionTarget(view, 'APPROVE')).toStrictEqual({
      target: {
        proposal_id: 'prop_target',
        proposal_version: 2,
        preview_id: 'preview_target',
        scope_fingerprint: 'a'.repeat(64),
      },
    });
  });

  it('makes APPROVE unavailable instead of inventing preview values', () => {
    const result = selectDecisionTarget({ ...BASE_VIEW, current_proposal: PROPOSAL }, 'APPROVE');

    expect(result).not.toHaveProperty('target');
    expect(result).toHaveProperty('unavailable', expect.stringMatching(/approval is unavailable/i));
  });

  it('sends only the proposal target for the other decisions when a proposal exists', () => {
    // Preview and failure are present but must not leak into a non-APPROVE body.
    const view: CaseView = {
      ...BASE_VIEW,
      current_proposal: PROPOSAL,
      action_preview: PREVIEW,
      processing_failure: FAILURE,
    };

    for (const decision of ['REJECT', 'REQUEST_REVISION', 'MANUAL_HANDLING'] as const) {
      expect(selectDecisionTarget(view, decision)).toStrictEqual({
        target: { proposal_id: 'prop_target', proposal_version: 2 },
      });
    }
  });

  it('targets a processing failure or order-lookup block only for MANUAL_HANDLING without a proposal', () => {
    const escalated: CaseView = { ...BASE_VIEW, status: 'ESCALATED' };

    expect(selectDecisionTarget({ ...escalated, processing_failure: FAILURE }, 'MANUAL_HANDLING')).toStrictEqual({
      target: { processing_failure_id: 'failure_target' },
    });
    expect(
      selectDecisionTarget(
        { ...escalated, order_lookup_block: BLOCK },
        'MANUAL_HANDLING'
      )
    ).toStrictEqual({ target: { order_lookup_block_id: 'block_target' } });

    expect(selectDecisionTarget({ ...escalated, processing_failure: FAILURE }, 'REJECT')).toHaveProperty('unavailable');
    expect(selectDecisionTarget(escalated, 'MANUAL_HANDLING')).toHaveProperty('unavailable');
    // After the decision the view may still carry the block, but the case is no longer escalated.
    expect(
      selectDecisionTarget({ ...BASE_VIEW, status: 'NOTIFICATION_PENDING', order_lookup_block: BLOCK }, 'MANUAL_HANDLING')
    ).toHaveProperty('unavailable', expect.stringMatching(/no longer escalated/i));
  });
});

describe('describeDecisionError', () => {
  it('shows a server refusal as the server sent it', () => {
    expect(
      describeDecisionError(new ApiError(409, 'The case version has changed.', 'STALE_CASE_VERSION'))
    ).toBe('[STALE_CASE_VERSION] The case version has changed.');
  });

  it('says the outcome is unknown after any 5xx or a lost response, never that nothing was recorded', () => {
    const unavailable = describeDecisionError(
      new ApiError(503, 'The service is temporarily unavailable; keep the original request key.', 'INTERNAL_ERROR')
    );
    // What request() produces when the Vite dev proxy cannot reach the API.
    const proxy = describeDecisionError(
      new ApiError(500, 'HTTP 500: Backend server unavailable at http://127.0.0.1:8000.', 'HTTP_500')
    );
    const lost = describeDecisionError(new ApiError(0, 'Failed to fetch'));
    const mismatch = describeDecisionError(
      new ApiError(0, 'The server replied without an accepted receipt for this case and decision.', 'RECEIPT_MISMATCH')
    );

    expect(unavailable).toMatch(/^\[INTERNAL_ERROR\] .* The outcome is unknown/);
    expect(proxy).toMatch(/^\[HTTP_500\] .* The outcome is unknown/);
    expect(lost).toMatch(/^Failed to fetch The outcome is unknown/);
    expect(mismatch).toMatch(/^\[RECEIPT_MISMATCH\] .* The outcome is unknown/);
    expect([unavailable, proxy, lost, mismatch].join(' ')).not.toMatch(/nothing was recorded/i);
  });
});
