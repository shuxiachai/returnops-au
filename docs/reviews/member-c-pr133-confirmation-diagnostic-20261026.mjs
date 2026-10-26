// Bounded C diagnostic, Node >=24.19.0; no installed packages, network or browser.
// Usage: node confirmation-diagnostic.mjs <candidate-FounderConsole.tsx>
//        <baseline-FounderConsole.tsx> <candidate-formatters.ts>
// Executes hash-pinned source functions with synthetic ports. This does NOT
// execute React rendering/effects, Vitest, HTTP, PostgreSQL or authorization.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { stripTypeScriptTypes } from 'node:module';
import { runInNewContext } from 'node:vm';

assert.equal(process.argv.length, 5, 'Supply candidate, baseline and formatter source paths.');
const expected = [
  '22e50cb7f785ea4146998472389e86ef263dcc9b14770ddb222570d75bdad1d2',
  '01711e6b42a3631440fc18b567e99acc2d360a7fd692e77409d7422c8f8d3ef9',
  '08e05bb689036406b948670ee5949085e73ab073db2973e1b4530e2f16588cf8',
];
const source = process.argv.slice(2).map((path, i) => {
  const bytes = readFileSync(path);
  assert.equal(createHash('sha256').update(bytes).digest('hex'), expected[i], 'Source hash differs from reviewed bytes.');
  return bytes.toString('utf8');
});
function between(text, start, end) {
  const from = text.indexOf(start);
  assert.ok(from >= 0 && text.indexOf(start, from + start.length) < 0, 'Source start must be unique.');
  const to = text.indexOf(end, from + start.length);
  assert.ok(to > from, 'Source end missing.');
  return text.slice(from, to);
}
const deferred = () => {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
};
function harness(text, reads, audits = []) {
  let state = { case_id: 'synthetic_case', case_version: 1, proposal_id: 'synthetic_original' };
  let auditApplications = 0;
  const detailLoad = { current: 0 };
  const selectedCaseRef = { current: 'synthetic_case' };
  const functions = between(text, '  const reloadCaseDetail =', '\n  const closeCaseDetail =') + '\n' +
    between(text, '  const handleOpenDecision =', '\n  const handleConfirmDecision =');
  const ports = {
    detailLoad, selectedCaseRef,
    getFounderCase: () => { assert.ok(reads.length); return reads.shift(); },
    listFounderCaseAudit: () => audits.length ? audits.shift() : Promise.resolve([]),
    setCaseDetail: value => { state = value; },
    applyAuditResult: () => { auditApplications += 1; },
    setPendingDecision() {}, setDecisionReason() {}, setDecisionError() {}, setDecisionModalOpen() {},
  };
  const code = stripTypeScriptTypes(functions, { mode: 'strip' }) + '\n({ reloadCaseDetail, handleOpenDecision });';
  return {
    ...runInNewContext(code, ports, { timeout: 1000 }),
    selectedCaseRef, state: () => state, audits: () => auditApplications,
  };
}
const newer = { case_id: 'synthetic_case', case_version: 2, proposal_id: 'synthetic_newer' };
const rows = [];
async function scenario(id, action) { await action(); rows.push({ id, result: 'PASS' }); }
await scenario('candidate_drops_late_case_response', async () => {
  const d = deferred(), h = harness(source[0], [d.promise]);
  const pending = h.reloadCaseDetail('synthetic_case'); h.handleOpenDecision('REJECT'); d.resolve(newer);
  assert.equal(await pending, false); assert.equal(h.state().case_version, 1); assert.equal(h.audits(), 0);
});
await scenario('candidate_drops_response_waiting_for_audit', async () => {
  const d = deferred(), h = harness(source[0], [Promise.resolve(newer)], [d.promise]);
  const pending = h.reloadCaseDetail('synthetic_case'); h.handleOpenDecision('REJECT'); d.resolve([]);
  assert.equal(await pending, false); assert.equal(h.state().proposal_id, 'synthetic_original'); assert.equal(h.audits(), 0);
});
await scenario('candidate_invalidates_two_older_reads', async () => {
  const a = deferred(), b = deferred(), h = harness(source[0], [a.promise, b.promise]);
  const p = h.reloadCaseDetail('synthetic_case'), q = h.reloadCaseDetail('synthetic_case');
  h.handleOpenDecision('REJECT'); b.resolve(newer); a.resolve(newer);
  assert.equal(await p, false); assert.equal(await q, false); assert.equal(h.state().case_version, 1);
});
await scenario('candidate_keeps_normal_read_working', async () => {
  const h = harness(source[0], [Promise.resolve(newer)]);
  assert.equal(await h.reloadCaseDetail('synthetic_case'), true); assert.equal(h.state().case_version, 2); assert.equal(h.audits(), 1);
});
await scenario('candidate_still_rejects_switched_case_response', async () => {
  const d = deferred(), h = harness(source[0], [d.promise]);
  const pending = h.reloadCaseDetail('synthetic_case'); h.selectedCaseRef.current = 'synthetic_other'; d.resolve(newer);
  assert.equal(await pending, false); assert.equal(h.state().case_version, 1);
});
await scenario('explicit_new_read_remains_possible_after_open', async () => {
  const h = harness(source[0], [Promise.resolve(newer)]); h.handleOpenDecision('REJECT');
  // The caller's explicit 409 reload is not a silently admitted old request.
  // This checks only that reload can run; it does not simulate an HTTP 409.
  assert.equal(await h.reloadCaseDetail('synthetic_case'), true); assert.equal(h.state().case_version, 2);
});
await scenario('baseline_control_reproduces_context_replacement', async () => {
  const d = deferred(), h = harness(source[1], [d.promise]);
  const pending = h.reloadCaseDetail('synthetic_case'); h.handleOpenDecision('REJECT'); d.resolve(newer);
  assert.equal(await pending, true); assert.equal(h.state().proposal_id, 'synthetic_newer'); assert.equal(h.audits(), 1);
});
await scenario('missing_outcome_uses_neutral_formatter_without_PASS_fallback', async () => {
  assert.match(source[0], /getRiskBadgeClass\(\s*caseDetail\.current_review\.outcome\s*\)/);
  const ts = between(source[2], 'export function getRiskBadgeClass', '\nexport function formatCategory').replace('export ', '');
  const fn = runInNewContext(stripTypeScriptTypes(ts, { mode: 'strip' }) + '\ngetRiskBadgeClass;', {}, { timeout: 1000 });
  assert.match(fn(undefined), /bg-gray-100/); assert.doesNotMatch(fn(undefined), /emerald/);
  assert.match(fn('PASS'), /emerald/);
});
console.log(JSON.stringify({
  source: 'a7a534b2f862822cc09b94af3c5400568a02fb72',
  baseline: '982bbb7aed3f21f4421f09cc7e1d287bf45cb96d',
  source_sha256: expected,
  kind: 'hash-pinned extracted-function diagnostic with synthetic ports',
  not_executed: ['React rendering or effects', 'Vitest', 'browser', 'HTTP', 'PostgreSQL', 'live model'],
  original_C_WBS_acceptance_claimed: false,
  rows,
}, null, 2));
