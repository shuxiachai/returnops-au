import { describe, it, expect } from 'vitest';
import schemas from '../../../../contracts/v1/schemas.json';
import { MOCK_FOUNDER_CASE_VIEWS } from './mockData';

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
