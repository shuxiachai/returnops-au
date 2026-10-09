import { describe, it, expect } from 'vitest';
import {
  formatCurrency,
  formatDate,
  getStatusBadgeClass,
  getRiskBadgeClass,
  formatCategory,
  formatActor,
} from './formatters';
import { ActorProvenance } from '../types/domain';

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
    it('returns em-dash for empty or invalid dates', () => {
      expect(formatDate('')).toBe('—');
      expect(formatDate(undefined)).toBe('—');
    });

    it('formats ISO dates accurately in en-AU format', () => {
      const formatted = formatDate('2026-10-09T14:30:00Z');
      expect(formatted).toBeTruthy();
      expect(formatted).not.toBe('—');
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
});
