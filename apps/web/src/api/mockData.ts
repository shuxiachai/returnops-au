import {
  CaseSummary,
  CaseView,
  CustomerCaseView,
  AnalyticsSnapshot,
  AuditEvent,
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
        total_records: 1,
        preview_count: 1,
        unavailable_count: 0,
        truncated: false,
      },
    },
  },
  'case_demo_002': {
    case_id: 'case_demo_002',
    case_version: 3,
    input_version: 2,
    status: 'UNDER_INVESTIGATION',
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
    evidence: [],
  },
};

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
      order_id: 'ord_9042',
      order_number: 'ORD-2026-9042',
      order_date: '2026-10-02T10:15:00Z',
      total_amount_cents: 14900,
      currency: 'AUD',
      status: 'DELIVERED',
      items: [
        {
          item_id: 'item_101',
          product_name: 'Navy Blue Cashmere Crewneck',
          sku: 'AP-CASH-BLU-M',
          quantity: 1,
          unit_price_cents: 14900,
        },
      ],
    },
    facts: {
      reported_issue: 'WRONG_ITEM',
      received_item: 'Forest Green Wool Cardigan (Size L)',
      customer_intent: 'REPLACEMENT',
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
    order_snapshot: {
      order_id: 'ord_8819',
      order_number: 'ORD-2026-8819',
      order_date: '2026-10-04T14:30:00Z',
      total_amount_cents: 8900,
      currency: 'AUD',
      status: 'DELIVERED',
      items: [
        {
          item_id: 'item_201',
          product_name: 'Handcrafted Ceramic Teapot (Celadon)',
          sku: 'HM-POT-CEL-01',
          quantity: 1,
          unit_price_cents: 8900,
        },
      ],
    },
    current_proposal: {
      proposal_id: 'prop_demo_002',
      proposal_version: 1,
      outcome: 'REFUND',
      refund_amount_cents: 8900,
      return_label_required: false,
      confidence_score: 0.94,
      rationale:
        'Product is unrepairable and shattered glassware/ceramic presents safety hazard. Australian Consumer Law statutory guarantee entitles full refund without return under safety policy §4.2.',
      created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    },
    current_review: {
      review_id: 'rev_demo_002',
      risk_outcome: 'PASS_WITH_WARNING',
      risk_score: 0.18,
      summary:
        'Low fraud probability. Delivery within 5 days, customer has 0 prior return history. Recommend instant refund authorisation.',
      policy_citations: [
        'ACL Section 54 (Acceptable Quality)',
        'Merchant Policy §4.2 (Damaged in Transit / Safety Exclusion)',
      ],
      evaluated_at: new Date(Date.now() - 3600000 * 1).toISOString(),
    },
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
        raw_text:
          'Changed my mind on the linen bedsheet set. Unopened in original packaging.',
        submitted_at: new Date(Date.now() - 3600000 * 12).toISOString(),
        order_reference: 'ORD-2026-7731',
        requested_outcome: 'REFUND',
      },
    ],
    evidence: [],
    order_snapshot: {
      order_id: 'ord_7731',
      order_number: 'ORD-2026-7731',
      order_date: '2026-09-28T16:00:00Z',
      total_amount_cents: 22000,
      currency: 'AUD',
      status: 'DELIVERED',
      items: [
        {
          item_id: 'item_301',
          product_name: 'French Linen Sheet Set (Queen, Oatmeal)',
          sku: 'LN-SHT-QN-OAT',
          quantity: 1,
          unit_price_cents: 22000,
        },
      ],
    },
    current_proposal: {
      proposal_id: 'prop_demo_003',
      proposal_version: 1,
      outcome: 'REFUND',
      refund_amount_cents: 22000,
      return_label_required: true,
      confidence_score: 0.96,
      rationale:
        '30-day change of mind policy applies. Return shipping label required for return to Melbourne distribution hub.',
      created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    },
    current_review: {
      review_id: 'rev_demo_003',
      risk_outcome: 'PASS',
      risk_score: 0.05,
      summary:
        'Unopened standard item within 30-day return window. Authorize Australia Post return consignment.',
      policy_citations: ['Store Policy §2.1 (30-day Change of Mind)'],
      evaluated_at: new Date(Date.now() - 3600000 * 3).toISOString(),
    },
    action_preview: {
      preview_id: 'prev_demo_003',
      scope_fingerprint: 'fp_scope_98124',
      scope: {
        operation: 'GENERATE_RETURN_CONSIGNMENT',
        carrier: 'Australia Post eParcel',
      },
      operation_type: 'GENERATE_RETURN_CONSIGNMENT',
      details: {
        carrier: 'Australia Post eParcel',
        service_code: 'RETURN_PARCEL_STANDARD',
        destination: 'ReturnOps Fulfilment Hub, Truganina VIC 3029',
      },
    },
  },
};

