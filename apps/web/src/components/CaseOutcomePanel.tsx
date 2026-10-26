import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, Send } from 'lucide-react';
import { ApiError, downloadEvidence } from '../api/client';
import {
  ApprovalRecord,
  CaseView,
  FounderDecisionRecord,
  FounderDecisionType,
  NotificationRecord,
  OperationAttempt,
} from '../types/domain';
import { formatDate } from '../utils/formatters';
import { ApprovalScopeSummary } from './ApprovalScopeSummary';

const DECISION_LABELS: Record<FounderDecisionType, string> = {
  APPROVE: 'Approved',
  REJECT: 'Rejected',
  REQUEST_REVISION: 'Revision requested',
  MANUAL_HANDLING: 'Manual takeover',
};

const OPERATION_LABELS: Record<string, string> = {
  CREATE_RETURN: 'Create the simulated return',
  GENERATE_LABEL: 'Generate the return label (PDF)',
};

const NOTICE_OUTCOMES: Record<NotificationRecord['outcome'], string> = {
  RETURN_CREATED: 'Return created',
  REJECTED: 'Rejected',
  MANUAL_HANDLED: 'Handled manually',
};

function statusClass(status: string): string {
  if (status === 'SUCCEEDED' || status === 'SENT') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (status === 'FAILED') return 'bg-rose-50 text-rose-700 border-rose-200';
  if (status === 'UNKNOWN' || status === 'RECONCILING' || status === 'BLOCKED') {
    return 'bg-amber-50 text-amber-800 border-amber-200';
  }
  return 'bg-slate-100 text-slate-700 border-slate-200';
}

