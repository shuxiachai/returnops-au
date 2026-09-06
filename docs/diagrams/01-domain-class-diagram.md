# Domain Class Diagram

> **MBSE Model Type**: Structural Class Diagram  
> **Course Requirement**: System structure, domain entities, collaborations, interdependencies  
> **Traceability**: [FR-001 to FR-012 and NFR-001 to NFR-009](../04-requirements-and-backlog.md)

---

## 1. Mermaid UML Class Diagram

```mermaid
classDiagram
    direction TB

    class ReturnCase {
        +UUID case_id
        +DateTime created_at
        +DateTime updated_at
        +CaseStatus status
        +RequestType classified_request_type
        +get_latest_proposal() DecisionProposal
        +get_active_approval() ApprovalRecord
    }

    class Customer {
        +String customer_id
        +String name
        +String email
        +String phone
    }

    class OrderSnapshot {
        +String order_id
        +String order_number
        +String provider_id
        +String provider_version
        +DateTime captured_at
        +DateTime order_date
        +DateTime fulfillment_date
        +String payment_status
        +String fulfillment_status
        +Float total_amount
        +String currency
    }

    class LineItem {
        +String item_id
        +String sku
        +String title
        +Int quantity
        +Float unit_price
        +Boolean returnable
    }

    class CustomerStatement {
        +UUID statement_id
        +String raw_text
        +DateTime submitted_at
        +String extracted_order_number
        +String extracted_item_title
        +String claimed_issue
        +String requested_remedy
    }

    class EvidenceItem {
        +UUID evidence_id
        +EvidenceType type
        +String uri_or_content
        +String description
        +EvidenceVerificationStatus verification_status
        +DateTime uploaded_at
    }

    class EvidenceAssessment {
        +String criterion_id
        +EvidenceAssessmentStatus status
        +UUID[] evidence_refs
        +String conflict_summary
        +String follow_up_question
        +DateTime assessed_at
    }

    class PolicyDocument {
        +String source_id
        +String source_version
        +String title
        +String source_type
        +String content_hash
        +DateTime effective_at
        +DateTime curated_at
    }

    class PolicyPassage {
        +String source_id
        +String source_version
        +String content_hash
        +String title
        +String url
        +String section
        +String text_snippet
        +Float confidence_score
        +DateTime retrieved_at
    }

    class DecisionProposal {
        +UUID proposal_id
        +Int proposal_version
        +String schema_version
        +RequestType request_type
        +RemedyType recommended_remedy
        +Float confidence_score
        +String rationale
        +String[] missing_information
        +RemedyType[] alternative_remedies
        +Float estimated_cost
        +Boolean requires_escalation
        +DateTime created_at
    }

    class RiskFinding {
        +UUID finding_id
        +RiskLevel risk_level
        +RiskCategory category
        +String reason
        +String suggested_action
        +DateTime detected_at
    }

    class ApprovalRecord {
        +UUID approval_id
        +UUID case_id
        +UUID proposal_id_ref
        +Int proposal_version
        +String authenticated_approver_id
        +ApprovalDecision decision
        +RemedyType optional_permitted_remedy
        +Float optional_max_approved_amount
        +String[] permitted_commands
        +String command_scope_hash
        +String notes
        +DateTime decided_at
        +DateTime expires_at
    }

    class ToolCommand {
        +UUID command_id
        +UUID case_id
        +UUID proposal_id_ref
        +String idempotency_key
        +String tool_name
        +Dict parameters
        +String allowlist_version
        +ToolCommandStatus status
        +UUID approval_id_ref
        +Dict result
        +String error_message
        +DateTime created_at
        +DateTime executed_at
    }

    class AuditEvent {
        +UUID event_id
        +UUID case_id
        +UUID correlation_id
        +DateTime timestamp
        +ActorType actor_type
        +String actor_id
        +String component_version
        +String source_version
        +String action
        +String outcome
        +String error_type
        +Boolean sensitive_content_redacted
        +CaseStatus previous_state
        +CaseStatus new_state
        +Dict payload
    }

    %% Relationships
    ReturnCase "1" *-- "1" Customer : references
    ReturnCase "1" *-- "0..1" OrderSnapshot : verified_from
    OrderSnapshot "1" *-- "1..*" LineItem : contains
    ReturnCase "1" o-- "0..1" LineItem : matched_item
    ReturnCase "1" *-- "1..*" CustomerStatement : preserves
    ReturnCase "1" *-- "0..*" EvidenceItem : includes
    ReturnCase "1" *-- "0..*" EvidenceAssessment : assesses
    ReturnCase "1" *-- "0..*" PolicyPassage : retrieved_grounds
    ReturnCase "1" *-- "0..*" DecisionProposal : produces
    ReturnCase "1" *-- "0..*" RiskFinding : flags
    ReturnCase "1" *-- "0..*" ApprovalRecord : authorizes
    ReturnCase "1" *-- "0..*" ToolCommand : dispatches
    ReturnCase "1" *-- "1..*" AuditEvent : logs_to
    
    DecisionProposal "1" o-- "0..*" PolicyPassage : cites
    PolicyDocument "1" *-- "1..*" PolicyPassage : contains
    EvidenceAssessment "0..*" o-- "0..*" EvidenceItem : references
    DecisionProposal "1" o-- "0..*" RiskFinding : reviewed_by
    DecisionProposal "1" <-- "0..*" ApprovalRecord : decides_version
    ApprovalRecord "1" <-- "0..*" ToolCommand : authorised_by
```

---

## 2. Multiplicity and Invariants

1. **Proposal Version Binding**: An `ApprovalRecord` refers to exactly one current `DecisionProposal` ID and version for the same `ReturnCase`.
2. **Decision Does Not Always Grant Authority**: Reject, revision, and escalation decisions have an empty command set. Only an approved decision may contain remedy, amount, command, and expiry scope.
3. **Complete Dispatch Guard**: Every high-impact `ToolCommand` must match an unexpired approved record for the same case and current proposal, authenticated actor, command set, parameters/amount, and allowlist version.
4. **Idempotent Effect**: `idempotency_key` is unique per logical command effect. A prior successful command is returned rather than executed again.
5. **Audit Immutability and Reproducibility**: `AuditEvent` entries are append-only and retain correlation, component/source version, outcome, typed error, and redaction status.
6. **Guidance Conflict Safety**: `PolicyDocument.source_type` distinguishes store policy from reviewed guidance; neither source type authorises the AI to make a final legal determination. Conflicting store-policy and approved-guidance passages remain visible, create a `RiskFinding`, and route the proposal to human review.
7. **Untrusted Content Boundary**: Customer, evidence, and retrieved text is data only. It cannot populate trusted approver identity, permitted commands, allowlist version, or workflow policy.
