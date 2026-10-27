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

export type PossibleBasis =
  | 'STORE_POLICY'
  | 'CONSUMER_GUIDANCE'
  | 'BOTH'
  | 'UNDETERMINED';

export type AssessmentStatus =
  | 'SUPPORTED'
  | 'MISSING_INFORMATION'
  | 'CONFLICTING'
  | 'UNCERTAIN'
  | 'OUT_OF_SCOPE';

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
  requested_outcome?: RequestedOutcome;
  question_id?: string;
  // Demo extensions, not contract fields (#122 item 5): the v1 CustomerStatement
  // carries neither an order reference nor evidence ids, so a live response never
  // has them and anything that renders them is showing fixture data only.
  order_reference?: string;
  evidence_ids?: string[];
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
  // Contract fields the type used to omit.
  snapshot_id: string;
  snapshot_case_version: number;
  total_records: number;
  preview_count: number;
  unavailable_count: number;
  truncated: boolean;
  start_cursor: string;
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

// Contract Citation / PolicyPassage (#122 item 5): what a proposal cites, and the
// retrieved passage each citation points at. The console previously rendered only
// the mock-only `policy_citations` chips, so a live case view showed no citations.
export interface Citation {
  citation_id: string;
  passage_id: string;
  document_id: string;
  source_version?: string | null;
  corpus_version: string;
  content_sha256: string;
  location: string;
}

