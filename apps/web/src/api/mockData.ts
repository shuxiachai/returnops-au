import {
  ApprovalScope,
  CaseSummary,
  CaseView,
  CustomerCaseView,
  AnalyticsSnapshot,
  AuditEvent,
  PolicyPassage,
} from '../types/domain';

export const MOCK_CUSTOMER_CASES: Record<string, CustomerCaseView> = {
  'case_demo_001': {
    case_id: 'case_demo_001',
    case_version: 2,
    input_version: 1,
    status: 'AWAITING_INFORMATION',
    created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    statements: [
      {
        statement_id: 'stmt_orig_001',
        kind: 'ORIGINAL',
        raw_text:
          'I received the wrong item in my delivery yesterday. I ordered a Navy Blue Cashmere Crewneck (Size M) but received a Forest Green Wool Cardigan (Size L).',
        submitted_at: new Date(Date.now() - 3600000 * 4).toISOString(),
        order_reference: 'ORD-2026-9042',
        requested_outcome: 'REPLACEMENT',
        evidence_ids: ['ev_demo_01'],
      },
    ],
    evidence: [
      {
        evidence_id: 'ev_demo_01',
        filename: 'parcel_package_label.jpg',
        media_type: 'image/jpeg',
        size_bytes: 482104,
        sha256: 'a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0',
        status: 'BOUND',
        description: 'Photo of the shipping box and garment tag',
        created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
        content_path: '/v1/evidence/ev_demo_01/content',
      },
    ],
    clarification: {
      question_set_id: 'qset_demo_001',
      input_version: 1,
      questions: [
        {
          question_id: 'q_01',
          text: 'Please confirm the SKU or barcode number printed on the garment label tag.',
          reason: 'Verifying dispatch record against Sydney fulfilment centre picking batch.',
        },
        {
          question_id: 'q_02',
          text: 'Was the courier outer bag sealed and undamaged when handed over?',
          reason: 'Checking whether delivery was tampered with during StarTrack transit.',
        },
      ],
    },
    collection_windows: {
      statements: {
        kind: 'STATEMENT',
        snapshot_id: 'snap_demo_001',
        snapshot_case_version: 2,
        total_records: 1,
        preview_count: 1,
        unavailable_count: 0,
        truncated: false,
        start_cursor: 'cur_demo001statements',
      },
      evidence: {
        kind: 'EVIDENCE',
        snapshot_id: 'snap_demo_001',
        snapshot_case_version: 2,
        total_records: 1,
        preview_count: 1,
        unavailable_count: 0,
        truncated: false,
        start_cursor: 'cur_demo001evidence',
      },
    },
  },
  'case_demo_002': {
    case_id: 'case_demo_002',
    case_version: 3,
    input_version: 2,
    status: 'RISK_REVIEW',
    created_at: new Date(Date.now() - 3600000 * 8).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 1).toISOString(),
    statements: [
      {
        statement_id: 'stmt_orig_002',
        kind: 'ORIGINAL',
        raw_text:
          'The artisan teapot arrived completely shattered with a broken lid and cracked base.',
        submitted_at: new Date(Date.now() - 3600000 * 8).toISOString(),
        order_reference: 'ORD-2026-8819',
        requested_outcome: 'REFUND',
      },
    ],
    evidence: [
      {
        evidence_id: 'ev_demo_02',
        filename: 'shattered_teapot.png',
        media_type: 'image/png',
        size_bytes: 1204890,
        sha256: 'b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef01a',
        status: 'BOUND',
        description: 'Photo showing broken ceramic parts inside packing paper',
        created_at: new Date(Date.now() - 3600000 * 8).toISOString(),
        content_path: '/v1/evidence/ev_demo_02/content',
      },
    ],
  },
  'case_demo_003': {
    case_id: 'case_demo_003',
    case_version: 4,
    input_version: 1,
    status: 'AWAITING_APPROVAL',
    created_at: new Date(Date.now() - 3600000 * 12).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 3).toISOString(),
    statements: [
      {
        statement_id: 'stmt_orig_003',
        kind: 'ORIGINAL',
        raw_text: 'Changed my mind on the linen bedsheet set. Unopened in original packaging.',
        submitted_at: new Date(Date.now() - 3600000 * 12).toISOString(),
        order_reference: 'ORD-2026-7731',
        requested_outcome: 'REFUND',
      },
    ],
    evidence: [
      {
        evidence_id: 'ev_demo_03',
        filename: 'sealed_bedsheet_packaging.jpg',
        media_type: 'image/jpeg',
        size_bytes: 184320,
        sha256: '9d2fb1a4c7e305d8b6a2f0913c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f',
        status: 'BOUND',
        created_at: new Date(Date.now() - 3600000 * 11).toISOString(),
        content_path: '/v1/evidence/ev_demo_03/content',
        case_id: 'case_demo_003',
        description: 'Photograph of the sealed packaging, attached by the customer.',
      },
    ],
  },
  'case_demo_004': {
    case_id: 'case_demo_004',
    case_version: 2,
    input_version: 1,
    status: 'ESCALATED',
    created_at: new Date(Date.now() - 3600000 * 24).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 18).toISOString(),
    statements: [
      {
        statement_id: 'stmt_orig_004',
        kind: 'ORIGINAL',
        raw_text: 'Purchased 50 espresso units for office commercial project that was cancelled. Returning entire bulk order.',
        submitted_at: new Date(Date.now() - 3600000 * 24).toISOString(),
        order_reference: 'ORD-2026-6612',
        requested_outcome: 'REFUND',
      },
    ],
    evidence: [],
  },
  'case_demo_005': {
    case_id: 'case_demo_005',
    case_version: 5,
    input_version: 1,
    status: 'COMPLETED',
    created_at: new Date(Date.now() - 3600000 * 48).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 36).toISOString(),
    statements: [
      {
        statement_id: 'stmt_orig_005',
        kind: 'ORIGINAL',
        raw_text: 'My Synthbrew S2 coffee machine stopped heating within 2 hours of unboxing and trips the power switch.',
        submitted_at: new Date(Date.now() - 3600000 * 48).toISOString(),
        order_reference: 'ORD-2026-5501',
        requested_outcome: 'REFUND',
        evidence_ids: ['ev_demo_05'],
      },
    ],
    evidence: [
      {
        evidence_id: 'ev_demo_05',
        filename: 'blown_circuit_photo.jpg',
        media_type: 'image/jpeg',
        size_bytes: 840120,
        sha256: 'c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef01a2b',
        status: 'BOUND',
        description: 'Photo of the tripped circuit breaker and burned element',
        created_at: new Date(Date.now() - 3600000 * 48).toISOString(),
        content_path: '/v1/evidence/ev_demo_05/content',
      },
    ],
  },
};