const StatusBadge: React.FC<{ status: string }> = ({ status }) => (
  <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold border ${statusClass(status)}`}>{status}</span>
);

// The operation type comes from its result once the provider confirmed it;
// before that, from the approved command it executes.
function operationType(operation: OperationAttempt, approvals: ApprovalRecord[]): string | undefined {
  if (operation.result) return operation.result.type;
  for (const approval of approvals) {
    const command = approval.scope.commands.find((c) => c.command_id === operation.command_id);
    if (command) return command.type;
  }
  return undefined;
}

function decisionTarget(decision: FounderDecisionRecord): string {
  if (decision.proposal_id) return `proposal ${decision.proposal_id} v${decision.proposal_version}`;
  if (decision.processing_failure_id) return `processing failure ${decision.processing_failure_id}`;
  if (decision.order_lookup_block_id) return `order-lookup block ${decision.order_lookup_block_id}`;
  return 'no recorded target';
}

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <section className="space-y-2.5">
    <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">{title}</h4>
    {children}
  </section>
);

const Empty: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-500 text-xs">{children}</div>
);

/**
 * What happened after the Founder decided (#122 item 4; FR-012, docs/08 B2.03):
 * the decision, the exact scope an approval authorised, the simulated operations
 * with the label PDF, and the customer notice, all as the server's case view
 * states them. Server text is shown as plain text; nothing is inferred.
 */
export const CaseOutcomePanel: React.FC<{ caseView: CaseView }> = ({ caseView }) => {
  const decisions = caseView.decisions ?? [];
  const approvals = caseView.approvals ?? [];
  const operations = caseView.operations ?? [];
  const notifications = caseView.notifications ?? [];
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleDownload = async (evidenceId: string) => {
    setDownloading(evidenceId);
    setDownloadError(null);
    try {
      await downloadEvidence(evidenceId, `${caseView.case_id}-return-label.pdf`);
    } catch (err: unknown) {
      const text = err instanceof ApiError ? `[${err.code}] ${err.message}` : 'The label could not be downloaded.';
      setDownloadError(text);
    } finally {
      setDownloading(null);
    }
  };

  if (decisions.length + approvals.length + operations.length + notifications.length === 0) {
    return (
      <Empty>
        No Founder decision is recorded for this case yet. Once the Founder decides, this tab shows the decision, the
        approved scope, the simulated operations and the notice to the customer.
      </Empty>
    );
  }

  return (
    <div className="space-y-6">
      <Section title="Founder decision">
        {decisions.length === 0 ? (
          <Empty>No Founder decision is recorded for this case.</Empty>
        ) : (
          decisions.map((decision) => (
            <div
              key={decision.decision_id}
              className="p-4 bg-white rounded-xl border border-slate-200 text-xs space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center space-x-1.5 font-bold text-slate-900 text-sm">
                  <CheckCircle2 className="w-4 h-4 text-sky-600" />
                  <span>{DECISION_LABELS[decision.decision] ?? decision.decision}</span>
                </span>
                <span className="text-slate-500" title={decision.decided_at}>
                  {formatDate(decision.decided_at)}
                </span>
              </div>
              <p className="text-slate-800 whitespace-pre-wrap">{decision.reason}</p>
              <div className="text-slate-500">
                By <span className="font-mono">{decision.principal_id}</span> · on {decisionTarget(decision)}
                {decision.approval_id && (
                  <>
                    {' '}
                    · approval <span className="font-mono">{decision.approval_id}</span>
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </Section>

      {approvals.length > 0 && (
        <Section title="Approved scope">
          {approvals.map((approval) => (
            <div
              key={approval.approval_id}
              className="p-4 bg-white rounded-xl border border-slate-200 text-xs space-y-2"
            >
              <div className="text-slate-500">
                Approval <span className="font-mono">{approval.approval_id}</span> issued{' '}
                <span title={approval.issued_at}>{formatDate(approval.issued_at)}</span> by{' '}
                <span className="font-mono">{approval.principal_id}</span>
              </div>
              <ApprovalScopeSummary
                preview={{
                  preview_id: approval.preview_id,
                  scope_fingerprint: approval.scope_fingerprint,
                  scope: approval.scope,
                }}
              />
            </div>
          ))}
        </Section>
      )}

      {(approvals.length > 0 || operations.length > 0) && (
        <Section title="Simulated operations">
          {operations.length === 0 ? (
            <Empty>No operation has been recorded yet. The approved commands run after the approval.</Empty>
          ) : (
            operations.map((operation) => {
              const type = operationType(operation, approvals);
              const label = operation.result?.type === 'GENERATE_LABEL' ? operation.result.label_evidence_id : null;
              return (
                <div
                  key={operation.operation_id}
                  className="p-4 bg-white rounded-xl border border-slate-200 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900">
                      {type ? OPERATION_LABELS[type] ?? type : 'Operation'}
                    </span>
                    <StatusBadge status={operation.status} />
                  </div>
                  <div className="text-slate-500">
                    Attempts: {operation.attempt_count} · via {operation.provider_id} · updated{' '}
                    <span title={operation.updated_at}>{formatDate(operation.updated_at)}</span>
                  </div>
                  {operation.error && (
                    <div className="flex items-start space-x-1.5 text-amber-800">
                      <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                      <span>
                        [{operation.error.error.code}] {operation.error.error.message}
                      </span>
                    </div>
                  )}
                  {label && (
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-slate-500">Simulated label: not valid for postage.</span>
                      <button
                        type="button"
                        onClick={() => handleDownload(label)}
                        disabled={downloading === label}
                        className="px-3 py-1.5 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white rounded-lg font-semibold flex items-center space-x-1"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>{downloading === label ? 'Downloading...' : 'Download label (PDF)'}</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
          {downloadError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs">
              Label download failed: {downloadError}
            </div>
          )}
        </Section>
      )}

      <Section title="Notice to the customer">
        {notifications.length === 0 ? (
          <Empty>No notice to the customer is recorded yet.</Empty>
        ) : (
          notifications.map((notice) => (
            <div
              key={notice.notification_id}
              className="p-4 bg-white rounded-xl border border-slate-200 text-xs space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center space-x-1.5 font-semibold text-slate-900">
                  <Send className="w-3.5 h-3.5 text-slate-500" />
                  <span>{NOTICE_OUTCOMES[notice.outcome] ?? notice.outcome}</span>
                </span>
                <StatusBadge status={notice.status} />
              </div>
              <p className="text-slate-800 whitespace-pre-wrap">{notice.message}</p>
              {notice.next_steps.length > 0 && (
                <ul className="list-disc pl-4 space-y-0.5 text-slate-700">
                  {notice.next_steps.map((step, index) => (
                    <li key={index} className="break-words">
                      {step}
                    </li>
                  ))}
                </ul>
              )}
              <div className="text-slate-500">
                Attempts: {notice.attempt_count} ·{' '}
                {notice.sent_at ? (
                  <>
                    sent <span title={notice.sent_at}>{formatDate(notice.sent_at)}</span>
                  </>
                ) : (
                  <>
                    not sent yet · updated <span title={notice.updated_at}>{formatDate(notice.updated_at)}</span>
                  </>
                )}
              </div>
              {notice.error && (
                <div className="flex items-start space-x-1.5 text-rose-800">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                  <span>
                    [{notice.error.error.code}] {notice.error.error.message}
                  </span>
                </div>
              )}
            </div>
          ))
        )}
      </Section>
    </div>
  );
};
