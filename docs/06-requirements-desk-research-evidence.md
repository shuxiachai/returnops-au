# Requirements Desk-Research Evidence Register

> **Status**: Proposed evidence baseline v0.1; not yet an amendment to the
> [requirements baseline v0.2](04-requirements-and-backlog.md)
>
> **Decision tracked by**:
> [GitHub Issue #3](https://github.com/shuxiachai/returnops-au/issues/3)
>
> **Research method**: Online-only secondary research
>
> **Research cut-off and access date**: 25 August 2026

## 1. Purpose and decision boundary

This register determines which ReturnOps AU requirements are supported by
external evidence, which need refinement before Baseline v1.0, and which must
remain explicit project hypotheses. It addresses five questions:

1. Is returns and remedy handling a material Australian commerce problem?
2. Which consumer-guarantee and evidence-handling constraints affect the MVP?
3. Which Shopify and Australia Post workflow constraints affect the models?
4. Which privacy controls are legal obligations, conditional obligations, or
   adopted design safeguards?
5. Which numerical claims can only be established by the project benchmark?

The team did not conduct interviews, field observation, a new survey,
usability research, or a legal review. This is not primary user research,
legal advice, or evidence that a production system is compliant. No source in
this register authorises an AI model to make a final legal-entitlement or
major/minor-failure determination. Proposed changes in Section 4 require team
review before they alter a requirement ID, model, acceptance test, or project
claim.

## 2. Method and evidence rules

### 2.1 Source grading

| Grade | Source class | Permitted use | Principal limitation |
|---|---|---|---|
| A1 | Current legislation | Define a legal rule within the legislation's jurisdiction and scope | Interpretation and applicability remain case-specific; legislation does not prove demand, usability, adoption, or system performance |
| A2 | Official regulator or government guidance | Inform interpretation of legal and regulatory constraints within the guidance's stated scope | Guidance is not legislation, legal advice, or a definitive decision for an individual case |
| A3 | First-party platform or provider documentation | Define that provider's API, permissions, states, and operational constraints | Does not prove that all target SMEs use or qualify for the provider |
| B | Government-commissioned empirical research with a reported method or sample | Support problem prevalence, cost, or behaviour within the study population | Metrics cannot be transferred to a different population or time definition |
| C | Industry survey or first-party operator report | Corroborate workflow friction and generate test scenarios | Commercial incentives and incomplete methods reduce confidence |
| D | Vendor case study or public community account | Discover an example AS-IS workflow or exception | Cannot support market-wide numbers or causal improvement claims |

### 2.2 Inference controls

1. A source supports only the claim and population it actually measures.
2. A complete consumer-problem resolution time is not a manual active-handling
   time and is not comparable with proposal-generation latency.
3. A regulator rule establishes a constraint, not evidence of user demand.
4. A platform's feature establishes technical feasibility, not universal SME
   access or willingness to adopt the feature.
5. Vendor improvement percentages and unattributed industry averages are not
   admitted as baseline facts.
6. Platform and regulator sources record their URL, cited API version where
   relevant, and access date because their content can change.
7. External evidence, project assumptions, prototype targets, and measured
   project results remain separate in all reports and presentations.

### 2.3 Claim status vocabulary

| Status | Meaning |
|---|---|
| `EXTERNAL_CONSTRAINT` | A current authoritative source constrains the system or workflow |
| `EXTERNAL_GUIDANCE` | An authoritative body recommends or describes a practice that informs, but does not itself impose, the project design |
| `CORROBORATED_NEED` | Multiple or method-reported secondary sources support the problem or user friction |
| `CORROBORATED_RISK` | External evidence supports a scoped compliance or operational risk without establishing its prevalence in the target market |
| `PROJECT_ASSUMPTION` | A scoped design choice that has not been established as a population fact |
| `PROTOTYPE_TARGET` | A threshold selected by the team and verified only by the project evaluation |
| `MEASURED_RESULT` | A reproducible project measurement with dataset, method, environment, and run record |

Support strength is recorded independently from source grade and claim status:

| Support | Meaning |
|---|---|
| `DIRECT` | The source directly supports the scoped statement |
| `PARTIAL` | The source supports only part of the statement and the remainder is identified |
| `CONTEXTUAL` | The source supports problem context but not the requirement or metric itself |
| `PENDING_EXPERIMENT` | The claim requires a controlled project measurement |
| `UNSUPPORTED` | No admissible evidence currently supports the claim |

## 3. Evidence register

All findings below are paraphrases. The linked source remains authoritative.

| ID | Evidence and supported finding | Grade / claim status / support | Requirement or model impact | Scope and limitation |
|---|---|---|---|---|
| EVD-001 | The government-commissioned Australian Consumer Survey 2023 ([landing page](https://consumer.gov.au/updates-and-reports/australian-consumer-survey-2023); [final report PDF](https://consumer.gov.au/sites/consumer/files/2025-02/report-australian-consumer-survey-2023.pdf)) reports that its business sample (`n=1,290`) self-estimated a mean 2.47 hours for a typical problem requiring repair, replacement, or refund. | B / `CORROBORATED_NEED` / `CONTEXTUAL` | Supports the problem statement and the need to establish a controlled manual baseline in Epic E1. It does not supply the value for NFR-005. | Cross-industry end-to-end problem handling is not e-commerce active handling, an SME-only estimate, or comparable directly with a sub-two-minute proposal target. |
| EVD-002 | Australia Post reports that 26% of its surveyed shoppers made an online return in the prior 12 months and that 28% of surveyed shoppers reported returning an item because it was faulty or incorrect; cost, drop-off, packaging uncertainty, and refund delay also contributed to poor experiences. [Returns 101](https://auspost.com.au/business/grow-your-business/business-ideas-blog/ecommerce-returns-guide) | C / `CORROBORATED_NEED` / `CONTEXTUAL` | Supports self-service intake, faulty/wrong-item scope, clear instructions, label delivery, and customer-visible progress. | Australia Post also sells returns services and the page does not expose enough sampling detail to treat the percentages as Australian population parameters, an order return rate, or a required benchmark distribution. The two percentages have shopper-level denominators and must not be presented as shares of all return events. |
| EVD-003 | The ACCC found potentially misleading returns terms while reviewing more than 2,000 Australian retail websites, including absolute exclusions and incorrect time limits. [ACCC returns-policy sweep](https://www.accc.gov.au/media-release/accc-sweep-uncovers-concerning-online-shopping-return-policies-and-terms-and-conditions) | A2 / `CORROBORATED_RISK` / `DIRECT` | Supports FR-006, FR-008, BR-001, and BR-002: store policy must not silently become a final entitlement decision, and problematic exclusions require review. | The sweep establishes compliance risk but does not provide a non-compliance rate or frequency estimate for the target SME segment. |
| EVD-004 | ACCC guidance distinguishes remedies for major and minor product problems, assigns responsibility to the seller, and describes when refund, replacement, repair, compensation, and return-cost paths may apply. [Repair, replace, refund, cancel](https://www.accc.gov.au/business/problem-with-a-product-or-service-you-sold/repair-replace-refund-cancel) | A2 / `EXTERNAL_CONSTRAINT` / `DIRECT` | FR-004 and FR-007 must separate request classification, possible guarantee basis, customer-requested outcome, conditional remedy paths, and unresolved assessment. BR-001 remains mandatory. | Guidance supports evidence-grounded conditional proposals; it does not make an automated classifier a legal decision-maker. |
| EVD-005 | ACCC guidance permits multiple reasonable forms of proof of purchase, including records other than an original receipt. Faulty-product returns under a consumer-guarantee path do not require original packaging, and transport responsibility can depend on the product and confirmed problem. [Proof of purchase](https://www.accc.gov.au/business/selling-products-and-services/receipts-bills-proof-of-purchase) and [faulty-product returns](https://www.accc.gov.au/business/problem-with-a-product-or-service-you-sold/repair-replace-refund-cancel) | A2 / `EXTERNAL_CONSTRAINT` / `DIRECT` | FR-002 and FR-005 should model alternative proof types. Original packaging must not be required for a faulty-product consumer-guarantee path; change-of-mind packaging conditions remain store-policy inputs subject to conflict review. FR-007 should expose return-responsibility and cost questions where relevant. | The examples are not exhaustive. The amount of sufficient proof and reasonable cost remains case-dependent and should be escalated when unresolved. |
| EVD-006 | ACCC complaint guidance identifies useful intake information such as the problem, requested outcome, purchase and problem dates, prior action, supporting records, and a response timeframe. [Contacting a business](https://www.accc.gov.au/consumers/problem-with-a-product-or-service-you-bought/contacting-a-business-to-fix-a-problem) | A2 / `EXTERNAL_GUIDANCE` / `CONTEXTUAL` | Provides an evidence-informed starting schema for FR-001, FR-002, FR-005, CustomerStatement, and EvidenceAssessment; adopting that schema is a project design choice. | The source guides consumer complaints generally and does not make every field mandatory for every return case. |
| EVD-007 | Shopify models a return lifecycle in which the customer requests a return and the merchant manages eligibility, approval, tracking, restocking, exchange, and refund. In Customer Account API `2025-04` or later, the documented self-service mutation submits a request that can be approved or rejected rather than directly creating an approved return. Shopify's [`returnCreate` 2025-10 reference](https://shopify.dev/docs/api/admin-graphql/2025-10/mutations/returnCreate) explicitly assumes the request has already been approved. [Returns apps](https://shopify.dev/docs/apps/build/orders-fulfillment/returns-apps) and [self-serve returns](https://shopify.dev/docs/apps/build/orders-fulfillment/returns-apps/build-self-serve-returns) | A3 / `EXTERNAL_CONSTRAINT` / `DIRECT` | Supports separation between UC-01 request and UC-03 decision. A future Shopify path must not substitute `returnCreate` for an unapproved customer request. The mandatory Founder gate remains a project governance rule. | Shopify also documents automated approval/refund use cases, so its documentation does not require a human Founder gate or prove every merchant wants one. The course mock may simplify the provider lifecycle if the simplification is explicit. |
| EVD-008 | Shopify separates opening a return from processing received items, disposition, financial outcome, and closure. Its [2025-07 changelog](https://shopify.dev/changelog/returns-processing-api) records the launch of `returnProcess`, while the [current mutation reference](https://shopify.dev/docs/api/admin-graphql/2026-07/mutations/returnProcess) defines processing and optional financial transfer. | A3 / `EXTERNAL_CONSTRAINT` / `DIRECT` | FR-010, UC-04, and the state model must define whether the MVP completes at approved simulated label issue or includes receipt, inspection, and financial processing. | The existing course MVP can stop earlier, but it must not label a generated return label as a completed real refund or copy Shopify states without a project rationale. |
| EVD-009 | Shopify's protected-customer-data rules require minimum-necessary access and, depending on app type and fields, provider review. Its `returnProcess` and `refundCreate` references also declare required access scopes. [Protected customer data](https://shopify.dev/docs/apps/launch/protected-customer-data), [`returnProcess` 2026-07](https://shopify.dev/docs/api/admin-graphql/2026-07/mutations/returnProcess), and [`refundCreate` 2026-04](https://shopify.dev/docs/api/admin-graphql/2026-04/mutations/refundCreate) | A3 / `EXTERNAL_CONSTRAINT` / `DIRECT` | NFR-002, NFR-003, NFR-007, and NFR-009 should require least-privilege scopes, server-side credential handling, and typed permission failures. Combining those provider constraints with ReturnOps NFR-002 yields two independent preconditions: valid ReturnOps approval and valid provider authority. | Shopify requires its own permissions; it does not define the ReturnOps approval rule. Development-store access does not demonstrate production-app approval or production privacy readiness. |
| EVD-010 | Shopify's supported `@idempotent` mutations require the same key for the same logical intent and parameters, reject unsafe concurrent duplication, and retain provider idempotency state for a documented 24-hour window. Shopify requires `refundCreate` to provide the directive from API version `2026-04`. [Implementing idempotency](https://shopify.dev/docs/api/usage/implementing-idempotency) and [`refundCreate` 2026-04](https://shopify.dev/docs/api/admin-graphql/2026-04/mutations/refundCreate) | A3 / `EXTERNAL_CONSTRAINT` / `DIRECT` | FR-010, FR-011, and NFR-004 should retain a stable key, request fingerprint, provider result, and reconciliation evidence. Any provider fingerprint change creates a new command and key; any change to approval-bound intent or scope, including remedy, amount, line items, or permitted command set, requires new human approval. | The documented behaviour applies only to mutations and versions that support `@idempotent`; it cannot be attributed to every Shopify return operation, Australia Post, notification service, or other provider. HTTP success also does not replace business-result validation. |
| EVD-011 | In Australia Post's domestic-shipment schema, an API `item` element represents each parcel; the return-product rules permit one such API item per return shipment. This is one parcel/article per shipment, not one merchandise SKU. [Create Domestic Shipments](https://developers.auspost.com.au/apis/shipping-and-tracking/reference/create-domestic-shipments) and [Returns and transfers](https://developers.auspost.com.au/apis/shipping-and-tracking/info/product-business-rules/returns-transfers) | A3 / `EXTERNAL_CONSTRAINT` / `DIRECT` | OF-004 and a logistics adapter must model one return parcel/article per shipment. Merchandise line items remain separate case contents and must not automatically create one label per SKU. | The sources do not prohibit multiple merchandise line items inside one return parcel. Test-bed results do not prove production delivery, pricing, or real exception distributions. |
| EVD-012 | Australia Post offers several operational paths, including merchant-created emailed labels, portals, tracking, and notifications; access and service tiers vary. [eParcel Contract returns](https://auspost.com.au/business/shipping/eparcel-contract/returns) and [Shipping and Tracking API](https://developers.auspost.com.au/apis/shipping-and-tracking/) | A3 / `EXTERNAL_CONSTRAINT` / `DIRECT` | OF-004 remains optional. The provider variability motivates a project decision on a mock/manual-label fallback. The adapter and status model should distinguish label creation, customer-notification request and delivery result, and physical parcel tracking and delivery status. | Availability to an Australian SME depends on its account and contract. MyPost Business user-interface capability is not equivalent to open API access. |
| EVD-013 | OAIC states that most small businesses with annual turnover of AUD 3 million or less are not covered by the Privacy Act, although exceptions apply and a business can opt in. [OAIC small-business guidance](https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/small-business) | A2 / `EXTERNAL_CONSTRAINT` / `DIRECT` | NFR-003 should not claim that every target SME is legally subject to every APP. Privacy controls should be an adopted baseline and a legal obligation where applicability is established. | Applicability is entity- and activity-specific; the project is not performing that legal assessment for a real merchant. |
| EVD-014 | APP 3 and APP 11, as described by OAIC, require covered entities to apply purpose-related data minimisation, reasonable security, and reasonable destruction or de-identification when personal information is no longer needed, subject to applicable retention exceptions. [APP 3](https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-3-app-3-collection-of-solicited-personal-information) and [APP 11](https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-11-app-11-security-of-personal-information) | A2 / `EXTERNAL_CONSTRAINT` / `DIRECT` | FR-011 should preserve tamper-evident audit integrity while applying retention, redaction, deletion, or de-identification rules to identifiable audit fields. Immutable non-personal hashes or event identifiers may be retained where justified as a separate project integrity control. NFR-003 and NFR-008 need evidence-purpose rules. | OAIC does not itself require audit immutability, and audit metadata can contain personal information. The current repository and demonstration use synthetic/de-identified data; production applicability and any lawful retention duty remain conditional. |
| EVD-015 | OAIC guidance for commercially available AI highlights collection notice, purpose, disclosure, overseas handling, data quality, and security considerations. [OAIC commercial AI guidance](https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/guidance-on-privacy-and-the-use-of-commercially-available-ai-products) | A2 / `EXTERNAL_GUIDANCE` / `DIRECT` | Supports a project safeguard in NFR-003, NFR-007, and NFR-009: document the AI-provider data flow and do not send real customer data to an unapproved public AI service. | This is regulator guidance and a basis for a project safeguard, not an unconditional statutory prohibition or certification of any selected provider or project implementation. |

## 4. Proposed requirement changes

These proposals do not yet change the stable requirement baseline. `P0` means a
baseline correction is required before implementation; `P1` means a scope or
verification decision is required before the affected feature; `P2` means a
future live-adapter refinement. `Model-breaking` means acceptance would change
a schema, state, interface, benchmark label, or externally visible behaviour;
it does not imply that the current prototype already implements that contract.

| Proposal | Priority | Change impact | Proposed disposition | Affected baseline and models | Evidence |
|---|---:|---|---|---|---|
| CP-001 | P0 | Process only | As a course-project scope decision, replace the previously planned three-interview task with structured desk research, an evidence register, a desk-research-derived reference workflow, and controlled scenario walkthroughs. Do not claim that these outputs are equivalent to primary user validation or an observed target-user AS-IS workflow. | Epic E1, first sprint, sprint evidence, project charter | Project scope decision; EVD-001 to EVD-003, EVD-006 to EVD-008, and EVD-012 inform the desk-research outputs |
| CP-002 | P0 | Model-breaking | Refine classification into separate fields: customer request type, possible consumer-guarantee basis, and unresolved assessment status. Preserve the prohibition on final automated entitlement or major/minor determinations. | FR-004, FR-007, BR-001, UC-02, feature and class models | EVD-003, EVD-004 |
| CP-003 | P0 | Model-breaking | Accept multiple proof-of-purchase types. Do not require original packaging for a faulty-product consumer-guarantee path; retain change-of-mind packaging conditions as store-policy inputs subject to conflict review. Collect product-size and transport facts only when relevant. | FR-001, FR-002, FR-005, UC-01/UC-01E, EvidenceItem/EvidenceType, EvidenceAssessment, class model | EVD-005, EVD-006 |
| CP-004 | P0 | Model-breaking | Preserve the customer-requested remedy in `CustomerStatement`, reference it from the proposal without creating a second source of truth, and keep it distinct from any recommended remedy. Add conditional remedy paths, unresolved questions, and relevant return-responsibility/cost facts to the non-executable proposal. | FR-007, UC-02, CustomerStatement, DecisionProposal, class model | EVD-004, EVD-005 |
| CP-005 | P0 | Model-breaking | Choose and state the exact MVP completion boundary. Recommended course scope: close the automated core only after an approved **simulated return and label outcome** is stored and notified; keep physical receipt, inspection, restocking, and real refund outside core scope or in OF-005. Do not call label creation a completed refund. | Project promise, FR-010, UC-04, state and sequence models, OF-005 | EVD-007, EVD-008 |
| CP-006 | P1 | Provider-contract breaking | Add provider-operation fingerprint, provider ID, business error, and an `UNKNOWN/RECONCILING` result for ambiguous timeouts. Validate required provider credentials and scopes separately from ReturnOps approval, deny missing provider authority before an effect, and contract-test that path. Retry only after provider-specific reconciliation rules. | FR-010, FR-011, NFR-002, NFR-004, NFR-006 to NFR-009, sequence and class models, provider contracts | EVD-009 to EVD-012 |
| CP-007 | P1 | Optional-adapter model | Model Australia Post cardinality as one parcel/article per return shipment, not one merchandise SKU per shipment. Decide how multiple returned line items map into a permitted parcel and test packaging/label guards without generating one label per product by default. | OF-004, FR-010, logistics adapter contract, use-case exception | EVD-011 |
| CP-008 | P0 | Storage-model breaking | Preserve tamper-evident audit integrity while treating identifiable audit fields and raw content under purpose, minimisation, redaction, retention, deletion, and de-identification rules. Retain immutable non-personal hashes or event identifiers only where justified. Add AI-provider data-flow controls, and state that legal APP applicability is conditional while privacy-by-design is mandatory for the project. | FR-011, NFR-003, NFR-007 to NFR-009, UC-01, AuditEvent | EVD-009, EVD-013 to EVD-015; tamper evidence is a project integrity control |
| CP-009 | P0 | Wording and measurement | Remove any presentation of approximately ten minutes of manual handling as an established fact. Replace it with the scoped HYP-001 controlled manual-baseline statement and measure that baseline. Keep sub-120-second proposal generation as a `PROTOTYPE_TARGET`, not an external benchmark. | Lab 3 AH-13, problem statement, NFR-005, Epic E6, evaluation plan | EVD-001 |
| CP-010 | P1 | Scope expansion | Add a candidate customer-transparency capability covering case status, expected next step, packaging/drop-off instructions, applicable cost information, and notification outcome. Assign a new FR ID only after scope approval. | Candidate FR, customer use case, feature diagram, portal scope | EVD-002, EVD-012 |
| CP-011 | P1 | Scope clarification | Define the demonstration persona as an Australian Shopify merchant using synthetic orders and a mock logistics contract. Treat merchant volume, platform tier, and production API eligibility as assumptions, not market facts. | Charter target user, assumptions, OF-003, OF-004 | EVD-007, EVD-009, EVD-012 |
| CP-012 | P0 | Model refinement | As an existing FR-006/NFR-001 engineering control informed by source volatility, maintain a reviewed, versioned corpus with source identity, version/access date, location, and content hash. A source conflict remains visible and routes to risk review. | FR-006, FR-008, NFR-001, BR-002, PolicyDocument/PolicyPassage | Existing FR-006/NFR-001 and project reproducibility design; EVD-003 to EVD-005 are contextual support only |

## 5. Hypothesis and target register

| ID | Statement | Type | Validation without fieldwork | Reporting rule |
|---|---|---|---|---|
| HYP-001 | Under the controlled project protocol, human preparation of a complete decision packet has a measurable active-handling-time and omission baseline. | `PROJECT_ASSUMPTION` | Have two team operators independently process 20 stratified synthetic cases using the same order and policy evidence as the prototype. | Report each operator's and pooled median, interquartile range, omissions, and scenario mix; do not generalise beyond the controlled project setting. |
| HYP-002 | ReturnOps AU can store a reviewed proposal within 120 seconds for a complete case. | `PROTOTYPE_TARGET` | Measure accepted-complete-input to stored-current-proposal time on the fixed 100-case environment, excluding human waiting. | Report environment, model/provider version, run date, failures, median, and tail percentiles. |
| HYP-003 | The selected accuracy, citation, agreement, and escalation thresholds are achievable. | `PROTOTYPE_TARGET` | Freeze labels and scoring rules before comparing the four architecture configurations. | Report denominators and confidence intervals or raw counts; do not relabel failures after observing results. |
| HYP-004 | Target merchants would adopt or pay for this product. | `PROJECT_ASSUMPTION` | No valid online-only project test is currently planned. Competitor existence and industry friction are not willingness-to-pay evidence. | Exclude adoption and revenue claims from assessed outcomes. Present only as future validation. |
| HYP-005 | The target merchant has the Shopify and Australia Post account capability needed by a live adapter. | `PROJECT_ASSUMPTION` | Demonstrate mock contracts first; separately document development-store and test-bed eligibility if optional adapters are attempted. | Do not present mock/test-bed success as production readiness. |
| HYP-006 | The system reduces total end-to-end resolution time. | `PROJECT_ASSUMPTION` | Not tested by proposal latency. A future test would need receipt, inspection, logistics, and financial completion timestamps. | Do not infer end-to-end improvement from HYP-002. |

## 6. Controlled validation protocol

For this course project, the team uses this protocol instead of the previously
planned field interviews. It is not equivalent to primary user validation and
does not replace future market discovery for a commercial product.

### 6.1 Pilot manual baseline

1. Freeze 20 synthetic cases before timing: five faulty-product, four
   wrong-item, four change-of-mind, four missing/ambiguous-evidence, and three
   policy-conflict or high-risk cases.
2. Have two team operators independently process the same frozen cases in
   separately randomised orders. Give each the same order snapshot, approved
   corpus, and evidence that the prototype receives.
3. Define active handling as time spent reading, checking, recording, and
   preparing a decision packet. Pause the timer for simulated customer,
   provider, transport, or founder waiting.
4. Have Member C record timing and score omissions against the frozen case
   labels. The timed operators should not author those ground-truth labels.
5. Report the scenario mix, per-operator and pooled medians, interquartile
   ranges, raw errors, possible order or learning effects, and all exclusions.
   Twenty cases and two student operators form a project baseline, not a
   population estimate.

### 6.2 Prototype evaluation

1. Freeze the 100-case dataset, label schema, corpus version, prompts, model
   versions, and scoring code before the final comparative run.
2. Measure proposal latency separately from human approval waiting, simulated
   tool execution, notification, and physical return completion.
3. Use the same cases and evidence boundaries for each architecture baseline.
4. Record every invalid output, unsupported claim, escalation, provider fault,
   approval block, and duplicate-effect test rather than reporting successful
   cases only.
5. Promote a target to `MEASURED_RESULT` only when the run artefact can be
   reproduced from a commit, configuration, dataset version, and result file.

## 7. Decision package for Baseline v1.0

Before any proposal in Section 4 changes the canonical requirements:

- [ ] Member A records accept, revise, defer, or reject for CP-001 to CP-012.
- [ ] Member B reviews customer/Founder journeys and CP-005, CP-007, CP-010.
- [ ] Member C reviews evidence grades, metric definitions, and HYP-001 to
  HYP-006.
- [ ] The team resolves the MVP completion boundary and multi-item logistics
  decision explicitly.
- [ ] Accepted changes update requirement text, rationale, affected models,
  acceptance tests, and change history in one Baseline v1.0 pull request.
- [ ] Rejected or deferred changes remain visible with a reason; evidence is
  not silently deleted.

Until that review occurs, [v0.2](04-requirements-and-backlog.md) remains the
canonical requirement baseline and this document is advisory evidence only.