// Cases case_demo_006 to case_demo_025 fill the queue past one page. They are
// still before risk review, so they carry no risk outcome, and each has a small
// case view so that every queue row can be opened (#122 item 1).
const GENERATED_QUEUE_SUMMARIES: CaseSummary[] = Array.from({ length: 20 }, (_, i) => {
  const num = String(i + 6).padStart(3, '0');
  return {
    case_id: `case_demo_${num}`,
    case_version: 1,
    input_version: 1,
    status: i % 2 === 0 ? 'UNDER_INVESTIGATION' : 'POLICY_ASSESSMENT',
    created_at: new Date(Date.now() - 3600000 * (50 + i * 2)).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * (40 + i * 2)).toISOString(),
    issue_category: i % 3 === 0 ? 'CHANGE_OF_MIND' : 'FAULTY_OR_QUALITY_ISSUE',
  };
});

function generatedQueueView(summary: CaseSummary, index: number): CaseView {
  const changeOfMind = summary.issue_category === 'CHANGE_OF_MIND';
  return {
    case_id: summary.case_id,
    case_version: summary.case_version,
    input_version: summary.input_version,
    status: summary.status,
    created_at: summary.created_at,
    updated_at: summary.updated_at,
    statements: [
      {
        statement_id: `stmt_orig_${summary.case_id}`,
        kind: 'ORIGINAL',
        raw_text: changeOfMind
          ? 'I changed my mind about this item. It is unused and still in its original box.'
          : 'The item stopped working properly after a few days of normal use.',
        submitted_at: summary.created_at,
        order_reference: `SYN-${1106 + index}`,
        requested_outcome: 'UNSPECIFIED',
      },
    ],
    evidence: [],
  };
}

// 25 synthetic cases to exercise limit=20 pagination and ensure 21st case is reachable
export const MOCK_FOUNDER_SUMMARIES: CaseSummary[] = [
  {
    case_id: 'case_demo_001',
    case_version: 2,
    input_version: 1,
    status: 'AWAITING_INFORMATION',
    created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    issue_category: 'WRONG_ITEM',
    current_risk_outcome: 'NEEDS_INFORMATION',
  },
  {
    case_id: 'case_demo_002',
    case_version: 3,
    input_version: 2,
    status: 'RISK_REVIEW',
    created_at: new Date(Date.now() - 3600000 * 8).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 1).toISOString(),
    issue_category: 'FAULTY_OR_QUALITY_ISSUE',
    current_risk_outcome: 'PASS_WITH_WARNING',
  },
  {
    case_id: 'case_demo_003',
    case_version: 4,
    input_version: 1,
    status: 'AWAITING_APPROVAL',
    created_at: new Date(Date.now() - 3600000 * 12).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 3).toISOString(),
    issue_category: 'CHANGE_OF_MIND',
    current_risk_outcome: 'PASS',
  },
  {
    case_id: 'case_demo_004',
    case_version: 2,
    input_version: 1,
    status: 'ESCALATED',
    created_at: new Date(Date.now() - 3600000 * 24).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 18).toISOString(),
    issue_category: 'OUT_OF_SCOPE',
    current_risk_outcome: 'ESCALATE',
  },
  {
    case_id: 'case_demo_005',
    case_version: 5,
    input_version: 1,
    status: 'COMPLETED',
    created_at: new Date(Date.now() - 3600000 * 48).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 36).toISOString(),
    issue_category: 'FAULTY_OR_QUALITY_ISSUE',
    current_risk_outcome: 'PASS',
  },
  ...GENERATED_QUEUE_SUMMARIES,
];

// Synthetic contract Hash (64 lowercase hex characters) for case_demo_003's preview.
export const MOCK_DEMO_003_SCOPE_FINGERPRINT =
  '5d41402abc4b2a76b9719d911017c592ae2f6c3b1d8e0f4a7c9b6e2d1f0a3b8c';