export interface PolicyPassage {
  passage_id: string;
  document_id: string;
  // Contract enum: a passage is either store policy or reviewed consumer guidance.
  source_type: 'STORE_POLICY' | 'REVIEWED_CONSUMER_GUIDANCE';
  title: string;
  source_uri: string;
  accessed_on: string;
  source_version?: string | null;
  corpus_version: string;
  location: string;
  content: string;
  content_sha256: string;
  retrieved_at: string;
  is_synthetic: boolean;
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
  // Contract DecisionPacket fields the console did not surface (#122 item 5):
  // what the proposal conditions its advice on, what it could not settle, and
  // the passages it cites.
  unresolved_questions?: string[];
  citations?: Citation[];
  // Who produced the proposal (DecisionPacket.model_run); the fixed Gate 1
  // proposal reports model_id 'fixture-no-live-model'.
  model_run?: { model_id?: string; prompt_version?: string; provider_id?: string; role?: string };
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

export interface LineSelection {
  line_item_id: string;
  quantity: number;
}

// Contract ExtractedFacts: all six fields are required and no other key is allowed.
export interface ExtractedFacts {
  issue_category: IssueCategory;
  customer_requested_outcome: RequestedOutcome;
  possible_basis: PossibleBasis;
  assessment_status: AssessmentStatus;
  line_items: LineSelection[];
  summary: string;
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

// One command inside an ApprovalScope. The contract fixes two: CREATE_RETURN
// (order_id, line_items, parcel_id) then GENERATE_LABEL (parcel_id,
// return_command_id, label_format 'PDF', chargeable false).
export interface ApprovalCommand {
  command_id: string;
  type: 'CREATE_RETURN' | 'GENERATE_LABEL';
  provider_id: string;
  parameters: Record<string, unknown>;
}

// Contract ApprovalScope: exactly what an APPROVE of this preview authorises.
export interface ApprovalScope {
  case_id: string;
  input_version: number;
  proposal_id: string;
  proposal_version: number;
  review_id: string;
  parcel_id: string;
  commands: ApprovalCommand[];
  currency: 'AUD';
  // Always 0 in v1: an approval authorises no payment.
  amount_ceiling_minor: number;
  expires_at: string;
  allowlist_version: string;
  environment: 'SIMULATED' | 'SANDBOX';
}

export interface ActionPreview {
  preview_id: string;
  scope_fingerprint: string;
  scope: ApprovalScope;
  // Frontend-only demo extensions: the v1 ActionPreview carries no operation
  // type or parameter map, so a live response leaves these undefined and the
  // preview rows render with no fabricated operation or parameters.
  operation_type?: string;
  details?: Record<string, unknown>;
}

// Contract FounderDecisionRecord: exactly one target (proposal, processing
// failure or order-lookup block); approval_id only for an APPROVE.
export interface FounderDecisionRecord {
  decision_id: string;
  case_id: string;
  proposal_id?: string;
  proposal_version?: number;
  processing_failure_id?: string;
  order_lookup_block_id?: string;
  decision: FounderDecisionType;
  principal_id: string;
  reason: string;
  decided_at: string;
  approval_id?: string;
}

// Contract ApprovalRecord: the exact scope one APPROVE authorised.
export interface ApprovalRecord {
  approval_id: string;
  decision_id: string;
  principal_id: string;
  issued_at: string;
  preview_id: string;
  scope: ApprovalScope;
  scope_fingerprint: string;
}

// Contract OperationResult: present once the provider confirmed the operation.
export type OperationResult =
  | { type: 'CREATE_RETURN'; provider_return_id: string; parcel_id: string }
  | { type: 'GENERATE_LABEL'; provider_label_id: string; parcel_id: string; label_evidence_id: string };

export type OperationStatus = 'PENDING' | 'EXECUTING' | 'SUCCEEDED' | 'FAILED' | 'UNKNOWN' | 'RECONCILING' | 'BLOCKED';

// Contract OperationAttempt: one approved command and its provider outcome.
export interface OperationAttempt {
  operation_id: string;
  case_id: string;
  case_version: number;
  command_id: string;
  approval_id: string;
  proposal_id: string;
  proposal_version: number;
  input_version: number;
  provider_id: string;
  operation_fingerprint: string;
  status: OperationStatus;
  attempt_count: number;
  updated_at: string;
  provider_operation_id?: string;
  result?: OperationResult;
  error?: ErrorEnvelope;
  idempotency_key: string;
}

// Contract NotificationRecord: the message the customer is (or was to be) sent.
export interface NotificationRecord {
  notification_id: string;
  case_id: string;
  case_version: number;
  status: 'PENDING' | 'SENT' | 'FAILED';
  outcome: 'RETURN_CREATED' | 'REJECTED' | 'MANUAL_HANDLED';
  message: string;
  next_steps: string[];
  attempt_count: number;
  updated_at: string;
  sent_at?: string;
  error?: ErrorEnvelope;
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
  facts?: ExtractedFacts;
  order_snapshot?: OrderSnapshot;
  clarification?: ClarificationSet;
  current_proposal?: ProposalDetail;
  // Contract ProcessingFailure: why an escalated case has no proposal.
  processing_failure?: {
    failure_id: string;
    case_id: string;
    input_version: number;
    stage: 'COORDINATOR' | 'ORDER_LOOKUP' | 'RETRIEVAL' | 'ASSESSMENT' | 'RISK_REVIEW';
    error: ErrorEnvelope;
    occurred_at: string;
  };
  current_review?: RiskReviewDetail;
  action_preview?: ActionPreview;
  // What happened after the Founder decided (#122 item 4); contract shapes below.
  decisions?: FounderDecisionRecord[];
  approvals?: ApprovalRecord[];
  operations?: OperationAttempt[];
  notifications?: NotificationRecord[];
  cited_passages?: PolicyPassage[];
  // Contract OrderLookupBlock: the order lookup stopped on a conflict or a denied read.
  order_lookup_block?: {
    block_id: string;
    case_id: string;
    input_version: number;
    status: 'CONFLICT' | 'AUTHORITY_DENIED';
    message: string;
    occurred_at: string;
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

// GET /v1/founder/analytics query: created_at window [created_from, created_before)
// in RFC 3339 UTC, plus one current status. Every key is optional and sent once.
export interface AnalyticsQuery {
  created_from?: string;
  created_before?: string;
  status?: CaseStatus;
}

export interface AnalyticsSnapshot {
  as_of: string;
  // The server echoes the validated query here, {} when none was sent.
  filters: AnalyticsQuery;
  case_count: number;
  // Zero buckets are omitted; the rest arrive in contract enum order.
  cases_by_status: Array<{ status: CaseStatus; count: number }>;
  current_risk_counts: Array<{ outcome: RiskOutcome; count: number }>;
  cases_without_current_review: number;
  // sample_count + failed_count + unmeasured_count == case_count. p50_ms and
  // p95_ms are present only when sample_count > 0.
  proposal_latency: {
    metric_version: 'proposal-latency-v1';
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
