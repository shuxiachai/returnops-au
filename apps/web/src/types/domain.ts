/**
 * ReturnOps AU — Domain & API TypeScript Contracts
 * Strictly aligned with contracts/v1/schemas.json and packages/returnops_domain/schemas_v1.json
 */

export type CaseStatus =
  | 'SUBMITTED'
  | 'AWAITING_INFORMATION'
  | 'UNDER_INVESTIGATION'
  | 'POLICY_ASSESSMENT'
  | 'RISK_REVIEW'
  | 'AWAITING_APPROVAL'
  | 'APPROVED'
  | 'ACTION_IN_PROGRESS'
  | 'ACTION_FAILED'
  | 'RECONCILING'
  | 'ESCALATED'
  | 'NOTIFICATION_PENDING'
  | 'NOTIFICATION_FAILED'
  | 'COMPLETED'
  | 'REJECTED'
  | 'MANUAL_HANDLED';

export type IssueCategory =
  | 'FAULTY_OR_QUALITY_ISSUE'
  | 'WRONG_ITEM'
  | 'CHANGE_OF_MIND'
  | 'UNCLEAR'
  | 'OUT_OF_SCOPE';

export type RequestedOutcome =
  | 'REFUND'
  | 'REPLACEMENT'
  | 'REPAIR'
  | 'RETURN'
  | 'INFORMATION'
  | 'UNSPECIFIED'
  | 'OTHER';

export type RiskOutcome =
  | 'PASS'
  | 'PASS_WITH_WARNING'
  | 'REVISE'
  | 'NEEDS_INFORMATION'
  | 'ESCALATE';

export type FounderDecisionType =
  | 'APPROVE'
  | 'REJECT'
  | 'REQUEST_REVISION'
  | 'MANUAL_HANDLING';

export type CustomerHistoryKind =
  | 'STATEMENT'
  | 'EVIDENCE'
  | 'OUTCOME_MESSAGE';

export type FounderHistoryKind =
  | 'STATEMENT'
  | 'EVIDENCE'
  | 'PROPOSAL'
  | 'REVIEW'
  | 'DECISION'
  | 'APPROVAL'
  | 'OPERATION'
  | 'NOTIFICATION'
  | 'PROCESSING_FAILURE'
  | 'ORDER_LOOKUP_BLOCK';

export type UserRole = 'CUSTOMER' | 'FOUNDER';

export interface SessionPrincipal {
  principal_id: string;
  role: UserRole;
  store_id?: string;
  enabled?: boolean;
  session_id?: string;
}

export interface EvidenceAttachment {
  evidence_id: string;
  filename: string;
  media_type: string;
  size_bytes: number;
  sha256?: string;
  status?: 'STAGED' | 'BOUND';
  created_at: string;
  content_path?: string;
  description?: string;
  case_id?: string;
}

export type StagedEvidence = EvidenceAttachment;

export interface CustomerStatement {
  statement_id: string;
  kind: 'ORIGINAL' | 'CLARIFICATION';
  raw_text: string;
  submitted_at: string;
  order_reference?: string;
  requested_outcome?: RequestedOutcome;
  evidence_ids?: string[];
  question_id?: string;
}

export interface ClarificationQuestion {
  question_id: string;
  text: string;
  reason?: string;
}

export interface ClarificationSet {
  question_set_id: string;
  input_version: number;
  questions: ClarificationQuestion[];
}

export interface ClarificationAnswer {
  question_id: string;
  text: string;
}

export interface CollectionWindow {
  kind: string;
  total_records: number;
  preview_count: number;
  unavailable_count: number;
  truncated: boolean;
  start_cursor?: string;
}

export interface CustomerCaseView {
  case_id: string;
  case_version: number;
  input_version: number;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
  statements: CustomerStatement[];
  evidence: EvidenceAttachment[];
  clarification?: ClarificationSet;
  outcome_message?: string;
  collection_windows?: Record<string, CollectionWindow>;
}

export interface CreateCaseRequest {
  original_message: string;
  order_reference?: string;
  requested_outcome?: RequestedOutcome;
  evidence_ids?: string[];
}

export interface ClarificationRequest {
  expected_case_version: number;
  question_set_id: string;
  answers: ClarificationAnswer[];
  evidence_ids: string[];
}

export interface CaseSummary {
  case_id: string;
  case_version: number;
  input_version: number;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
  issue_category?: IssueCategory;
  current_risk_outcome?: RiskOutcome;
}

export interface CaseList {
  items: CaseSummary[];
  next_cursor?: string;
}

export interface ProposalDetail {
  proposal_id: string;
  proposal_version: number;
  input_version?: number;
  case_id?: string;
  recommended_action?: string;
  confidence?: number;
  rationale?: string;
  created_at: string;
  cost_responsibility_note?: string;
  conditions?: string[];
  alternatives?: string[];
  // Frontend-only demo extensions: the v1 DecisionPacket carries no refund
  // amount and no label-required flag, so a live response leaves these
  // undefined and those tiles fall back to a placeholder ("—") rather than a
  // fabricated value.
  refund_amount_cents?: number;
  return_label_required?: boolean;
}

export interface RiskFinding {
  finding_id: string;
  category: string;
  severity: 'INFO' | 'WARNING' | 'BLOCK';
  message: string;
  citation_ids?: string[];
  evidence_ids?: string[];
}