// case_demo_005's outcome (#122 item 4) in contract shapes: the APPROVE decision,
// the exact scope it authorised, both simulated operations and the customer
// notice. The times follow its audit events (approved 40 h ago, operations 38 h,
// completed 36 h). The label evidence ID downloads a Mock Mode placeholder file.
const DEMO_005_APPROVED_AT = new Date(Date.now() - 3600000 * 40).toISOString();
const DEMO_005_OPERATED_AT = new Date(Date.now() - 3600000 * 38).toISOString();
const DEMO_005_NOTIFIED_AT = new Date(Date.now() - 3600000 * 36).toISOString();
// Same form as a server-generated label (glabel_ plus 64 lowercase hex characters).
const DEMO_005_LABEL_EVIDENCE_ID = 'glabel_ed1ecf5db8b440680f3cc4e64dff8f97f51ea7f936126e1001293203ffe81d18';
const DEMO_005_SCOPE: ApprovalScope = {
  case_id: 'case_demo_005',
  input_version: 1,
  proposal_id: 'prop_demo_005',
  proposal_version: 1,
  review_id: 'rev_demo_005',
  parcel_id: 'parcel_demo_005',
  commands: [
    {
      command_id: 'cmd_demo_005_return',
      type: 'CREATE_RETURN',
      provider_id: 'provider_mock_au',
      parameters: {
        order_id: 'ord_5501',
        line_items: [{ line_item_id: 'item_501', quantity: 1 }],
        parcel_id: 'parcel_demo_005',
      },
    },
    {
      command_id: 'cmd_demo_005_label',
      type: 'GENERATE_LABEL',
      provider_id: 'provider_mock_au',
      parameters: {
        parcel_id: 'parcel_demo_005',
        return_command_id: 'cmd_demo_005_return',
        label_format: 'PDF',
        chargeable: false,
      },
    },
  ],
  currency: 'AUD',
  amount_ceiling_minor: 0,
  expires_at: new Date(Date.now() - 3600000 * 40 + 300000).toISOString(),
  allowlist_version: 'allowlist-demo-v1',
  environment: 'SIMULATED',
};

const DEMO_005_OUTCOME: Pick<CaseView, 'decisions' | 'approvals' | 'operations' | 'notifications'> = {
  decisions: [
    {
      decision_id: 'dec_demo_005',
      case_id: 'case_demo_005',
      proposal_id: 'prop_demo_005',
      proposal_version: 1,
      decision: 'APPROVE',
      principal_id: 'founder_demo',
      reason: 'Approved the simulated return and label for the reported electrical fault.',
      decided_at: DEMO_005_APPROVED_AT,
      approval_id: 'appr_demo_005',
    },
  ],
  approvals: [
    {
      approval_id: 'appr_demo_005',
      decision_id: 'dec_demo_005',
      principal_id: 'founder_demo',
      issued_at: DEMO_005_APPROVED_AT,
      preview_id: 'prev_demo_005',
      scope: DEMO_005_SCOPE,
      scope_fingerprint: '7fd6399e35b4ecf4e3c8768b2edcf8a56c66e37194ba205a25af0730418ce236',
    },
  ],
  operations: [
    {
      operation_id: 'op_demo_005_return',
      case_id: 'case_demo_005',
      case_version: 4,
      command_id: 'cmd_demo_005_return',
      approval_id: 'appr_demo_005',
      proposal_id: 'prop_demo_005',
      proposal_version: 1,
      input_version: 1,
      provider_id: 'provider_mock_au',
      operation_fingerprint: 'd0e480a08bcd31ade37509e87c21a0ce3a59b61ac1d04af03be9045d354e5590',
      status: 'SUCCEEDED',
      attempt_count: 1,
      updated_at: DEMO_005_OPERATED_AT,
      result: { type: 'CREATE_RETURN', provider_return_id: 'ret_mock_005', parcel_id: 'parcel_demo_005' },
      idempotency_key: 'op-demo-005-return',
    },
    {
      operation_id: 'op_demo_005_label',
      case_id: 'case_demo_005',
      case_version: 4,
      command_id: 'cmd_demo_005_label',
      approval_id: 'appr_demo_005',
      proposal_id: 'prop_demo_005',
      proposal_version: 1,
      input_version: 1,
      provider_id: 'provider_mock_au',
      operation_fingerprint: 'ea23f18c2072896558f8458a56c728cc26457c1f4dcf373eb1fbb8cc6eeadd93',
      status: 'SUCCEEDED',
      attempt_count: 1,
      updated_at: DEMO_005_OPERATED_AT,
      result: {
        type: 'GENERATE_LABEL',
        provider_label_id: 'lbl_mock_005',
        parcel_id: 'parcel_demo_005',
        label_evidence_id: DEMO_005_LABEL_EVIDENCE_ID,
      },
      idempotency_key: 'op-demo-005-label',
    },
  ],
  notifications: [
    {
      notification_id: 'note_demo_005',
      case_id: 'case_demo_005',
      case_version: 5,
      status: 'SENT',
      outcome: 'RETURN_CREATED',
      // The server's CORE_MOCK v2 wording (packages/returnops_domain/notification_profile.py).
      message:
        'A simulated return and parcel label have been recorded. The prototype PDF is not valid for postage. This prototype has not arranged a real shipment or made a charge.',
      next_steps: [
        `View the simulated label using authorised attachment access at /v1/evidence/${DEMO_005_LABEL_EVIDENCE_ID}/content. This PDF must not be used for postage.`,
        'Next step: ask the store operator to confirm the contact channel and any further arrangements.',
        'Drop-off: no physical drop-off is arranged. Never post a parcel using a prototype label.',
      ],
      attempt_count: 1,
      updated_at: DEMO_005_NOTIFIED_AT,
      sent_at: DEMO_005_NOTIFIED_AT,
    },
  ],
};

