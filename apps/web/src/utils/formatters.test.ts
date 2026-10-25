import { describe, it, expect } from 'vitest';
import {
  formatCurrency,
  formatDate,
  getStatusBadgeClass,
  getRiskBadgeClass,
  formatCategory,
  formatActor,
  formatCustomerStatus,
  formatRequestedOutcome,
  describeProposalSource,
  FIXED_PROPOSAL_MODEL_ID,
} from './formatters';
import { ActorProvenance, CaseStatus, RequestedOutcome } from '../types/domain';

describe('formatters', () => {
  describe('formatCurrency', () => {
    it('formats cents into Australian dollar currency strings', () => {
      expect(formatCurrency(12999)).toBe('$129.99');
      expect(formatCurrency(0)).toBe('$0.00');
      expect(formatCurrency(245050)).toBe('$2,450.50');
    });

    it('handles undefined or null gracefully with em-dash', () => {
      expect(formatCurrency(undefined)).toBe('—');
      expect(formatCurrency(null as unknown as number)).toBe('—');
    });
  });

  describe('formatDate', () => {
    it('returns em-dash for empty, undefined and unparseable dates', () => {
      expect(formatDate('')).toBe('—');
      expect(formatDate(undefined)).toBe('—');
      // `new Date('not-a-date')` yields Invalid Date rather than throwing.
      expect(formatDate('not-a-date')).toBe('—');
    });

    it('formats ISO timestamps with en-AU medium date and short time', () => {
      const iso = '2026-10-09T14:30:00Z';
      const expected = new Date(iso).toLocaleString('en-AU', {
        dateStyle: 'medium',
        timeStyle: 'short',
      });

      expect(formatDate(iso)).toBe(expected);
      // Structural assertion so the check cannot pass on an empty string, while
      // staying independent of the machine's local timezone.
      expect(formatDate(iso)).toMatch(/^\d{1,2} [A-Z][a-z]{2} \d{4}, \d{1,2}:\d{2} (am|pm)$/);
    });
  });

  describe('getStatusBadgeClass', () => {
    it('returns emerald badge classes for terminal approved states', () => {
      const cls = getStatusBadgeClass('COMPLETED');
      expect(cls).toContain('emerald');
    });

    it('returns rose badge classes for rejected states', () => {
      const cls = getStatusBadgeClass('REJECTED');
      expect(cls).toContain('rose');
    });

    it('returns amber badge classes for awaiting information states', () => {
      const cls = getStatusBadgeClass('AWAITING_INFORMATION');
      expect(cls).toContain('amber');
    });

    it('returns purple badge classes for awaiting approval and risk review', () => {
      const cls = getStatusBadgeClass('AWAITING_APPROVAL');
      expect(cls).toContain('purple');
    });

    it('maps every one of the sixteen CaseStatus values to its expected badge family (Finding 12)', () => {
      // Exhaustive on purpose: the shared switch has sixteen domain branches, so a
      // partial spot-check of four inputs does not evidence full status coverage.
      const expected: Record<CaseStatus, string> = {
        SUBMITTED: 'blue',
        AWAITING_INFORMATION: 'amber',
        UNDER_INVESTIGATION: 'indigo',
        POLICY_ASSESSMENT: 'indigo',
        RISK_REVIEW: 'purple',
        AWAITING_APPROVAL: 'purple',
        APPROVED: 'emerald',
        ACTION_IN_PROGRESS: 'cyan',
        ACTION_FAILED: 'red',
        RECONCILING: 'cyan',
        ESCALATED: 'red',
        NOTIFICATION_PENDING: 'cyan',
        NOTIFICATION_FAILED: 'red',
        COMPLETED: 'emerald',
        REJECTED: 'rose',
        MANUAL_HANDLED: 'slate',
      };

      const statuses = Object.keys(expected) as CaseStatus[];
      expect(statuses).toHaveLength(16);
      for (const status of statuses) {
        expect(getStatusBadgeClass(status)).toContain(expected[status]);
      }

      // The unknown-state fallback sits outside the sixteen-state domain map.
      expect(getStatusBadgeClass(undefined)).toContain('gray');
    });
  });

  describe('getRiskBadgeClass', () => {
    it('returns emerald badge for PASS', () => {
      expect(getRiskBadgeClass('PASS')).toContain('emerald');
    });

    it('returns yellow badge for PASS_WITH_WARNING', () => {
      expect(getRiskBadgeClass('PASS_WITH_WARNING')).toContain('yellow');
    });

    it('returns amber badge for REVISE and NEEDS_INFORMATION', () => {
      expect(getRiskBadgeClass('REVISE')).toContain('amber');
      expect(getRiskBadgeClass('NEEDS_INFORMATION')).toContain('amber');
    });

    it('returns red badge for ESCALATE', () => {
      expect(getRiskBadgeClass('ESCALATE')).toContain('red');
    });
  });

  describe('formatCategory', () => {
    it('formats known domain categories into human-readable descriptions', () => {
      expect(formatCategory('FAULTY_OR_QUALITY_ISSUE')).toBe('Faulty / Quality Issue');
      expect(formatCategory('WRONG_ITEM')).toBe('Wrong Item Sent');
      expect(formatCategory('CHANGE_OF_MIND')).toBe('Change of Mind');
      expect(formatCategory('UNCLEAR')).toBe('Unclear Statement');
    });

    it('returns Uncategorised for undefined category', () => {
      expect(formatCategory(undefined)).toBe('Uncategorised');
    });
  });

  describe('formatActor', () => {
    it('formats plain string actor directly', () => {
      expect(formatActor('operator_001')).toBe('operator_001');
    });

    it('formats HUMAN ActorProvenance with principal ID and role', () => {
      const actor: ActorProvenance = {
        kind: 'HUMAN',
        principal_id: 'user_123',
        role: 'FOUNDER',
      };
      expect(formatActor(actor)).toBe('user_123 (FOUNDER)');
    });

    it('formats SERVICE ActorProvenance with component ID', () => {
      const actor: ActorProvenance = {
        kind: 'SERVICE',
        component_id: 'api-gateway',
      };
      expect(formatActor(actor)).toBe('Service: api-gateway');
    });

    it('formats MODEL ActorProvenance with model ID', () => {
      const actor: ActorProvenance = {
        kind: 'MODEL',
        model_run: {
          model_id: 'campus-qwen',
        },
      };
      expect(formatActor(actor)).toBe('Model: campus-qwen');
    });

    it('returns em-dash for nullish actor', () => {
      expect(formatActor(null as unknown as string)).toBe('—');
      expect(formatActor(undefined)).toBe('—');
    });
  });

  describe('customer wording (#111 items 4 to 6)', () => {
    it('gives every case status a plain customer phrase and never shows the internal name', () => {
      const statuses: CaseStatus[] = [
        'SUBMITTED', 'AWAITING_INFORMATION', 'UNDER_INVESTIGATION', 'POLICY_ASSESSMENT', 'RISK_REVIEW',
        'AWAITING_APPROVAL', 'APPROVED', 'ACTION_IN_PROGRESS', 'ACTION_FAILED', 'RECONCILING', 'ESCALATED',
        'NOTIFICATION_PENDING', 'NOTIFICATION_FAILED', 'COMPLETED', 'REJECTED', 'MANUAL_HANDLED',
      ];
      for (const status of statuses) {
        const phrase = formatCustomerStatus(status);
        expect(phrase).not.toBe(status);
        expect(phrase).not.toMatch(/_/);
      }
      expect(formatCustomerStatus('AWAITING_INFORMATION')).toBe('We need a bit more information');
      expect(formatCustomerStatus('RISK_REVIEW')).toBe('Being reviewed');
      expect(formatCustomerStatus('MANUAL_HANDLED')).toBe('The shop is handling this personally');
      expect(formatCustomerStatus(undefined)).toBe('Unknown');
    });

    it('names every requested outcome in words, including "Not sure"', () => {
      const outcomes: RequestedOutcome[] = ['REFUND', 'REPLACEMENT', 'REPAIR', 'RETURN', 'INFORMATION', 'UNSPECIFIED', 'OTHER'];
      for (const outcome of outcomes) {
        expect(formatRequestedOutcome(outcome)).not.toBe(outcome);
      }
      expect(formatRequestedOutcome('UNSPECIFIED')).toBe('Not sure');
      expect(formatRequestedOutcome(undefined)).toBe('—');
    });

    it('labels the fixed proposal as no model and names a real model with its prompt', () => {
      expect(describeProposalSource({ model_id: FIXED_PROPOSAL_MODEL_ID })).toEqual({
        label: 'Fixed rule-based proposal (no model)',
        isModel: false,
      });
      expect(describeProposalSource(undefined)).toEqual({ label: 'Not recorded', isModel: false });
      expect(describeProposalSource({ model_id: 'campus-qwen', prompt_version: 'p-2' })).toEqual({
        label: 'Model campus-qwen (prompt p-2)',
        isModel: true,
      });
      expect(describeProposalSource({ model_id: 'campus-qwen' })).toEqual({ label: 'Model campus-qwen', isModel: true });
    });
  });
});