export const MOCK_AUDIT_EVENTS: Record<string, AuditEvent[]> = {
  'case_demo_001': [
    {
      event_id: 'evt_001',
      sequence: 1,
      event_type: 'CASE_CREATED',
      actor: {
        kind: 'HUMAN',
        role: 'CUSTOMER',
        principal_id: 'customer_demo_one',
      },
      occurred_at: new Date(Date.now() - 3600000 * 4).toISOString(),
      timestamp: new Date(Date.now() - 3600000 * 4).toISOString(),
      previous_event_hash: '0000000000000000000000000000000000000000000000000000000000000000',
      previous_hash: '0000000000000000000000000000000000000000000000000000000000000000',
      event_hash: '3f789ab2e45c71d98fa6312456e4ab91024bc681a93e8765412bba32014ff901',
      current_hash: '3f789ab2e45c71d98fa6312456e4ab91024bc681a93e8765412bba32014ff901',
      payload: { original_message_length: 147, order_reference: 'ORD-2026-9042' },
    },
    {
      event_id: 'evt_002',
      sequence: 2,
      event_type: 'EVIDENCE_BOUND',
      actor: {
        kind: 'HUMAN',
        role: 'CUSTOMER',
        principal_id: 'customer_demo_one',
      },
      occurred_at: new Date(Date.now() - 3600000 * 4).toISOString(),
      timestamp: new Date(Date.now() - 3600000 * 4).toISOString(),
      previous_event_hash: '3f789ab2e45c71d98fa6312456e4ab91024bc681a93e8765412bba32014ff901',
      previous_hash: '3f789ab2e45c71d98fa6312456e4ab91024bc681a93e8765412bba32014ff901',
      event_hash: 'a9c51239eb88047c6d123e459a0f12c49982467d01824a7bc9103e56a7bc12e4',
      current_hash: 'a9c51239eb88047c6d123e459a0f12c49982467d01824a7bc9103e56a7bc12e4',
      payload: { evidence_id: 'ev_demo_01', filename: 'parcel_package_label.jpg' },
    },
    {
      event_id: 'evt_003',
      sequence: 3,
      event_type: 'INTAKE_ASSESSMENT_COMPLETED',
      actor: {
        kind: 'SERVICE',
        component_id: 'deterministic-intake-v1',
      },
      occurred_at: new Date(Date.now() - 3600000 * 2).toISOString(),
      timestamp: new Date(Date.now() - 3600000 * 2).toISOString(),
      previous_event_hash: 'a9c51239eb88047c6d123e459a0f12c49982467d01824a7bc9103e56a7bc12e4',
      previous_hash: 'a9c51239eb88047c6d123e459a0f12c49982467d01824a7bc9103e56a7bc12e4',
      event_hash: 'bf891234ea76901c890123fa78bc912349012356cdae78901234e45601278abc',
      current_hash: 'bf891234ea76901c890123fa78bc912349012356cdae78901234e45601278abc',
      payload: {
        transition_to: 'AWAITING_INFORMATION',
        question_count: 2,
        question_set_id: 'qset_demo_001',
      },
    },
  ],
};

export const MOCK_ANALYTICS: AnalyticsSnapshot = {
  as_of: new Date().toISOString(),
  case_count: 128,
  cases_by_status: [
    { status: 'SUBMITTED', count: 14 },
    { status: 'AWAITING_INFORMATION', count: 22 },
    { status: 'UNDER_INVESTIGATION', count: 18 },
    { status: 'POLICY_ASSESSMENT', count: 12 },
    { status: 'RISK_REVIEW', count: 8 },
    { status: 'AWAITING_APPROVAL', count: 6 },
    { status: 'APPROVED', count: 24 },
    { status: 'COMPLETED', count: 16 },
    { status: 'REJECTED', count: 5 },
    { status: 'ESCALATED', count: 3 },
  ],
  current_risk_counts: [
    { outcome: 'PASS', count: 36 },
    { outcome: 'PASS_WITH_WARNING', count: 12 },
    { outcome: 'NEEDS_INFORMATION', count: 15 },
    { outcome: 'REVISE', count: 4 },
    { outcome: 'ESCALATE', count: 3 },
  ],
  cases_without_current_review: 58,
  proposal_latency: {
    metric_version: 'proposal-latency-v1',
    sample_count: 70,
    failed_count: 0,
    unmeasured_count: 2,
    p50_ms: 11200,
    p95_ms: 46500,
  },
};