// Contract PolicyPassage for case_demo_003's proposal citation (#122 item 5). The
// customer case view does not carry cited passages; the Founder case view does.
const DEMO_003_CITED_PASSAGES: PolicyPassage[] = [
  {
    passage_id: 'passage_demo_store_21',
    document_id: 'doc_demo_store_policy',
    source_type: 'STORE_POLICY',
    title: 'Store policy §2.1 — 30-day change of mind',
    source_uri: 'urn:returnops:demo-store/policy#2.1',
    accessed_on: '2026-10-20',
    source_version: '2026.1',
    corpus_version: 'demo-corpus-v1',
    location: 'Store Policy §2.1',
    content:
      'A customer may return an unused item within 30 days of delivery for a refund, provided it is in its original packaging. Return shipping is paid by the store for change-of-mind returns.',
    content_sha256: 'c1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f80',
    retrieved_at: '2026-10-20T00:00:00Z',
    is_synthetic: true,
  },
];

export const MOCK_FOUNDER_CASE_VIEWS: Record<string, CaseView> = {
  'case_demo_001': {
    case_id: 'case_demo_001',
    case_version: 2,
    input_version: 1,
    status: 'AWAITING_INFORMATION',
    created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    statements: MOCK_CUSTOMER_CASES['case_demo_001'].statements,
    evidence: MOCK_CUSTOMER_CASES['case_demo_001'].evidence,
    clarification: MOCK_CUSTOMER_CASES['case_demo_001'].clarification,
    order_snapshot: {
      snapshot_id: 'snap_demo_001',
      order_id: 'ord_9042',
      provider_id: 'provider_mock_au',
      snapshot_version: 1,
      purchased_at: '2026-10-02T10:15:00Z',
      currency: 'AUD',
      line_items: [
        {
          line_item_id: 'item_101',
          sku: 'AP-CASH-BLU-M',
          description: 'Navy Blue Cashmere Crewneck (Size M)',
          quantity: 1,
          unit_price_minor: 14900,
        },
      ],
      retrieved_at: '2026-10-02T10:16:00Z',
    },
    // Hand-written, contract-shaped ExtractedFacts for Mock Mode; no model produced
    // it, and the Founder Console labels it as mock data.
    facts: {
      issue_category: 'WRONG_ITEM',
      customer_requested_outcome: 'REPLACEMENT',
      possible_basis: 'UNDETERMINED',
      assessment_status: 'MISSING_INFORMATION',
      line_items: [],
      summary:
        'The customer reports receiving a different garment from the one ordered (wrong colour, style and size) and asks for a replacement.',
    },
  },
  'case_demo_002': {
    case_id: 'case_demo_002',
    case_version: 3,
    input_version: 2,
    status: 'RISK_REVIEW',
    created_at: new Date(Date.now() - 3600000 * 8).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 1).toISOString(),
    statements: MOCK_CUSTOMER_CASES['case_demo_002'].statements,
    evidence: MOCK_CUSTOMER_CASES['case_demo_002'].evidence,
    order_snapshot: {
      snapshot_id: 'snap_demo_002',
      order_id: 'ord_8819',
      provider_id: 'provider_mock_au',
      snapshot_version: 1,
      purchased_at: '2026-10-04T14:30:00Z',
      currency: 'AUD',
      line_items: [
        {
          line_item_id: 'item_201',
          sku: 'HM-POT-CEL-01',
          description: 'Handcrafted Ceramic Teapot (Celadon)',
          quantity: 1,
          unit_price_minor: 8900,
        },
      ],
      retrieved_at: '2026-10-04T14:31:00Z',
    },
    current_proposal: {
      proposal_id: 'prop_demo_002',
      proposal_version: 1,
      recommended_action: 'PROPOSE_REFUND',
      confidence: 0.94,
      refund_amount_cents: 8900,
      return_label_required: false,
      rationale:
        'The teapot arrived broken and the pieces are a safety hazard. Under the Australian Consumer Law this may be a major failure, and store policy §4.2 lets the Founder waive the return of broken items. The Founder decides; this proposal approves nothing.',
      created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    },
    current_review: {
      review_id: 'rev_demo_002',
      outcome: 'PASS_WITH_WARNING',
      risk_score: 0.18,
      reviewed_at: new Date(Date.now() - 3600000 * 1).toISOString(),
      summary:
        'Low risk signals: delivered within 5 days and no earlier returns on record. No conflicting evidence found; the decision stays with the Founder.',
      findings: [
        {
          finding_id: 'find_02a',
          category: 'SUPPORT',
          severity: 'INFO',
          message: 'Ceramics broken in transit may be a major failure under the ACL (conditional guidance, not a legal determination).',
          citation_ids: ['ACL s54'],
          evidence_ids: ['ev_demo_02'],
        },
        {
          finding_id: 'find_02b',
          category: 'SCOPE',
          severity: 'WARNING',
          message: 'No earlier returns on record. Store policy §4.2 lets the Founder waive the return of broken items; nothing is waived until the Founder decides.',
          citation_ids: ['Merchant Policy §4.2'],
          evidence_ids: [],
        },
      ],
      policy_citations: [
        'ACL Section 54 (Acceptable Quality)',
        'Merchant Policy §4.2 (Damaged in Transit / Safety Exclusion)',
      ],
    },
  },
  'case_demo_003': {
    case_id: 'case_demo_003',
    case_version: 4,
    input_version: 1,
    status: 'AWAITING_APPROVAL',
    created_at: new Date(Date.now() - 3600000 * 12).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 3).toISOString(),
    statements: MOCK_CUSTOMER_CASES['case_demo_003'].statements,
    evidence: MOCK_CUSTOMER_CASES['case_demo_003'].evidence,
    cited_passages: DEMO_003_CITED_PASSAGES,
    order_snapshot: {
      snapshot_id: 'snap_demo_003',
      order_id: 'ord_7731',
      provider_id: 'provider_mock_au',
      snapshot_version: 1,
      purchased_at: '2026-09-28T16:00:00Z',
      currency: 'AUD',
      line_items: [
        {
          line_item_id: 'item_301',
          sku: 'LN-SHT-QN-OAT',
          description: 'French Linen Sheet Set (Queen, Oatmeal)',
          quantity: 1,
          unit_price_minor: 22000,
        },
      ],
      retrieved_at: '2026-09-28T16:01:00Z',
    },
    current_proposal: {
      proposal_id: 'prop_demo_003',
      proposal_version: 1,
      recommended_action: 'PROPOSE_REFUND',
      confidence: 0.96,
      refund_amount_cents: 22000,
      return_label_required: true,
      rationale:
        '30-day change of mind policy applies. Return shipping label required for return to Melbourne distribution hub.',
      // Contract DecisionPacket fields (#122 item 5): what the advice is
      // conditional on, what it could not settle, and the passages it cites.
      conditions: [
        'The item is unopened and in its original packaging, as the customer states.',
        'The return goes to the Melbourne distribution hub with the label this approval authorises.',
      ],
      unresolved_questions: [
        // The attached photograph shows the packaging; it cannot show the item unused.
        'The photograph shows the packaging sealed; whether the item is unused is the customer word only.',
      ],
      citations: [
        {
          citation_id: 'cite_demo_003_1',
          passage_id: 'passage_demo_store_21',
          document_id: 'doc_demo_store_policy',
          source_version: '2026.1',
          corpus_version: 'demo-corpus-v1',
          content_sha256: 'c1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f80',
          location: 'Store Policy §2.1',
        },
      ],
      created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    },
    current_review: {
      review_id: 'rev_demo_003',
      outcome: 'PASS',
      risk_score: 0.05,
      reviewed_at: new Date(Date.now() - 3600000 * 3).toISOString(),
      summary:
        'Unopened item within the 30-day return window. If the Founder approves, the simulated return and label in the preview are the only actions.',
      findings: [
        {
          finding_id: 'find_03',
          category: 'SUPPORT',
          severity: 'INFO',
          message: 'Claim within 30-day return policy window.',
          citation_ids: ['Store Policy §2.1'],
          evidence_ids: [],
        },
      ],
      policy_citations: ['Store Policy §2.1 (30-day Change of Mind)'],
    },
    action_preview: {
      preview_id: 'prev_demo_003',
      scope_fingerprint: MOCK_DEMO_003_SCOPE_FINGERPRINT,
      // Contract ApprovalScope: the two fixed commands, no payment, a short expiry
      // (getFounderCase gives expires_at a fresh window on every Mock Mode read).
      scope: {
        case_id: 'case_demo_003',
        input_version: 1,
        proposal_id: 'prop_demo_003',
        proposal_version: 1,
        review_id: 'rev_demo_003',
        parcel_id: 'parcel_demo_003',
        commands: [
          {
            command_id: 'cmd_demo_003_return',
            type: 'CREATE_RETURN',
            provider_id: 'provider_mock_au',
            parameters: {
              order_id: 'ord_7731',
              line_items: [{ line_item_id: 'item_301', quantity: 1 }],
              parcel_id: 'parcel_demo_003',
            },
          },
          {
            command_id: 'cmd_demo_003_label',
            type: 'GENERATE_LABEL',
            provider_id: 'provider_mock_au',
            parameters: {
              parcel_id: 'parcel_demo_003',
              return_command_id: 'cmd_demo_003_return',
              label_format: 'PDF',
              chargeable: false,
            },
          },
        ],
        currency: 'AUD',
        amount_ceiling_minor: 0,
        expires_at: new Date(Date.now() + 300000).toISOString(),
        allowlist_version: 'allowlist-demo-v1',
        environment: 'SIMULATED',
      },
      operation_type: 'GENERATE_RETURN_CONSIGNMENT',
      details: {
        carrier: 'Australia Post eParcel',
        service_code: 'RETURN_PARCEL_STANDARD',
        destination: 'ReturnOps Fulfilment Hub, Truganina VIC 3029',
      },
    },
  },
  'case_demo_004': {
    case_id: 'case_demo_004',
    case_version: 2,
    input_version: 1,
    status: 'ESCALATED',
    created_at: new Date(Date.now() - 3600000 * 24).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 18).toISOString(),
    statements: MOCK_CUSTOMER_CASES['case_demo_004'].statements,
    evidence: [],
    order_snapshot: {
      snapshot_id: 'snap_demo_004',
      order_id: 'ord_6612',
      provider_id: 'provider_mock_au',
      snapshot_version: 1,
      purchased_at: '2026-09-15T09:00:00Z',
      currency: 'AUD',
      line_items: [
        {
          line_item_id: 'item_401',
          sku: 'SYN-ESP-COMM-50',
          description: 'Commercial Bulk Espresso Machine Lot (50 units)',
          quantity: 50,
          unit_price_minor: 49000,
        },
      ],
      retrieved_at: '2026-09-15T09:01:00Z',
    },
    current_proposal: {
      proposal_id: 'prop_demo_004',
      proposal_version: 1,
      recommended_action: 'REFER_FOR_MANUAL_HANDLING',
      confidence: 0.88,
      rationale:
        'Customer indicates 50 commercial units returned due to commercial project cancellation; exceeds retail consumer protection scope.',
      created_at: new Date(Date.now() - 3600000 * 20).toISOString(),
    },
    current_review: {
      review_id: 'rev_demo_004',
      outcome: 'ESCALATE',
      risk_score: 0.92,
      reviewed_at: new Date(Date.now() - 3600000 * 19).toISOString(),
      summary:
        'High business risk: a bulk commercial order is outside the store retail consumer terms. The case is escalated, so the Founder can take it over manually or ask for a revised proposal.',
      findings: [
        {
          finding_id: 'find_04a',
          category: 'SCOPE',
          severity: 'BLOCK',
          message: 'Bulk order volume (50 units) exceeds consumer threshold under Store Terms §1.4.',
          citation_ids: ['Store Policy §1.4 (Commercial Exclusions)'],
          evidence_ids: [],
        },
        {
          finding_id: 'find_04b',
          category: 'AUTHORITY',
          severity: 'BLOCK',
          message: 'The claim ($24,500.00) is far above a retail return. Only the Founder can decide it, and this prototype moves no money.',
          citation_ids: ['Operations Guard §3.1'],
          evidence_ids: [],
        },
      ],
      policy_citations: [
        'Store Policy §1.4 (Commercial Exclusions)',
        'Operations Guard §3.1 (Founder-only decisions)',
      ],
    },
  },
  'case_demo_005': {
    case_id: 'case_demo_005',
    case_version: 5,
    input_version: 1,
    status: 'COMPLETED',
    created_at: new Date(Date.now() - 3600000 * 48).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 36).toISOString(),
    statements: MOCK_CUSTOMER_CASES['case_demo_005'].statements,
    evidence: MOCK_CUSTOMER_CASES['case_demo_005'].evidence,
    order_snapshot: {
      snapshot_id: 'snap_demo_005',
      order_id: 'ord_5501',
      provider_id: 'provider_mock_au',
      snapshot_version: 1,
      purchased_at: '2026-09-10T11:20:00Z',
      currency: 'AUD',
      line_items: [
        {
          line_item_id: 'item_501',
          sku: 'SYN-ESP-S2',
          description: 'Synthbrew S2 Espresso Machine',
          quantity: 1,
          unit_price_minor: 69900,
        },
      ],
      retrieved_at: '2026-09-10T11:21:00Z',
    },
    current_proposal: {
      proposal_id: 'prop_demo_005',
      proposal_version: 1,
      recommended_action: 'PROPOSE_REFUND',
      confidence: 0.99,
      refund_amount_cents: 69900,
      return_label_required: true,
      rationale:
        'An electrical fault within 2 hours of delivery may be a major failure under ACL section 54 (conditional guidance). The Founder approved the simulated return and label; this prototype moves no money.',
      created_at: new Date(Date.now() - 3600000 * 44).toISOString(),
    },
    current_review: {
      review_id: 'rev_demo_005',
      outcome: 'PASS',
      risk_score: 0.02,
      reviewed_at: new Date(Date.now() - 3600000 * 43).toISOString(),
      summary:
        'The photo evidence matches the reported fault. No conflicting evidence found.',
      findings: [
        {
          finding_id: 'find_05',
          category: 'SUPPORT',
          severity: 'INFO',
          message: 'Customer provided clear image evidence of burned element and invoice.',
          citation_ids: ['ACL s54'],
          evidence_ids: ['ev_demo_05'],
        },
      ],
      policy_citations: ['ACL Section 54 (Acceptable Quality)'],
    },
    ...DEMO_005_OUTCOME,
  },
  ...Object.fromEntries(
    GENERATED_QUEUE_SUMMARIES.map((summary, index) => [summary.case_id, generatedQueueView(summary, index)])
  ),
};

