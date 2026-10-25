import { describe, it, expect } from 'vitest';
import schemas from '../../../../contracts/v1/schemas.json';
import {
  MOCK_AUDIT_EVENTS,
  MOCK_CUSTOMER_CASES,
  MOCK_FOUNDER_CASE_VIEWS,
  MOCK_FOUNDER_SUMMARIES,
} from './mockData';

const defs = schemas.$defs;
const mockViewsWithFacts = Object.values(MOCK_FOUNDER_CASE_VIEWS).filter((view) => view.facts);

describe('mock Founder facts (Issue #95)', () => {
  it('keeps every mock facts object to the contract ExtractedFacts shape', () => {
    expect(mockViewsWithFacts.length).toBeGreaterThan(0);
    const required = [...defs.ExtractedFacts.required].sort();
    expect(Object.keys(defs.ExtractedFacts.properties).sort()).toEqual(required);

    for (const view of mockViewsWithFacts) {
      const facts = view.facts!;
      // All six required keys and nothing else (additionalProperties: false).
      expect(Object.keys(facts).sort()).toEqual(required);
      expect(defs.IssueCategory.enum).toContain(facts.issue_category);
      expect(defs.RequestedOutcome.enum).toContain(facts.customer_requested_outcome);
      expect(defs.PossibleBasis.enum).toContain(facts.possible_basis);
      expect(defs.AssessmentStatus.enum).toContain(facts.assessment_status);
      expect(facts.summary.length).toBeGreaterThanOrEqual(defs.ExtractedFacts.properties.summary.minLength);
      expect(facts.summary.length).toBeLessThanOrEqual(defs.ExtractedFacts.properties.summary.maxLength);
      expect(facts.line_items.length).toBeLessThanOrEqual(defs.ExtractedFacts.properties.line_items.maxItems);
    }
  });

  it('only uses values the advisory showcase can accept (docs/44 acceptance chain)', () => {
    for (const view of mockViewsWithFacts) {
      const facts = view.facts!;
      const original = view.statements.find((s) => s.kind === 'ORIGINAL');
      expect(facts.line_items).toEqual([]);
      expect(facts.possible_basis).toBe('UNDETERMINED');
      expect(facts.assessment_status).not.toBe('SUPPORTED');
      expect(facts.customer_requested_outcome).toBe(original?.requested_outcome);
      expect(facts.summary.trim().length).toBeGreaterThan(0);
      expect(facts.summary.length).toBeLessThanOrEqual(1000);
    }
  });
});

describe('mock queue and wording (#122 items 1 and 3)', () => {
  it('gives every queue row a case view with the same status and version, so every row can be opened', () => {
    expect(MOCK_FOUNDER_SUMMARIES).toHaveLength(25);
    for (const summary of MOCK_FOUNDER_SUMMARIES) {
      const view = MOCK_FOUNDER_CASE_VIEWS[summary.case_id];
      expect(view, summary.case_id).toBeDefined();
      expect(view.status).toBe(summary.status);
      expect(view.case_version).toBe(summary.case_version);
      expect(view.statements.length).toBeGreaterThan(0);
    }
  });

  it('claims no PASS review for a case that has not reached risk review', () => {
    for (const summary of MOCK_FOUNDER_SUMMARIES) {
      if (summary.status === 'UNDER_INVESTIGATION' || summary.status === 'POLICY_ASSESSMENT') {
        expect(summary.current_risk_outcome, summary.case_id).not.toBe('PASS');
      }
    }
  });

  it('uses Founder-only, simulated-only wording and no real brand', () => {
    const text = JSON.stringify({ MOCK_CUSTOMER_CASES, MOCK_FOUNDER_CASE_VIEWS, MOCK_AUDIT_EVENTS });
    for (const phrase of [
      /autonomous/i,
      /instant refund/i,
      /waiver granted/i,
      /REFUND_DISPATCHED/,
      /payment_method/,
      /VISA/,
      /DeLonghi/i,
    ]) {
      expect(text).not.toMatch(phrase);
    }
    const events = Object.values(MOCK_AUDIT_EVENTS).flat();
    // Only the Founder approves, and no agent closes a case.
    for (const event of events.filter((e) => e.event_type === 'FOUNDER_APPROVED')) {
      expect(event.actor).toMatchObject({ kind: 'HUMAN', role: 'FOUNDER' });
    }
    const completed = events.filter((e) => e.event_type === 'CASE_COMPLETED');
    expect(completed.length).toBeGreaterThan(0);
    for (const event of completed) {
      expect(JSON.stringify(event.actor)).not.toMatch(/agent/i);
    }
  });
});