export interface RiskReviewDetail {
  review_id: string;
  case_id?: string;
  proposal_id?: string;
  proposal_version?: number;
  input_version?: number;
  corpus_version?: string;
  outcome?: RiskOutcome;
  findings?: RiskFinding[];
  reviewed_at?: string;
  revision_requests?: string[];
  questions?: ClarificationQuestion[];
  // Frontend-only demo extensions: the v1 RiskReview contract carries none of
  // these, so a live response leaves them undefined, the risk-score tile shows
  // "N/A", and the summary/citation blocks do not render at all. The contract's
  // citation data lives elsewhere (DecisionPacket.citations and
  // RiskFinding.citation_ids, the latter already present in the mock findings).
  risk_score?: number;
  summary?: string;
  policy_citations?: string[];
}

export interface LineItem {
  line_item_id: string;
  sku: string;
  description: string;
  quantity: number;
  unit_price_minor: number;
}

export interface OrderSnapshot {
  snapshot_id?: string;
  order_id: string;
  provider_id?: string;
  snapshot_version?: number;
  purchased_at: string;
  currency: string;
  line_items: LineItem[];
  retrieved_at?: string;
}

export interface ActionPreview {
  preview_id: string;
  scope_fingerprint: string;
  scope: Record<string, unknown>;
  // Frontend-only demo extensions: the v1 ActionPreview carries no operation
  // type or parameter map, so a live response leaves these undefined and the
  // preview rows render with no fabricated operation or parameters.
  operation_type?: string;
  details?: Record<string, unknown>;
}

export interface CaseView {
  case_id: string;
  case_version: number;
  input_version: number;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
  statements: CustomerStatement[];
  evidence: EvidenceAttachment[];
  facts?: Record<string, unknown>;
  order_snapshot?: OrderSnapshot;
  clarification?: ClarificationSet;
  current_proposal?: ProposalDetail;
  processing_failure?: {
    failure_id: string;
    reason: string;
    component: string;
    occurred_at: string;
  };
  current_review?: RiskReviewDetail;
  action_preview?: ActionPreview;
  decisions?: Array<{
    decision_id: string;
    decision: FounderDecisionType;
    reason: string;
    decided_at: string;
  }>;
  approvals?: Array<{
    approval_id: string;
    scope_fingerprint: string;
    approved_at: string;
  }>;
  operations?: Array<{
    operation_id: string;
    status: string;
    action: string;
  }>;
  notifications?: Array<{
    notification_id: string;
    status: string;
    recipient: string;
  }>;
  cited_passages?: string[];
  order_lookup_block?: {
    block_id: string;
    reason: string;
  };
  collection_windows?: Record<string, CollectionWindow>;
}

export interface FounderDecisionRequest {
  expected_case_version: number;
  decision: FounderDecisionType;
  reason: string;
  proposal_id?: string;
  proposal_version?: number;
  preview_id?: string;
  scope_fingerprint?: string;
  processing_failure_id?: string;
  order_lookup_block_id?: string;
}

export interface DecisionReceipt {
  case_id: string;
  case_version: number;
  decision_id: string;
  decision: FounderDecisionType;
  accepted_at: string;
  processing_status: 'ACCEPTED';
  approval_id?: string;
}

export type ActorProvenance =
  | { kind: 'HUMAN'; role: 'CUSTOMER' | 'FOUNDER'; principal_id: string }
  | { kind: 'MODEL'; model_run?: { model_id?: string; provider?: string; prompt_version?: string; run_id?: string; [key: string]: unknown } }
  | { kind: 'SERVICE'; component_id: string };

export interface AuditEvent {
  event_id: string;
  case_id?: string;
  case_version?: number;
  correlation_id?: string;
  sequence?: number;
  event_type: string;
  occurred_at?: string;
  object_ids?: string[];
  component_version?: string;
  payload_hash?: string;
  previous_event_hash?: string | null;
  event_hash?: string;
  actor: string | ActorProvenance;
  history_refs?: Array<{
    kind: string;
    object_id: string;
    object_version: number;
    case_version?: number;
  }>;
  payload?: Record<string, unknown>;
}

export interface AuditPage {
  items: AuditEvent[];
  next_cursor?: string;
}

export interface HistoryRecord {
  record_id: string;
  case_id: string;
  kind: string;
  object_id: string;
  object_version: number;
  case_version: number;
  recorded_sequence: number;
  recorded_at: string;
  retention_state: string;
  body?: unknown;
}

export interface CustomerHistoryPage {
  case_id: string;
  kind: CustomerHistoryKind;
  snapshot_id: string;
  snapshot_case_version: number;
  as_of: string;
  items: HistoryRecord[];
  next_cursor?: string;
}

export interface FounderHistoryPage {
  case_id: string;
  kind: FounderHistoryKind;
  snapshot_id: string;
  snapshot_case_version: number;
  as_of: string;
  items: HistoryRecord[];
  next_cursor?: string;
}

export interface AnalyticsSnapshot {
  as_of: string;
  filters?: Record<string, unknown>;
  case_count: number;
  cases_by_status: Array<{ status: CaseStatus; count: number }>;
  current_risk_counts: Array<{ outcome: RiskOutcome; count: number }>;
  cases_without_current_review: number;
  proposal_latency?: {
    metric_version?: string;
    sample_count: number;
    failed_count: number;
    unmeasured_count: number;
    p50_ms?: number;
    p95_ms?: number;
  };
}

export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    retryable?: boolean;
    details?: unknown;
  };
  correlation_id?: string;
}