export const MOCK_AUDIT_EVENTS: Record<string, AuditEvent[]> = {
  'case_demo_001': [
    {
      event_id: 'evt_001_1',
      sequence: 1,
      event_type: 'CASE_CREATED',
      actor: {
        kind: 'HUMAN',
        role: 'CUSTOMER',
        principal_id: 'customer_demo_one',
      },
      occurred_at: new Date(Date.now() - 3600000 * 4).toISOString(),
      previous_event_hash: '0000000000000000000000000000000000000000000000000000000000000000',
      event_hash: '3f789ab2e45c71d98fa6312456e4ab91024bc681a93e8765412bba32014ff901',
      payload: { original_message_length: 147, order_reference: 'ORD-2026-9042' },
    },
    {
      event_id: 'evt_001_2',
      sequence: 2,
      event_type: 'EVIDENCE_BOUND',
      actor: {
        kind: 'HUMAN',
        role: 'CUSTOMER',
        principal_id: 'customer_demo_one',
      },
      occurred_at: new Date(Date.now() - 3600000 * 4).toISOString(),
      previous_event_hash: '3f789ab2e45c71d98fa6312456e4ab91024bc681a93e8765412bba32014ff901',
      event_hash: 'a9c51239eb88047c6d123e459a0f12c49982467d01824a7bc9103e56a7bc12e4',
      payload: { evidence_id: 'ev_demo_01', filename: 'parcel_package_label.jpg' },
    },
    {
      event_id: 'evt_001_3',
      sequence: 3,
      event_type: 'INTAKE_ASSESSMENT_COMPLETED',
      actor: {
        kind: 'SERVICE',
        component_id: 'deterministic-intake-v1',
      },
      occurred_at: new Date(Date.now() - 3600000 * 2).toISOString(),
      previous_event_hash: 'a9c51239eb88047c6d123e459a0f12c49982467d01824a7bc9103e56a7bc12e4',
      event_hash: 'bf891234ea76901c890123fa78bc912349012356cdae78901234e45601278abc',
      payload: {
        transition_to: 'AWAITING_INFORMATION',
        question_count: 2,
        question_set_id: 'qset_demo_001',
      },
    },
  ],
  'case_demo_002': [
    {
      event_id: 'evt_002_1',
      sequence: 1,
      event_type: 'CASE_CREATED',
      actor: { kind: 'HUMAN', role: 'CUSTOMER', principal_id: 'customer_demo_two' },
      occurred_at: new Date(Date.now() - 3600000 * 8).toISOString(),
      previous_event_hash: '0000000000000000000000000000000000000000000000000000000000000000',
      event_hash: '1111111111111111111111111111111111111111111111111111111111111111',
      payload: { order_reference: 'ORD-2026-8819' },
    },
    {
      event_id: 'evt_002_2',
      sequence: 2,
      event_type: 'RISK_REVIEW_COMPLETED',
      actor: { kind: 'SERVICE', component_id: 'risk-reviewer-c' },
      occurred_at: new Date(Date.now() - 3600000 * 1).toISOString(),
      previous_event_hash: '1111111111111111111111111111111111111111111111111111111111111111',
      event_hash: '2222222222222222222222222222222222222222222222222222222222222222',
      payload: { outcome: 'PASS_WITH_WARNING' },
    },
  ],
  'case_demo_003': [
    {
      event_id: 'evt_003_1',
      sequence: 1,
      event_type: 'CASE_CREATED',
      actor: { kind: 'HUMAN', role: 'CUSTOMER', principal_id: 'customer_demo_three' },
      occurred_at: new Date(Date.now() - 3600000 * 12).toISOString(),
      previous_event_hash: '0000000000000000000000000000000000000000000000000000000000000000',
      event_hash: '3333333333333333333333333333333333333333333333333333333333333333',
      payload: { order_reference: 'ORD-2026-7731' },
    },
    {
      event_id: 'evt_003_2',
      sequence: 2,
      event_type: 'ASSESSMENT_PROPOSAL_GENERATED',
      actor: { kind: 'SERVICE', component_id: 'returns-assessment-agent' },
      occurred_at: new Date(Date.now() - 3600000 * 4).toISOString(),
      previous_event_hash: '3333333333333333333333333333333333333333333333333333333333333333',
      event_hash: '4444444444444444444444444444444444444444444444444444444444444444',
      payload: { recommended_action: 'PROPOSE_REFUND', confidence: 0.96 },
    },
    {
      event_id: 'evt_003_3',
      sequence: 3,
      event_type: 'RISK_REVIEW_COMPLETED',
      actor: { kind: 'SERVICE', component_id: 'risk-reviewer-c' },
      occurred_at: new Date(Date.now() - 3600000 * 3).toISOString(),
      previous_event_hash: '4444444444444444444444444444444444444444444444444444444444444444',
      event_hash: '5555555555555555555555555555555555555555555555555555555555555555',
      payload: { outcome: 'PASS', score: 0.05 },
    },
    {
      event_id: 'evt_003_4',
      sequence: 4,
      event_type: 'APPROVAL_PREVIEW_GENERATED',
      actor: { kind: 'SERVICE', component_id: 'operations-service' },
      occurred_at: new Date(Date.now() - 3600000 * 3).toISOString(),
      previous_event_hash: '5555555555555555555555555555555555555555555555555555555555555555',
      event_hash: '6666666666666666666666666666666666666666666666666666666666666666',
      payload: { preview_id: 'prev_demo_003', scope_fingerprint: MOCK_DEMO_003_SCOPE_FINGERPRINT },
    },
  ],
  'case_demo_004': [
    {
      event_id: 'evt_004_1',
      sequence: 1,
      event_type: 'CASE_CREATED',
      actor: { kind: 'HUMAN', role: 'CUSTOMER', principal_id: 'customer_demo_four' },
      occurred_at: new Date(Date.now() - 3600000 * 24).toISOString(),
      previous_event_hash: '0000000000000000000000000000000000000000000000000000000000000000',
      event_hash: '7777777777777777777777777777777777777777777777777777777777777777',
      payload: { order_reference: 'ORD-2026-6612', amount_cents: 2450000 },
    },
    {
      event_id: 'evt_004_2',
      sequence: 2,
      event_type: 'RISK_REVIEW_ESCALATED',
      actor: { kind: 'SERVICE', component_id: 'risk-reviewer-c' },
      occurred_at: new Date(Date.now() - 3600000 * 19).toISOString(),
      previous_event_hash: '7777777777777777777777777777777777777777777777777777777777777777',
      event_hash: '8888888888888888888888888888888888888888888888888888888888888888',
      payload: { outcome: 'ESCALATE', reason: 'Commercial bulk order exceeds authority' },
    },
  ],
  'case_demo_005': [
    {
      event_id: 'evt_005_1',
      sequence: 1,
      event_type: 'CASE_CREATED',
      actor: { kind: 'HUMAN', role: 'CUSTOMER', principal_id: 'customer_demo_five' },
      occurred_at: new Date(Date.now() - 3600000 * 48).toISOString(),
      previous_event_hash: '0000000000000000000000000000000000000000000000000000000000000000',
      event_hash: '9999999999999999999999999999999999999999999999999999999999999999',
      payload: { order_reference: 'ORD-2026-5501' },
    },
    {
      event_id: 'evt_005_2',
      sequence: 2,
      event_type: 'EVIDENCE_BOUND',
      actor: { kind: 'HUMAN', role: 'CUSTOMER', principal_id: 'customer_demo_five' },
      occurred_at: new Date(Date.now() - 3600000 * 48).toISOString(),
      previous_event_hash: '9999999999999999999999999999999999999999999999999999999999999999',
      event_hash: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      payload: { evidence_id: 'ev_demo_05', filename: 'blown_circuit_photo.jpg' },
    },
    {
      event_id: 'evt_005_3',
      sequence: 3,
      event_type: 'FOUNDER_DECISION_ACCEPTED',
      actor: { kind: 'HUMAN', role: 'FOUNDER', principal_id: 'founder_demo' },
      occurred_at: new Date(Date.now() - 3600000 * 40).toISOString(),
      previous_event_hash: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      event_hash: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      payload: { rationale: 'Approved the simulated return and label for the reported electrical fault.' },
    },
    {
      event_id: 'evt_005_4',
      sequence: 4,
      event_type: 'SIMULATED_RETURN_AND_LABEL_CREATED',
      actor: { kind: 'SERVICE', component_id: 'operations-service' },
      occurred_at: new Date(Date.now() - 3600000 * 38).toISOString(),
      previous_event_hash: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      event_hash: 'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
      payload: { commands: ['CREATE_RETURN', 'GENERATE_LABEL'], environment: 'SIMULATED', amount_ceiling_minor: 0 },
    },
    {
      event_id: 'evt_005_5',
      sequence: 5,
      event_type: 'CASE_COMPLETED',
      actor: { kind: 'SERVICE', component_id: 'operations-service' },
      occurred_at: new Date(Date.now() - 3600000 * 36).toISOString(),
      previous_event_hash: 'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
      event_hash: 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
      payload: { final_status: 'COMPLETED' },
    },
  ],
};

// Fixed synthetic snapshot that keeps the contract invariants: status buckets sum
// to case_count, risk buckets plus cases_without_current_review sum to case_count,
// the three latency counts sum to case_count, and buckets follow enum order.
export const MOCK_ANALYTICS: AnalyticsSnapshot = {
  as_of: new Date().toISOString(),
  filters: {},
  case_count: 128,
  cases_by_status: [
    { status: 'SUBMITTED', count: 14 },
    { status: 'AWAITING_INFORMATION', count: 22 },
    { status: 'UNDER_INVESTIGATION', count: 18 },
    { status: 'POLICY_ASSESSMENT', count: 12 },
    { status: 'RISK_REVIEW', count: 8 },
    { status: 'AWAITING_APPROVAL', count: 6 },
    { status: 'APPROVED', count: 24 },
    { status: 'ESCALATED', count: 3 },
    { status: 'COMPLETED', count: 16 },
    { status: 'REJECTED', count: 5 },
  ],
  current_risk_counts: [
    { outcome: 'PASS', count: 36 },
    { outcome: 'PASS_WITH_WARNING', count: 12 },
    { outcome: 'REVISE', count: 4 },
    { outcome: 'NEEDS_INFORMATION', count: 15 },
    { outcome: 'ESCALATE', count: 3 },
  ],
  cases_without_current_review: 58,
  proposal_latency: {
    metric_version: 'proposal-latency-v1',
    sample_count: 70,
    failed_count: 2,
    unmeasured_count: 56,
    p50_ms: 11200,
    p95_ms: 46500,
  },
};
