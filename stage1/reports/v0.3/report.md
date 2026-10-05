# ReturnOps AU Stage 1 Report Team Review Draft

> Repository-readable rendition of the user-provided current native DOCX export. The native Google Doc remains authoritative. See the snapshot README and source metadata for provenance and limits.

<!-- REPORT CONTENT START -->

ReturnOps AU

Stage One Requirements and Design Report

ELEC5620 Model Based Software Engineering<br>University of Sydney<br>Version 0.3 — 21 September clarification for final team review<br>Sep 21, 2026

A human governed multi agent returns operations system for one Australian online store.

Team: A - Jingbo Chai; B - Chengsi Li; C - Yuwei Tao.

Prepared with AI assistance for final team review. Personal contribution confirmation and course submission checks remain pending.

Original technical baseline: rc.5 at 64582a3; A's test correction at 3dd1ff6 and C's model/report follow-up at 32c704f are cited in \[P10\]. This integrated report is separate from those CI runs; current B report views derive from the MB-0.2 compatibility correction \[P14\], and current C figure sources are identified in \[P12\]. Personal design work, shared contributions and task-specific AI instructions remain subject to confirmation before submission.

Contents

[1 Purpose and preparation status 3](<#_lxcjrc9d1dh6>)

[2 Project problem and scope 3](<#_llyyulk981wb>)

[3 Requirements and feature model 4](<#_f4ec5k5ovku7>)

[4 Use cases 7](<#_wp9arpl82b0n>)

[5 System architecture and shared models 10](<#_ftkhtmywzcd1>)

[6 Member A governed execution model 12](<#_29fzj16eydnn>)

[7 Member B: customer interaction and intake models 13](<#_xna2zwiyaqnv>)

[8 Grounding and independent risk review 16](<#_zfiavx5vnmqu>)

[9 Design choices and change assessment 18](<#_t8t47hcoejvw>)

[10 Verification and evaluation plan 19](<#_gn0abb84naan>)

[11 Delivery status and contribution plan 22](<#_3iigzxz4b4fw>)

[12 Submission checks and unresolved decisions 23](<#_ula0uicn2uvh>)

[13 References 24](<#_ccpv0bmju8cr>)

[**14 Model figures 26**](<#_bntzqq9itovk>)

[Appendix A Review and provenance notes 51](<#_2yt60knmpb6r>)

Figures are grouped in the Model figures appendix at a readable page size. In-text figure links jump to the corresponding model. Figures are embedded images. Editable PlantUML sources are retained in the project report materials for replacing revised figures.

**Assessment reading guide**

Requirements and use cases: Sections 2-4; Figures 1-3; six detailed use-case specifications.

Shared structure: Section 5; classes in Figures 5-8, runtime structures in Figures 9-11, and the object snapshot in Figure 24.

Individual chains: Section 6/A (AH-10, UC-04, Figures 13-16); Section 7/B (AH-01, UC-01, Figures 17-20); Section 8/C (AH-08, UC-02, Figures 21-23).

Design rationale, change assessment and verification: Sections 9-10; package and deployment views in Figures 4 and 12.

Contributions, AI acknowledgement and submission checks: Sections 1, 11-12 and Appendix A.

# <a id="_lxcjrc9d1dh6"></a>1 Purpose and preparation status

ReturnOps AU is a proposed human-governed returns operations system for one Australian online store. This report explains its requirements, six use cases, architecture, behavioural models, design decisions and planned verification. This submission-preparation revision presents one coherent design for final team review.

A led this report's integration with AI assistance; Section 11 distinguishes recorded source attribution from personal contributions that still require confirmation. B's published personal chain is represented through the A-led, AI-assisted MB-0.2 compatibility correction \[P14\]; the C chapter now incorporates C-published, AI-assisted report views \[P12\]. Each member remains responsible for individual design, shared modelling and personal explanation. The official ELEC5620 2026 unit outline permits AI use in Project Stage 1 and requires acknowledgement \[C4\]. Canvas task-page observations through 21 September 2026 are incorporated in Appendix A \[C5, C6\]. Final submission checks and the assigned interview slot remain to be verified; individual and shared-contribution requirements remain applicable \[C1\]. Submission checks are consolidated in Section 12.

The report preserves the approved nine-feature allocation \[P2\]. Its diagrams explain the proposed design without defining new public APIs. Team review can proceed while business implementation and joint contract acceptance remain unfinished; the later technical environment reproduction is recorded in \[P17\]. Appendix A records the technical reference and preparation evidence.

# <a id="_llyyulk981wb"></a>2 Project problem and scope

## Business problem and proposed outcome

A single store operator must combine a customer's description, purchase information, evidence, store policy and consumer guidance before deciding how to handle a return request. Missing information, contradictory sources and uncertain operational results make a fluent answer alone insufficient. The proposed system prepares a traceable decision packet, then presents it to the Human Founder for a specific decision. Only a valid human approval can authorise the simulated operational steps.

The course prototype serves one synthetic merchant rather than multiple tenants. It supports faulty or damaged goods, wrong items, and change-of-mind requests. A case concerns one order and may contain several order items. One approved return parcel produces one label. The automated success boundary is a saved simulated return and label outcome followed by successful outcome notification. Physical receipt, inspection, stock adjustment, payment and real refund settlement remain outside the core.

The three AI business roles are Customer Case Coordinator, Returns Assessment Agent and Compliance and Risk Reviewer. The Coordinator extracts facts and asks relevant questions. Assessment combines evidence with retrieved sources to draft a conditional recommendation. Risk independently checks that recommendation. These roles cannot grant approval or directly perform a high-impact operation. Domain Service owns authoritative business state, and a deterministic Operations Service performs only approved simulated commands.

The project asks whether the complete governed architecture improves citation correctness and risky-case detection relative to a single-LLM baseline while meeting a target proposal p95 latency below 120 seconds. These are research questions and prototype targets. No measured improvement, pre-existing ten-minute handling baseline, legal correctness or production readiness is claimed.

## Illustrative synthetic walkthrough

Illustrative synthetic walkthrough—not a Gold case or measured result. A customer reports that a desk lamp arrived with a cracked base and requests a return. Through UC-01, the portal submits the original message and permitted synthetic evidence; Domain preserves them. The Coordinator requests the missing order reference through UC-01E. Once accepted, read-only order facts and versioned retrieved passages enter the evidence bundle. Assessment drafts a conditional return proposal; citation checks confirm source identity and Risk independently checks support, conflicts and scope. For this illustrative PASS outcome, the Founder inspects the sources and server-generated ActionPreview, then approves the current proposal and exact return-and-label scope in UC-03. Domain records approval and work; Operations rechecks authority before each mock command in UC-04. The mock return is saved before its parcel's label, and Domain records both results. If outcome notification fails, only notification is retried: the saved return and label are not created again. This illustrates the proposed design, not a legal entitlement or observed performance.

## Evidence and assumptions

The requirements were informed by secondary desk research, recorded in the frozen evidence register \[P3\]. No merchant interviews, field observations or primary usability study have been completed. The source summary below explains design consequences rather than reproducing the full research appendix. Public pages \[R1–R4\] were read again on Sep 7, 2026; this check does not revise the frozen research methodology or establish field validation.

ACCC guidance describes different remedy paths and circumstances in which businesses are responsible for resolving product problems. It also describes return-cost responsibilities and explains that original packaging is not required for a faulty-product return \[R1\]. The design therefore separates the issue category, requested outcome, possible basis and unresolved assessment. A retrieved passage informs a conditional proposal; an AI classification is not a final determination of legal entitlement. Store policy and reviewed guidance retain separate source types, and their material conflicts are shown for review.

ACCC proof-of-purchase guidance describes alternatives to an original paper receipt, including relevant payment and transaction records \[R2\]. Intake therefore preserves an optional order number, supports relevant alternative evidence and asks targeted follow-up questions. The project does not make every possible complaint field mandatory for every case. When evidence is missing or conflicting, it records that condition instead of inventing facts or rejecting the request automatically.

Shopify's versioned returnCreate reference assumes that the return request has already been approved \[R3\]. This supports separating request intake from operational return creation, while the compulsory Human Founder gate remains the project's own governance choice. The course implementation uses mock commerce providers; the reference does not imply a live Shopify integration or permission to access production orders.

OAIC explains that many small businesses are exempt from the Privacy Act while specified exceptions apply \[R4\]. ReturnOps AU therefore states data minimisation, controlled access, redaction and retention as project safeguards without asserting that every target merchant has identical statutory obligations. Demonstration data is synthetic or de-identified. Non-personal integrity records can be preserved separately from removable content, subject to an explicit retention design; a hash alone does not establish that retained metadata is non-personal.

The assumed operating context is one Human Founder, a small reviewed corpus, synthetic orders, test-only adapters and intermittent provider or model failures. The team currently has no Australia Post or StarTrack contract or test account. The selected logistics extension remains an unresolved external dependency; the core mock cannot be counted again as its implementation \[P4\]. User validation, provider access, actual workload and performance all require later evidence.

# <a id="_f4ec5k5ovku7"></a>3 Requirements and feature model

## Stakeholders and agreement

The Customer supplies a request and evidence and receives clarification and an outcome. The Founder reviews sources, uncertainty and proposed actions and decides whether to approve, reject, revise or handle a case manually. The student maintainers develop the prototype and its evidence. Tutors assess the design and individual contributions. External model, order and operational providers supply bounded inputs or capabilities. The reviewed course corpus, retrieval and citation verification are internal components; none replaces the Founder's authority.

The lead-approved agreement fixes one store, three AI roles, six detailed use cases, nine assigned features and a simulated operational endpoint. This is the current planning agreement, with team and tutor adoption feedback still to be resolved. Each member owns two core features and one selected optional. A/B/C's 45/27/28 effort split is a planning estimate, not measured contribution or a marking allocation.

[Figure 1. Stakeholder requirements and their design consequences](<#c7ki4yqx189b>)

The user requirement view relates stakeholder needs to capabilities and qualities. The informal individual requirements are A AH-10, execute only the exact approved action without duplicate effects; B AH-01, lodge the original request through a usable customer interface; and C AH-08, expose material source conflicts and escalate an unsafe proposal. The corresponding personal model chapters develop UC-04, UC-01 and UC-02 respectively.

## Mandatory capabilities

| **ID** | **Required capability** | **Planned acceptance evidence** |
| --- | --- | --- |
| FR-001 | Accept and preserve the original customer request and requested outcome | Intake and API tests preserve the submitted statement |
| FR-002 | Extract facts and ask targeted questions about missing information | Pilot cases distinguish missing, conflicting and irrelevant facts |
| FR-003 | Perform a read-only order lookup | MATCHED, NOT\_FOUND, CONFLICT, AUTHORITY\_DENIED and PROVIDER\_FAILURE tests |
| FR-004 | Separate issue type, customer preference, possible basis and assessment status | Distinct typed fields; no automatic entitlement determination |
| FR-005 | Maintain a criterion-level evidence matrix | PRESENT, MISSING, CONFLICTING and NOT\_APPLICABLE examples |
| FR-006 | Retrieve versioned reviewed policy and guidance | Reproducible retrieval with source location, version and content hash |
| FR-007 | Generate a versioned non-executable decision packet | Structural validity, original-statement references and resolvable citations |
| FR-008 | Independently review evidence, risk and scope | Five business outcomes and separate technical-failure tests |
| FR-009 | Record a current, authorised Founder decision | Exact target, version, scope, actor and expiry checks |
| FR-010 | Execute only approved simulated return and label work, then notify | Provider-effect, retry, reconciliation and notification tests |
| FR-011 | Preserve traceable business history with retention controls | Correlated audit and authorised role-specific history tests |
| FR-012 | Provide Founder case and decision visibility | Current-state, evidence, operation and notification read-model tests |

The operational rules are cumulative: a schema-valid proposal does not authorise an action; a passing risk review does not approve it; a stored approval is insufficient if its scope, version, identity, expiry or provider permission is no longer valid at dispatch. Any non-proposal manual decision must identify the current technical failure or order-lookup block and cannot create an approval or operation.

## Quality requirements and selected options

| **ID** | **Quality concern** | **Verification approach** |
| --- | --- | --- |
| NFR-001 | Traceability | Resolvable citations and requirement to model to test links |
| NFR-002 | Safety and human control | No unauthorised effect under identity, version, scope and expiry negatives |
| NFR-003 | Privacy | Synthetic data, access isolation, model field allowlists and retention tests |
| NFR-004 | Reliability | Durable attempts, at-most-once effects, ambiguous-outcome recovery |
| NFR-005 | Performance | p50/p95 proposal latency with explicit boundaries and failure reporting |
| NFR-006 | Testability | Deterministic mocks, observable effects, reproducible failure injection |
| NFR-007 | Maintainability | Typed ports and separate ownership of UI, domain, agents and providers |
| NFR-008 | Observability | Correlation identifiers, versions, provenance and authorised audit queries |
| NFR-009 | Prompt and input robustness | Untrusted-input tests and no direct Agent-to-Operations authority |

[Figure 2. Mandatory capabilities and product family options](<#9na5boaialtk>)

The feature view distinguishes product-family variability from this team's fixed selection. A owns A1 lifecycle and proposal preparation, A2 approval and simulated execution, and selected OF-004 logistics sandbox integration. B owns B1 intake, B2 Founder review and selected OF-006 analytics. C owns C1 retrieval and citation verification, C2 risk review and selected OF-001 image observations. The selected options remain course commitments. Their implementation is not a prerequisite for producing this design report.

## <a id="_dgmdcgagu6hb"></a>Selected extensions: design and planned acceptance

These selected features remain course commitments under the fixed allocation. The following design summary does not claim implementation or provider access.

| **Feature** | **Trigger and inputs** | **Output and integration** | **Failure and planned acceptance** |
| --- | --- | --- | --- |
| A3 / OF-004<br>Logistics test adapter | UC-04, after exact approval and verified test authority; saved return, parcel and approved parameters. | An independent adapter maps authorised test-provider results to the existing Operations interfaces; Domain records bound observations. | Blocked: no Australia Post/StarTrack contract or test account. Later verify no production charge, deduplication and original-effect/artifact recovery. Core mock work cannot count twice; no replacement is approved. |
| B3 / OF-006<br>Operations analytics | An authorised Founder opens UC-05 analytics; A supplies validated filters and one as\_of snapshot. | B displays each selected case once: current status, latest valid current-input/proposal review, and measured proposal latency. Missing current reviews remain separate. | Reconcile sample\_count + failed\_count + unmeasured\_count = case\_count. Test empty/error views and fixed fixtures. When sample\_count=0, omit p50/p95 and show unavailable, not zero. |
| C3 / OF-001<br>Image observations | After the text workflow is stable, orchestration requests authorised images bound to case\_id, input\_version and evidence\_ids. | C returns evidence\_id-linked visible\_observations, limitations and confidence. Domain validates bindings; Assessment and Risk receive observations with original-image references, never approval or legal authority. | Compare the same synthetic case with/without authorised images: clear images yield attributable visible observations; blurred/unrelated images add no invented detail. Test image-text injection without changed authority. Record unreadability in limitations; visible\_observations may be empty. Retain C-owned extraction-module, test and demo evidence distinct from B's upload component. No new outcome enum; confidence thresholds and continuation rules still require A/C review. |

Additional languages, live Shopify integration, inventory restocking and anomaly scoring remain unselected product-family options. Hybrid retrieval, Redis/Celery/Outbox, extensive observability tooling, B2/B3 experimental ablations and expansion towards 100 cases are deferred portfolio work. The core is intentionally bounded to a small reviewed corpus, keyword/BM25 retrieval and 30 double-reviewed Gold cases for the later formal comparison of the single-LLM baseline (B1) with the full governed configuration (B4). Experimental B1-B4 labels identify configurations; member B's B1/B2/B3 labels identify features.

# <a id="_wp9arpl82b0n"></a>4 Use cases

## System boundary and catalogue

[Figure 3. Overall use case model with human and external actors](<#pepro98kty7x>)

The six specifications below provide the report's complete use-case catalogue. B is the document owner for UC-01 and UC-01E, C for UC-02 and UC-05, and A for UC-03 and UC-04. These assignments are modelling responsibilities rather than exclusive ownership of all code touched by a use case. For example, UC-05 uses B's interface and A's authorised queries while C checks evidence consistency. The source specifications remain in docs/05 \[P5\].

## UC01 Lodge a return or remedy request

Actor: Customer. Goal: preserve one original request and receive an authoritative acknowledgement. Preconditions: the request uses a valid customer context and permitted synthetic input; an order identifier may be missing. Trigger: the customer submits the form. Success: Domain stores the statement, requested outcome and initial case and returns the accepted case reference.

The Customer enters the problem and desired outcome, optionally supplying an order reference and permitted evidence. The portal checks input presentation and uploads attachments through the authorised backend. The API validates identity, request shape and the scoped idempotency key. Domain accepts the original statement without replacing it with an AI summary, links authorised evidence and records the case and audit transaction. The portal displays only the server's acknowledgement; an accepted request is not a completed return.

If the network result is unclear, the client preserves the original request identity instead of starting a duplicate. The same key with changed content is rejected. If the original receipt content has been removed under retention rules, replay returns the specified conflict response without recreating content or effects; the client uses authorised current-state recovery. Invalid uploads and unauthorised access are rejected. Further clarification is modelled separately in UC-01E. Trace: AH-01; FR-001/002/005/011; B1 and A1, server-side demo identity and authorisation (F.03), and attachment upload, references and authorised reads (F.04).

## UC01E Provide clarification or evidence

Actor: Customer. Goal: answer current questions within the same case. Preconditions: the authenticated customer owns the case and the current server state is AWAITING\_INFORMATION with the matching current question set. Trigger: the customer responds to those questions. Success: a new accepted input revision preserves prior statements and becomes available for reassessment.

The portal loads current questions and permitted evidence requirements. The customer supplies answers and authorised attachment references. The API checks ownership, case/input version, legal material-admission state and request identity. Domain stores the additional statement and the new input revision with audit history. The Coordinator then resumes the case workflow. The interface refreshes from server facts.

An outdated question or version is rejected and refreshed. Unsupported attachments, a different customer's reference, a post-review append outside a legal admission state or a reused key with different content cannot silently mutate the case. Missing information stays explicitly missing. Reasonable alternative proof can be considered without universal original-packaging or paper-receipt requirements. Trace: FR-002/005/011; B1, A1 and F.04.

## UC02 Assess the case and prepare a proposal

Beneficiary and operator: Founder; trigger: an accepted case/input revision. Preconditions: authorised, bounded inputs and configured read-only providers are available. Main success: Domain stores a current non-executable packet and a matching PASS or PASS\_WITH\_WARNING review, entering AWAITING\_APPROVAL for Founder review. Alternative exits request clarification or escalate for manual handling without an operation.

The Coordinator extracts typed facts and identifies missing or conflicting information. A read-only order lookup returns a typed result. Assessment obtains C1's versioned retrieved passages. Deterministic wrappers forward the original retrieval result and full conflicts through the orchestrator for Domain to accept the source receipt. Assessment then supplies a conditional candidate packet and evidence matrix. The orchestrator invokes C1 to verify the candidate's citations, preserves the original verification result, and submits the packet with the complete evidence bundle to Domain. Domain validates and atomically commits the packet and bundle before the orchestrator supplies that accepted bundle and exact proposal revision to an independent Risk invocation. Risk checks support and authority risks and returns a structured outcome; the orchestrator submits the unchanged review to Domain for acceptance and routing.

PASS and PASS\_WITH\_WARNING permit Founder review, not execution. REVISE requests a new packet and review; NEEDS\_INFORMATION opens an authorised clarification route; ESCALATE blocks approval of that proposal. Model errors, malformed responses or stale bindings never become PASS. NOT\_FOUND asks for more information; pre-proposal order CONFLICT/AUTHORITY\_DENIED and technical failure remain distinct targets for manual handling. Source conflicts stay with evidence and Risk. Trace: AH-08; FR-002–008/011; A1 and C1/C2.

## UC03 Review a proposal or record a manual outcome

Actor: authorised Founder. Goal: make an informed decision on the current eligible target. Preconditions: the Founder can access the case; the current target is exactly one proposal revision, technical ProcessingFailure or pre-proposal OrderLookupBlock. Success: the specific decision and required subsequent work are durably recorded.

The dashboard shows original requests, evidence, source citations, uncertainty, current review and version. For a proposal, the server first generates an ActionPreview bound to the current target, case version, command parameters, limits and expiry. The dashboard shows this exact scope before the Founder confirms it. APPROVE returns the server-owned preview\_id and scope\_fingerprint; an expired preview or changed version requires a fresh preview and confirmation. The Founder chooses APPROVE, REJECT, REQUEST\_REVISION or MANUAL\_HANDLING. Approval includes the exact permitted command scope, parameters, monetary ceiling where applicable and validity period. Domain verifies trusted identity, current target/version and review eligibility and stores the decision, approval where appropriate, audit and pending work atomically. Rejection or manual handling generates the appropriate notification work; revision invalidates assumptions about earlier approval and requires a new reviewed proposal.

Only PASS/PASS\_WITH\_WARNING proposals are eligible for execution approval. ESCALATE, stale or missing reviews cannot be overridden by a client flag. Without a proposal, only MANUAL\_HANDLING is legal; the decision targets the current failure or lookup block and creates no ApprovalRecord or return/label work. Duplicate requests preserve the original accepted meaning subject to the retention-aware receipt rule. Trace: FR-009/011/012; A2 and B2.

## UC04 Execute the approved simulated action

Trigger: committed work associated with valid Founder approval. Supporting actors: mock returns, logistics and notification providers. Preconditions: current authority, scope, provider permission and durable intent pass the final dispatch guards. Success: the return and label results are saved, outcome notification is SENT and Domain records the permitted completed outcome.

Operations claims unfinished work through Domain, revalidates the exact approval and records the original command/attempt identity before invocation. The return adapter executes first. Label creation depends on the saved return result for the same parcel. Operations returns typed observations to Domain, which persists results and audit. Once the appropriate operational result is complete, notification is sent and its separate outcome recorded.

Unknown effects enter reconciliation using the original identity; a timeout alone does not justify a new effect. A known label success with an unavailable local file remains EXECUTING with artifact-only recovery, not an UNKNOWN effect. Retrying notification never repeats a successful return or label. Current manual/reject outcomes survive late historical confirmations. Missing authority or unresolved overlapping effects block new dispatch. Recovery of old facts uses its own current authorisation and cannot grant permission for new actions. Trace: AH-10; FR-009–012; A2 and A3 extension.

## UC05 Inspect case state and audit history

Actor: authorised Founder. Goal: understand the current case and reconstruct relevant decisions. Preconditions: access is verified before current or historical content is returned. Success: the Founder sees consistent, versioned case, proposal, review, decision, operation and notification information.

The Founder opens the list or case detail. The query service authorises access and reads Domain's persisted facts. The interface presents current status separately from historical revisions, shows citations and uncertainty, and distinguishes operation status from notification status. An authorised history request resolves exact object revisions and provenance rather than synthesising current data as an old receipt. The analytics view uses case-based denominators and the defined current-review selection rule.

Missing or removed content is explicitly marked; retention never recreates deleted text. Customer history uses a separate role-limited projection and must not reveal Founder-only material. UNKNOWN is not presented as an ordinary failure inviting unrestricted retries. Empty statistics, unavailable measurements and failures are displayed with sample counts. Trace: FR-011/012; audit and read-only queries (F.05), metrics and statistics API (F.06), and privacy, model-input and retention controls (F.07); B2/B3 and C's evidence review.

# <a id="_ftkhtmywzcd1"></a>5 System architecture and shared models

## Components and control flow

The proposed deployment is a modular application with PostgreSQL as the sole authoritative business store. A thin API authenticates and validates requests; Domain owns legal transitions, accepted versions and trusted audit. An orchestrator coordinates typed calls to the three AI roles and retrieval without creating another state store. Provider adapters translate bounded input and observations. The web application presents server facts and submits user intent. The evaluation runner operates on declared datasets and frozen configurations.

This separation makes model-generated suggestions distinguishable from trusted decisions. Coordinator and Assessment are A's implementations; retrieval, independent Risk and image observations belong to C; B implements the two interfaces and analytics. Shared authentication, attachments, history, metrics, deployment and integration remain A's responsibility. Operations is a deterministic service, not a fourth AI business role.

[Figure 4. Shared package responsibilities](<#4ela4qpnujhf>)

The package view summarises the existing PD-0.2 candidate for report readability. It is an architectural explanation, not evidence that all packages are implemented. Browser, server and provider credentials are separated; raw attachment content and provider secrets are not passed through arbitrary model-generated references. C receives only controlled evidence inputs and returns observations which Domain must accept against their original case/input binding.

## Design time class structure

[Figure 5. Core case and evidence classes](<#s615ajmpz53u>)

The report class view abbreviates the detailed shared class model \[P6\] while retaining the relationships that drive behaviour. A Customer may have many cases. A case preserves several statements and input/proposal revisions but only one order identity; repeated snapshots are historical views of that order. CaseLineItem refers to the accepted order's LineItem, and a case has at most one return parcel. The parcel has at most one label result, regardless of how many merchandise items it contains.

IntakeSession is the durable, case-owned intake record, preserving clarification rounds and outstanding questions. Figure 20 models this object \[P14\]. IntakeViewSession is a separate transient UI controller: it may exist before a case reference is known, and several views can refer to one case. Closing a view does not destroy the domain record or its statements, reopen a case or cause a business transition. This internal lifecycle refinement changes no public API.

DecisionPacket aggregates references to evidence and cited PolicyPassages. Policy sources can support several cases and are not owned by a single case. The shared-class ProposalReview result maps to the wire RiskReview and binds one exact packet revision with one of five outcomes. It is distinct from C's internal review-work lifecycle \[P12\]; technical invocation failure is a separate processing observation. FounderDecision has exactly one target among a proposal, a technical failure and an order-lookup block. Only an eligible APPROVE decision creates an ApprovalRecord, which authorises the two scoped command types. Each command retains its individual OperationAttempts.

[Figure 6. Decision and execution record relationships](<#ijxbxjks2oqf>)

[Figure 7. Approval and service interfaces](<#rlvg4gylu6r4>)

[Figure 8. Analysis classes, typed ports and AI role responsibilities](<#k3gl7y2tpnn1>)

The analysis class view supplies the design-time types behind the runtime parts: Coordinator, Assessment, IndependentRisk and BoundedOrchestrator, together with read-only order and retrieval/citation ports. Their methods exchange typed requests and observations. Domain alone validates and accepts the original evidence bundle, proposal and review; the orchestrator retrieves that accepted bundle for the independent reviewer. These report names map to the existing shared-class roles and do not add public endpoints or give the AI roles business-write authority.

ToolCommand is abstract, with CreateReturnCommand and GenerateLabelCommand specialisations. Provider interfaces separate the core mock from a potential authorised test adapter. Domain methods require a trusted principal, current expected versions and validated typed inputs; they return accepted records or explicit errors. recordDecision cannot accept a client-manufactured approval. acceptReview checks proposal/input/source bindings. recordObservation accepts only an observation bound to existing trusted work. readHistory applies role and retention rules before returning content. Their names are report-level method contracts, not additional public API endpoints.

Composition indicates ownership of record lifecycles; aggregation/reference expresses shared material. The conceptual class relationship does not by itself authorise indefinite retention. Request receipt storage, historical content and attachment bytes must obey the same deletion policy while minimal deduplication and non-personal audit evidence retain a documented purpose. Exact database columns and the unresolved attempt counter interpretation remain implementation decisions to review rather than inferred facts from a diagram. The proposal revision is named DecisionPacket.proposal\_version consistently across the report. The domain-result class ProposalReview maps to the rc.5 RiskReview DTO; neither name denotes the internal review-work lifecycle in Figure 23. Figures 5–8 select conceptual attributes, whereas Figure 24 uses selected DTO slots. Omitted fields are not assertions of absence, and this explanatory mapping makes no public-contract change.

## Runtime structure and collaboration

[Figure 9. Runtime parts and ports of the governed case system](<#7tu4fcoddh47>)

[Figure 10. Analysis collaboration with independent Risk](<#b91m03xhe4bo>)

[Figure 11. Execution collaboration with approvals and audit](<#w2e8swrr131b>)

Figures 9–11 specify parts of structured classifiers: role : Type denotes an internal part, not a recorded running-instance snapshot. Figure 9's GovernedCaseSystem encloses api : API, domain : DomainService, analysis : AnalysisSystem and execution : ExecutionSystem. This report boundary includes the application API context around the GovernedCaseAssessment collaboration in docs/13 \[P6\]; it is not an identical alias for that narrower classifier. API denotes the existing authenticated application boundary, not a newly required implementation class. AnalysisSystem and ExecutionSystem are report short names for GovernedAnalysis and GovernedExecution. Figures 10 and 11 expand those same analysis and execution parts, using the role/service types in Figures 7–8. Store and audit denote CaseRepository and AuditPort boundaries. Each shown role is logical, not a limit on cases or workers. These structural names require no additional Python class, microservice or deployment process; Domain retains the authority to accept facts, change business state and record business audit.

The three report views derived from CS-0.2 show runtime parts, ports and connectors rather than merely repeating package dependencies. The overall case collaboration delegates to analysis and execution. Within analysis, deterministic wrappers preserve the raw order/retrieval/citation receipts before Domain accepts them; Risk receives those accepted materials, not the generator's self-reported evidence or hidden reasoning. The independent invocation has its own prompt and structured result.

Within execution, Operations reaches provider interfaces only through approval and work guards. Only Domain calls CaseRepository and creates trusted business AuditEvents. Domain and AuditPort share a transaction context for facts and required audit; diagnostic logs do not replace that atomic record. A saved intent must precede an external call because a database rollback cannot undo a provider effect. Notifications have separate work and state so a communications retry does not replay a return.

Figure 24 adds a C-supplied synthetic object snapshot for the existing shared structure task M-S.02 \[P12, P13\]. Named instances, selected slot values and links describe one pre-Founder-decision ESCALATE case, unlike the typed parts in Figures 9–11. It records no approval or execution and does not establish a running system or completed shared contribution.

Automatic retries and REVISE follow-ups are bounded; customer clarification has no fixed round cap. Exhaustion stops automatic work and preserves the actual result and any current proposal; escalation uses lawful targets and existing guards, without fabricating ProcessingFailure or an ESCALATE review. Human waiting and physical parcel movement are not counted as machine proposal latency. These are proposed runtime collaborations; their correctness still requires implementation, failure injection and independent review.

## Proposed deployment and existing environment

[Figure 12. Proposed local deployment and trust boundaries](<#xllaw9m8qlsx>)

The existing F.02 preparation provides a health-only FastAPI application, PostgreSQL environment, migration entry point, dependency locks, Compose and automated checks. The fifteen planned business operations are not implemented by those health endpoints. The deployment figure distinguishes intended components from this narrower verified environment. A future web interface reaches the API; the API controls database and adapter access. Local fixtures and test providers contain synthetic input, and live secrets remain outside Git and the report.

## <a id="_jgtlguukyz1f"></a>Personal chains and shared-model links

Figure references identify current report candidates, not individual completion or acceptance. Figure 24 supplements shared structure with a synthetic object snapshot. B's later shared candidates and index are separately sourced in \[P15\]: UCD-1 is an overall use-case view, OBJ-1 a synthetic named-instance snapshot, and COL-1 a numbered collaboration. They supplement the current overview, Composite and C object views; publication does not establish runtime behaviour or completed shared contribution.

| **Requirement and use case** | **Activity** | **Interaction and state** | **Shared structure** |
| --- | --- | --- | --- |
| A: AH-10 → UC-04; UC-03 approval context | [Figure 13](<#5cmh8j5fbczt>) | Sequences: [Figures 14–15](<#5vqmlb2gq640>)<br>State: [Figure 16](<#9bmil9zcr6vt>) | Classes: [Figures 5–8](<#s615ajmpz53u>)<br>Runtime: [Figures 9](<#7tu4fcoddh47>) and 11 |
| B: AH-01 → UC-01; UC-01E clarification | [Figure 17](<#9rlzgp8ypdk9>) | Sequences: [Figures 18–19](<#2wco8e7ki64s>)<br>State: [Figure 20](<#caaa9cna8q2c>) | IntakeSession and UI mapping: [Figures 5–8](<#s615ajmpz53u>)<br>Runtime: [Figures 9–10](<#7tu4fcoddh47>) |
| C: AH-08 → UC-02; UC-05 document responsibility | [Figure 21](<#yob7ra45allo>) | Sequence: [Figure 22](<#pl3vpuim0rgt>)<br>State: [Figure 23](<#n7wv812z15mp>) | Evidence/review/classes: [Figures 5–8](<#s615ajmpz53u>)<br>Runtime: [Figures 9–10](<#7tu4fcoddh47>) |

# <a id="_29fzj16eydnn"></a>6 Member A governed execution model

## Requirement and modelling rationale

A's individual chain is AH-10 to UC-04, with UC-03 as its approval precondition and alternative manual/reject boundary. The requirement is to execute only the approved simulated action and avoid duplicate effects. The models distinguish a proposed recommendation, a committed decision, a durable command intent, a provider effect, a saved result and a delivered notification. Combining these into one approval-success flag would conceal recoverable failures and unsafe retries.

These figures summarise MA-0.3; detailed guards and full diagrams remain in docs/12. A must examine and explain these candidates, and C's review is still required.

[Figure 13. A activity for governed execution and outcome notification](<#5cmh8j5fbczt>)

[Figure 14. A interaction for exact scope approval and dispatch](<#5vqmlb2gq640>)

[Figure 15. A interaction for recovery and notification](<#dkvrqlqj8lky>)

[Figure 16. A OperationAttempt state machine](<#9bmil9zcr6vt>)

## Normal and exceptional walkthroughs

For a normal eligible proposal, UC-03 checks trusted Founder identity and exact current scope and persists decision, approval, pending work and audit. UC-04 then records and claims work, checks authority again at the actual adapter invocation boundary and performs the simulated return. Label work references the saved return identity. Domain accepts complete results, then the independent notification path finishes the case. A duplicate HTTP request or worker must reuse the original accepted meaning or unfinished work; it must not mint an effect identity to bypass deduplication.

For an ambiguous label invocation, a previously successful return remains successful. If no trusted effect confirmation exists, abandoned work can become UNKNOWN and then RECONCILING under an authorised claim. A temporary NOT\_FOUND does not prove that the original invocation cannot complete. If a trusted label success receipt exists but downloading or saving the file failed, the attempt remains EXECUTING with only original-artifact retrieval/storage permitted. It becomes SUCCEEDED only after the complete result, bound label evidence and required audit are durable. Deleted content must not be recreated by recovery.

For an escalated case with no proposal, UC-03 may record only a manual decision on the current ProcessingFailure or OrderLookupBlock. It creates no approval or command. A successful manual outcome notification can then produce MANUAL\_HANDLED. If earlier effects are later confirmed, authorised history reconciliation records those facts while preserving an already accepted manual or rejection outcome.

## State interpretation and open design decision

OperationAttempt uses PENDING, EXECUTING, SUCCEEDED, FAILED, UNKNOWN, RECONCILING and BLOCKED. FAILED requires conclusive no-effect evidence; UNKNOWN preserves uncertainty; RECONCILING records active inquiry. Artifact-only recovery is an internal EXECUTING subphase rather than a new wire state. Notification retries do not change a successful attempt. New effects still require current approval and provider authority, whereas authorised recovery of historical facts uses a distinct permission scope.

The AD-0.2 proposal for a one-based attempt sequence is not part of the frozen rc.5 wire semantics: the schema still accepts zero. This report does not adopt a stricter minimum or redefine public fields. A and C must resolve the ID/count mapping and concurrency protocol before implementation. Local locking also cannot make the database and an external provider atomic; the mock must expose durable deduplication and effect observations, and any external test provider needs independent capability evidence \[P7\].

# <a id="_xna2zwiyaqnv"></a>7 Member B: customer interaction and intake models

Figures 17–20 are report views of B's published MB-0.2 chain \[P14\], derived from the original B delivery at 92cd717 through an A-led, AI-assisted compatibility correction. They present an Activity, two independent Sequence definitions and a durable IntakeSession state model. B's explanation and acceptance of the corrected candidate remain pending; later shared candidates and index corrections are separately recorded in \[P15\].

## Requirement, responsibility and use-case boundary

The informal need AH-01 is to describe a return or product problem without navigating internal systems. Its refined goal, UC-01, is to lodge one traceable request while preserving what the customer actually said. UC-01E supplies requested clarification or evidence when the server identifies missing information. This chain covers FR-001, FR-002, FR-005 and FR-011, with privacy, observability and untrusted-input constraints from NFR-003, NFR-008 and NFR-009. Its sources are the [use-case specifications, sections 4.3–4.4](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/05-lab-3-requirement-modelling.md>), [fixed allocation, sections 2.4–2.6 and 4](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/07-frozen-work-allocation.md>), and [rc.5 contract, sections 3–5, 7, 9 and 10.4](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/09-interface-contract-v1.md>).

B owns the Customer Intake and Clarification Portal, Founder Review Dashboard and selected Operations Analytics optional feature. This personal chain develops customer intake. A owns authentication, authoritative state, attachment binding and API effects. C owns retrieval, risk review and image observation. B renders authorised outputs and writes interface tests, without a second case database or transferring all tests to C.

For UC-01, a verified demonstration customer enters an original message and optionally an order identifier, requested outcome and evidence. Missing optional fields do not prevent submission. The server preserves the original statement independently of extracted facts. A successful resource creation returns a case reference; analysis may subsequently produce questions or progress towards assessment. Neither a submitted request nor a displayed receipt approves a remedy. Only synthetic or de-identified demonstration data is in scope.

## Activity and interaction design

Figure 17 describes one intake traversal. Its two ordinary admission actions refer only to the admission prefix of sd CustomerIntake (Figure 18), through the 201/202 or receipt/error response and excluding that interaction's processing ref. Only freshly accepted input/work then invokes sd ProcessAcceptedIntake (Figure 19), exactly once. Freshly accepted clarification follows the single return path to processing; replay or rejection ends this traversal. Questions are displayed only when this traversal's valid current result has committed them; the overview does not recommit questions or treat historical questions as a new result. Figure 19 has independent lifelines and an accepted-work precondition, not a continuation after replay or rejection. Stop symbols in Figure 17 end this traversal, not the durable session. Domain alone accepts business changes; A's Coordinator returns non-authoritative observations for its validation. G-A denotes the applicable fresh creation/clarification admission guards below. R1 is IDEMPOTENCY\_CONFLICT for a changed accepted payload; R2 is non-retryable INVALID\_STATE after receipt content is removed.

[Figure 17. ](<#9rlzgp8ypdk9>)[MB-ACT-0.2 — One intake traversal: admission prefix and one processing invocation.](<#9rlzgp8ypdk9>)

[Figure 18. ](<#2wco8e7ki64s>)[MB-SEQ-0.2a — sd CustomerIntake; only fresh acceptance invokes processing.](<#2wco8e7ki64s>)

[Figure 19. ](<#g8ggbkj0bxq9>)[MB-SEQ-0.2b — Independent sd ProcessAcceptedIntake; accepted work only.](<#g8ggbkj0bxq9>)

Uploads first create private STAGED attachments. Current candidate restrictions are JPEG, PNG or PDF, at most 10 MiB per file and ten references per submission; these are proposed technical limits, not course marking rules. Browser checks help the user, while A's server validates actual content, ownership, availability and binding. Creation or accepted clarification atomically binds eligible references; an upload alone changes no case input. Previews escape customer text, and downloads use authorised evidence references rather than storage credentials.

A fresh clarification is admitted only for the owner's case in AWAITING\_INFORMATION, with the current question\_set\_id and expected\_case\_version. Answers append a statement; they do not edit the original. An old question set, stale version or unsuitable state receives a blocking response. The interface reloads and asks the customer to confirm any genuinely new intent. There is no general customer append or reopen path after review or approval. UC-01E may repeat only when a refreshed authorised view exposes another current request for information.

Each POST uses a stable key for its logical request. An uncertain response is recovered with the same key and unchanged body. Authentication, the current route-role check, request validation and current resource authorisation also apply to every replay. The API rejects an invalid identity or role; Domain verifies current case/evidence access before reading or returning receipt content. Historical acceptance and a matching key cannot restore revoked access or disclose a former owner's data. Only then may a matching accepted request reuse its original readable receipt, followed by GET for current facts; this is not new admission against today's question set. Fresh state, version, question-set and attachment-binding checks remain distinct from those always-required access checks. If permitted deletion makes an otherwise authorised receipt unavailable, rc.5 returns 409 INVALID\_STATE with retryable=false. The UI must neither reveal removed text nor automatically generate a replacement key. A known case reference permits an authorised current/history read. Without a known reference, the UI presents the unresolved recovery condition; these models invent no customer case-search endpoint.

## Durable IntakeSession and interface separation

MB-STM-0.2 models the durable, case-owned IntakeSession required by M-B.04 \[P14\]. Its lifecycle\_state labels are internal design values, not new wire or ReturnCase states. COMPLETE and ESCALATED\_FAILURE are quiescent states, not UML finals. G-REENTRY requires an already committed legal Domain transition to AWAITING\_INFORMATION, a current case/input-bound ClarificationSet and existing source/state/effect/authority guards. From failure it additionally requires lawful proposal-bound Founder REQUEST\_REVISION followed by an assessment gap; a no-proposal failure has no restart, revision or re-entry path. Only authoritative COMPLETED, REJECTED or MANUAL\_HANDLED satisfies G-TERMINAL. The separate IntakeViewSession controls local drafting, pending/error display and closing/reopening; it cannot create these domain transitions. HTTP 201 means creation and 202 means acceptance, not completed processing. Replay or a rejected request creates no new lifecycle transition or work.

[Figure 20. ](<#caaa9cna8q2c>)[MB-STM-0.2 — Durable IntakeSession, quiescent states and guarded re-entry.](<#caaa9cna8q2c>)

Three choices shape the design. First, server-owned state makes refresh and concurrent-window behaviour consistent, at the cost of explicit loading and conflict handling. Second, staged uploads permit recoverable file selection before submission, but require atomic server binding and cleanup rather than trusting a preview. Third, stable request identity protects against duplicate cases after lost responses, while requiring the UI to distinguish uncertain acceptance, a readable historical receipt and a removed receipt. Removing a duplicate-click button alone would not provide these guarantees.

Role isolation applies to data, not just navigation. The customer receives CustomerCaseView and customer history kinds STATEMENT, EVIDENCE and OUTCOME\_MESSAGE; outcome messages are safe, already-sent messages. Founder proposals, risk records, approvals and internal audit are not downloaded and hidden with CSS. Preview windows are bounded, not complete history. Full history starts at its prescribed cursor and preserves the snapshot; tombstones remain unavailable instead of restoring deleted content from older revisions or local caches.

## Walkthroughs and B's discussion actions

In the normal walkthrough, a customer submits a faulty-item message without an order number. One case is created; later current questions permit a matching clarification with 202. A fourth still-incomplete round remains AWAITING\_INFORMATION. The exception walkthrough distinguishes a lost response recovered with the same key, a removed receipt, a rejected stale intent and an actual current Coordinator failure after accepted initial or clarification input. Only the last, after bounded recovery, can persist a real ProcessingFailure under exact-target guards. Missing facts, UI silence and admission errors cannot supply that target. Revoked access blocks receipt recovery; unauthorised attachments remain unbound. Browser reopening does not restart a no-proposal failure.

B must personally inspect the original PR 14 delivery and the A/AI-assisted MB-0.2 correction \[P14\], record attributable revisions, and explain the independent interactions and guarded durable-session transitions. Accessibility, safe error wording and correspondence with current API examples still require B's own review. The unknown-case-reference recovery experience, optional attachment replacement, and retained local draft lifetime need A/B discussion within the data and interface contract (F.01), server-side authorisation (F.03), and privacy, model-input and retention controls (F.07). Later acceptance requires B-owned component/E2E evidence and non-author review under M-B.01–.06 and B1.01–.05. The diagrams alone establish none of those outcomes.

# <a id="_zfiavx5vnmqu"></a>8 Grounding and independent risk review

C published the MC-0.1.2/MC-RPT-0.3 report views used in Figures 21–23 and the shared object snapshot in Figure 24 \[P12\]. Figure 21 was clarified as two guarded control-flow panels with AI assistance under C’s authorisation on 21 September 2026; Figures 22–24 retain their published sources. Personal explanation, attributable revisions and shared participation remain required.

## Requirement, use case and responsibility

AH-08 states: “Show material source conflicts; if they prevent a safe proposal, stop and hand the case to me.” The corresponding UC-02 prepares an evidence-grounded decision packet for the Human Founder. A successful assessment ends with a stored, versioned, non-executable packet and a current PASS or PASS\_WITH\_WARNING review. It does not approve or execute a return. Missing information or an unresolved blocking conflict produces an explicit alternative path. This chain primarily addresses FR-006, FR-008 and NFR-009, with FR-007 and FR-011 supporting proposal and audit traceability.

Under the fixed allocation, C1 provides versioned retrieval and citation verification, C2 provides independent risk review, and the selected C3 feature later extracts observations from authorised synthetic images. A owns Assessment, orchestration and authoritative state changes; B owns the interfaces. C also maintains the UC-05 specification for inspecting case status and history. That documentation responsibility does not transfer B's dashboard implementation or A's authorised history API to C. UC-05 supports explanation of review provenance and uncertainty, while the personal behaviour chain below remains centred on AH-08 and UC-02. Each historical page must recheck current permission and snapshot/query binding; legitimate removal remains a tombstone rather than reconstructed content \[P16\].

## Evidence and authority boundaries

C1 retrieves from a small, reviewed corpus. Each passage preserves its source identity, type, applicable version, access date, location, content hash and retrieval time. NO\_MATCH is a valid retrieval result, not a successful risk review or a technical exception. Citation verification checks whether a reference resolves to the expected version, location and content; C2 separately asks whether that content supports the proposal's actual claim.

The rc.5 RiskReviewRequest contains the packet, original statements, authorised attachment references, order lookup, evidence matrix, complete accepted retrieval result, citation verification and optional image observations. The evidence matrix is Assessment's interpretation, not an independent source of truth. Known conflicts remain present even when the packet cites no passage. Domain validates matching case, input, proposal and corpus bindings, assembles the complete historical evidence bundle, and accepts that bundle atomically with the new proposal before review. It cannot replace full evidence with a dashboard preview, silently truncate necessary material, or claim removed source content was checked.

The C-F01 fixture-oracle correction \[P10\] checks that retained verification binds the historical proposal ID/version and exactly its citation IDs. A failed citation status alone is not a reason to discard retained history; it is not evidence that a claim is supported or that a Risk outcome passes.

C2 uses a separate prompt and model invocation without Assessment's hidden reasoning. Its structured response remains untrusted until Domain validates its shape and current bindings. Every accepted review identifies the exact case, input version, proposal ID/version and corpus version. C2 cannot edit the proposal, write authoritative state, create an approval or call an operations provider.

## Behaviour models and outcome handling

The C activity model follows AH-08 through UC-02. C1 retrieves versioned sources and preserves the original conflicts; Assessment drafts a candidate, and C1 verifies its citation references. Domain validates and atomically accepts the complete packet, evidence bundle and required audit before the orchestrator invokes independent C2 review. Figure 21 separates admissible current material, stale events and bounded technical recovery from the five accepted business outcomes. A resolvable citation is not proof that a claim is supported. The routing table contains exactly five business outcomes:

| **Outcome** | **Domain-controlled continuation** |
| --- | --- |
| PASS | Offer the current packet for Founder review; no execution authority follows. |
| PASS\_WITH\_WARNING | Show explicit warnings before Founder review; no blocking finding is permitted. |
| REVISE | Return specific revision requests to Assessment; a new proposal needs a new review. |
| NEEDS\_INFORMATION | Return questions through Coordinator and UC-01E; preserve the input history. |
| ESCALATE | Present reasons to the Founder. For a current proposal, a valid REQUEST\_REVISION may request a new proposal and independent review, or MANUAL\_HANDLING records a manual outcome. The escalated proposal cannot receive execution approval. |

[Figure 21A–B. C activity: validation, bounded recovery and five-outcome routing](<#yob7ra45allo>)

The sequence model shows that Domain supplies the accepted evidence bundle to C2 instead of trusting Assessment to reconstruct supporting sources. A timeout or malformed response follows bounded technical recovery and cannot become PASS. A validly shaped but stale response is rejected for current use. Neither failure nor staleness creates a sixth business outcome. A proposal-level ESCALATE does not remove the Founder's valid revision path: any return to execution requires a new proposal and a new PASS or PASS\_WITH\_WARNING review, followed by exact approval. The stricter manual-only rule applies when no current proposal exists and the target is a persisted ProcessingFailure or OrderLookupBlock; those targets never permit revision or execution approval.

[Figure 22. C interaction: accepted evidence and an independent reviewer](<#pl3vpuim0rgt>)

The state model follows one internal ProposalReview work lifecycle bound to a proposal/input/corpus, separate from the shared-class result and wire RiskReview. Its seven phases are not ReturnCase states, business outcomes or new wire fields. An accepted RiskReview remains immutable when retired to history; its old passing result cannot authorise a later proposal. Domain owns guarded acceptance, recovery, retirement and business audit.

Same-version recovery follows the selected MC-D01–03 design. Seven review-work phases remain internal and each accepted RiskReview is immutable with the existing five outcomes. G\_START checks queued work/round before an invocation exists. Domain atomically matches selected work, round, invocation and phase for reply, validation, timeout, retirement, retry, exhaustion and audit effects. A stale event cannot alter a replacement invocation or its business audit outcome. Each logical analysis call permits at most two durable reservations (initial plus one technical retry); each admitted episode permits one automatic REVISE follow-up. The 2/1 defaults persist with the episode, so retry, restart and redelivery do not reset them; a valid clarification answer or proposal-bound Founder REQUEST\_REVISION admits a separate episode. These are prototype configuration defaults, not public wire fields, measured optima or implemented race protection.

If the follow-up again returns REVISE, Domain preserves that actual outcome and current proposal, stops automatic processing and records the budget reason; it does not rewrite REVISE to ESCALATE or fabricate ProcessingFailure. The current proposal remains available for lawful REQUEST\_REVISION or MANUAL\_HANDLING but not APPROVE. A real initial or admitted-revision technical failure with no current proposal instead uses the existing manual-only ProcessingFailure target.

[Figure 23. C state model: review acceptance, failure and historical validity](<#n7wv812z15mp>)

## Design choices and walkthroughs

**Deterministic citation checks plus semantic review.** A resolvable citation can still fail to support a claim. Splitting these checks makes a wrong hash distinguishable from unsupported reasoning, at the cost of additional interfaces and tests. Keyword/BM25 retrieval keeps the initial corpus inspectable; vector retrieval is a later comparison, not a prerequisite for this report.

**Independent review rather than self-approval.** A separate invocation can challenge the generator without inheriting its hidden reasoning. It adds latency and model cost; correlated model error can remain despite separate prompts and calls \[P16\]. Domain validation and the separate Founder gate remain necessary even after a passing response.

**Immutable evidence rather than reconstructed history.** Saving the accepted bundle makes a past recommendation explainable against the sources actually used. Storage and retention handling become more demanding; deleted content must remain unavailable rather than being reconstructed through an old review.

Three synthetic walkthroughs test consistency without claiming measured performance. In the normal path, matching order evidence and supporting passages produce a conditional packet, valid citations and a current PASS; Domain offers it to the Founder. In the conflict path, store-policy and guidance passages disagree materially; C1 preserves both and C2 returns ESCALATE when no safe proposal can be supported. This is a business finding, not an OrderLookupBlock. In the missing-information path, C2 returns NEEDS\_INFORMATION with a relevant question; an accepted answer changes the input version, and the regenerated proposal requires another independent review.

## Verification plan and remaining confirmation

Planned C tests cover source provenance, missing and altered citations, all five outcomes, prompt injection, invalid output, stale bindings and failure recovery. The evaluation plan uses separate pilot inputs, 30 double-reviewed Gold cases and a required single-LLM B1 versus governed B4 comparison. The 30-case set is a small controlled project evaluation, not a representative sample of Australian retailers or disputes \[P16\]. Targets and procedures are not results; this draft contains no Gold labels. C must confirm the conflict criteria, question quality, lifecycle guards, actual personal edits and shared-model contributions. A/C must review the hand-off semantics together. Personal explanation, non-author review, implementation evidence and measured evaluation remain outstanding.

Source basis: project definition, frozen allocation, Lab 3 specifications and F.01 rc.5 (project documents 00, 07, 05 and 09). The course Stage 1 rubric requires the personal requirement/use-case/activity/interaction/state chain and identifiable participation in shared work.

# <a id="_t8t47hcoejvw"></a>9 Design choices and change assessment

The design combines layered presentation/application/domain responsibilities, typed ports and adapters, and bounded orchestration. It uses specialised AI roles for interpretation and independent review while retaining deterministic authority at Domain and Operations. This choice provides a concrete application of the architecture and class-design work requested in Laboratory 5 \[C3\]. It does not require microservices or every agent pattern mentioned in the laboratory.

| **Decision** | **Reason and requirement impact** | **Cost or limitation** |
| --- | --- | --- |
| One modular application and PostgreSQL | A single authority simplifies version checks and audit; NFR-004/007 | Shared process/resources need bounded work and careful failure isolation |
| Structured AI output and deterministic gates | Models interpret evidence; only trusted services grant effects; FR-007–010 | Schema validity is insufficient without semantic and runtime checks |
| Independent Risk invocation | Challenges evidence support and scope; FR-008/NFR-009 | Adds latency and cost and may share model biases |
| Keyword/BM25 over a reviewed corpus | Inspectable provenance and a manageable baseline; FR-006 | Vocabulary mismatch may reduce retrieval quality |
| Versioned decisions and stable work identities | Avoid stale approval and duplicate effects; NFR-002/004 | Requires durable transactions, concurrency coordination and recovery |
| Separate notification and operation state | Communication retries do not duplicate returns; FR-010/011 | More explicit states and failure handling in the interface |
| Synthetic mock-first delivery | Repeatable safe tests and observable effects; NFR-003/006 | Does not establish production-provider behaviour |

A single unrestricted prompt was not selected for deployment because it would combine interpretation, recommendation and tool authority without independently verifiable boundaries. It remains the offline B1 comparison with no retrieval or operational permission. Automatically following a failing or escalated review was rejected because it would turn model failure into permission. Broad exception handlers that retry all operations were rejected because an unanswered call can still have produced an external effect.

Microservices, a distributed queue, vector infrastructure and a live commerce integration were deferred to keep the course prototype testable. The selected logistics test extension remains an independent increment over the core mock, but it cannot proceed without suitable access and recovery semantics. The team must assess a concrete authorised alternative with the lead and, where needed, tutor; merely renaming the mock does not satisfy that requirement.

A change is assessed against requirement IDs, affected use cases and diagrams, public compatibility, safety, workload and verification evidence. Internal naming or presentation changes can follow ordinary review. Public semantics require producer/consumer review and a compatible or versioned migration. A change to scope, ownership, selected optional, dependency or acceptance strength needs an explicit material-change decision under the existing allocation rules. The rejected/accepted alternative and its evidence remain visible rather than being erased from the report.

The current report retains three specific questions for discussion: the interpretation of attempt identifiers and count; how original effect recovery interacts with new approvals; and how current authority is coordinated with dispatch at a provider boundary. The rc.5 correction already distinguishes a known label effect with unfinished artifact storage from an unknown effect. None of these design descriptions proves the future concurrency implementation.

# <a id="_gn0abb84naan"></a>10 Verification and evaluation plan

## Model and implementation verification

Verification starts by walking the same scenarios through requirements, use cases, activity, sequence and state models. For customer intake, the relevant cases are a normal request, missing information, stale questions and a lost acknowledgement. For Risk, they are supported evidence, material conflict, missing information, invalid output and stale bindings. For execution, they are exact approval, wrong scope, duplicate work, ambiguous effects and notification failure. Each walkthrough must identify guards and the last durably known state, not simply reach a desired ending.

Later implementation evidence includes contract, unit, API/database, provider, UI and end-to-end tests. A tests authoritative state, authentication, attachments, approval, concurrency, recovery, privacy and integration. B tests its components and user flows. C tests retrieval, citations, independent Risk and image observations and coordinates evaluation. Each member fixes and explains their own failures; evaluation coordination does not make C responsible for everyone else's tests.

| **Requirement and model example** | **Implementation responsibility** | **Planned decisive test** |
| --- | --- | --- |
| FR-001/002, B intake Activity/Sequence/State | B1 interface with A1, identity/authorisation (F.03) and attachment backend (F.04) | Lost response, same request identity and legal clarification preserve one case |
| FR-006/008, C grounding and review models | C1/C2 with A1 orchestration | Unsupported or stale evidence never yields eligible current approval |
| FR-009/010, A execution models | A2 and identity/authorisation (F.03) | Wrong scope, actor, version or expiry produces zero provider effects |
| NFR-004, OperationAttempt recovery | A2.04/.05 | Ambiguous effect is queried using its original identity; no duplicate |
| FR-010/011, A recovery Sequence | A2.06 and audit queries (F.05) | Notification-only retry leaves successful return/label effect counts unchanged |
| NFR-003/009, role and retention boundaries | Attachment backend (F.04), privacy, model-input and retention controls (F.07), B interface and C input handling | Removed receipt content is unavailable and cannot be reconstructed or replayed as new work |
| FR-012, Founder view and UC-05 | B2/B3, audit queries (F.05) and statistics API (F.06) | Counts use the defined case/current-review denominator, including missing data |

## Controlled comparison

## <a id="_bo9ilwfb3byi"></a>Two distinct evaluation activities

| **Study** | **Cases and access** | **Activity and timing** | **Planned reporting** |
| --- | --- | --- | --- |
| Student-operator baseline | 20 stratified cases from the 30 Gold inputs; A/B work independently without labels, using the same order, evidence and corpus. | Time active reading, checking, recording and decision-packet preparation. Pause simulated customer, provider, Founder and physical waiting; retain the existing randomisation and sealing protocol. | Per-operator and pooled medians, IQRs, omissions, scenario mix and learning/order effects. This is not merchant performance or end-to-end resolution time. |
| Automated B1 versus B4 | All 30 Gold cases under fixed model conditions. B1 has no retrieval or operation authority; B4 includes retrieval, independent review and deterministic gates. | Use the configuration-specific packet endpoints below: B1 saves its candidate response; B4 saves a reviewed packet. Include machine work; disclose valid timing samples, failures and unmeasured cases. Score frozen outputs. | Quality/safety counts, denominators, failures, p50/p95, tokens and cost. Compare the architecture bundle; no isolated multi-agent causal claim or measured result is implied. |

The planned formal dataset contains 30 double-reviewed Gold cases across the three supported categories, complete and incomplete inputs, conflicts, escalation, out-of-scope requests and representative prompt injection. A separate set of 10–20 pilot cases supports prompt and rule development. Gold labels are not tuning data, and this draft does not create or disclose them.

Twenty timed student-operator cases form a stratified subset of those 30 inputs. C seals all initial labels, source reasons, versions and hashes before reading any timed answers. A and B independently process the inputs in separately randomised orders without Gold labels, each other's answers or scoring feedback. After both outputs are locked, C hands over the sealed labels, A reviews all cases, B arbitrates unresolved disagreements and C freezes the final manifest before scoring. Source-based changes retain the original labels and rationale; the process cannot adjust answers to improve observed agreement. The operators also participate in later review, so the study does not claim external blind adjudication or merchant representativeness.

The required experiment compares offline single-LLM B1, without retrieval or operation permission, against full governed B4. Both use the same formal cases and underlying model conditions while preserving their defined architectural differences. The comparison estimates the effect of the whole architecture bundle; it cannot isolate the causal benefit of multi-agent decomposition. B2/B3 ablations are portfolio work and are not confused with member B's feature identifiers.

Metrics include classification macro-F1, mandatory-information recall, unsupported critical facts, citation coverage and correctness, risk recall and specificity, schema validity, completion/failure rates, latency and model cost. Targets include citation correctness at least 90%, classification macro-F1 at least 0.85, information recall at least 95%, risk-escalation recall at least 95%, specificity at least 80%, zero unauthorised or duplicate effects and proposal p95 below 120 seconds. The 100% citation-coverage target applies to claims requiring sources; empty denominators and failures must be reported explicitly.

Proposed benchmark timing requires team confirmation. Use the same frozen complete input: start B1 at offline runner acceptance and B4 at Domain acceptance, before machine processing. End B1 when its offline runner saves the schema-valid candidate packet and self-declared disposition; end B4 when Domain saves a current ready packet and its bound PASS, PASS\_WITH\_WARNING or ESCALATE review. Include all permitted machine work under the frozen configuration: B1 remains single-call, while B4 includes review/revision and bounded recovery. REVISE continues the episode; NEEDS\_INFORMATION without a later ready packet is unmeasured. Exclude only human/physical waiting.

Freeze the cutoff and select the latest assessment episode for the current input, without inherited timing from earlier inputs: count each case once as a valid measured packet, a terminal technical failure without a valid packet, or otherwise unmeasured; totals equal 30 separately for each automated configuration. Incomplete inputs and valid pre-proposal stops are unmeasured. Revisions are not extra samples.

For sorted valid times x(1), ..., x(n), nearest-rank Pq=x(ceil(q\*n)), q=0.50/0.95; n=0 is unavailable. Display n/30 and failed/unmeasured counts beside p50/p95; log failure durations separately. Conditional p95 alone cannot establish reliable performance. Preserve raw times, outcome counts, failure examples, tokens/cost, environment and dataset/corpus/prompt/model/configuration/scoring-code/commit versions. These are benchmark conventions, not rc.5 analytics changes or measured results; the small sample cannot establish population performance.

## <a id="_11ewa591rasr"></a>Scoring clarification proposed for the label guide

Before formal runs, confirm and freeze scoring eligibility and missing-output treatment. Proposed citation coverage is source-dependent claims with resolvable citations divided by all source-dependent claims; correctness is supported claim–citation links divided by submitted claim–citation links. Without citations, correctness is unavailable, never 100%; missing required citations reduce coverage. Without source-dependent claims, coverage is unavailable. A missing packet remains a failure in all-30 accounting; report each metric's eligible count. These proposed conventions do not change rc.5 analytics or create results.

Proposed risk convention, requiring team confirmation: before outputs, freeze a common B1/B4 risk cohort expected to reach proposal review. Gold positive means source-supported unresolved evidence/authority problems require ESCALATE; negative means otherwise. Legitimate pre-proposal clarification/order blocks remain in all-30 workflow accounting; observed failure never removes eligibility. B4 predicts from its last current Domain-accepted review at the frozen cutoff. B1 self-declares the same disposition in its single-LLM response; no extra reviewer, retrieval, API or operation authority is added. ESCALATE predicts positive; PASS, PASS\_WITH\_WARNING, REVISE and NEEDS\_INFORMATION predict negative for escalation only, not workflow completion or permission.

Missing, malformed, stale or technically failed predictions are unavailable: U+ or U- by Gold class. Technical ESCALATED case states do not count as Risk predictions.

Valid predictions form TP/FN/TN/FP. Ordinary recall=TP/(TP+FN) and specificity=TN/(TN+FP) are conditional on availability. Separately, conservative target checks use TP/(TP+FN+U+) and TN/(TN+FP+U-); never label these ordinary metrics or claim attainment from valid-only rates. Undefined denominators are unavailable; retain U counts and all 30 workflow outcomes.

Non-Gold arithmetic illustration only: four risk-eligible toy cases are (Gold, prediction, valid seconds): (+, ESCALATE, 12), (+, PASS, 20), (-, PASS, 16), (-, technical failure, unavailable). TP/FN/TN/FP=1/1/1/0; U+/U-=0/1. Ordinary recall/specificity are 50%/100%; conservative checks are 50%/50%. Sorted valid times 12,16,20 give nearest-rank p50=16s and p95=20s. Sample/failed/unmeasured=3/1/0. This is hand calculation, not performance evidence or an added case-count commitment.

# <a id="_3iigzxz4b4fw"></a>11 Delivery status and contribution plan

## Existing evidence and its limits

The recorded rc.5 preparation checks passed \[P8\]; they do not establish implementation of the fifteen proposed business operations, benchmark results or team acceptance. Appendix A records the tested revisions and check counts.

B approved five consumer-boundary items for exact A source 3dd1ff6 \[P11\]. C's earlier records and current figure/text sources remain \[P10\], \[P12\] and \[P16\]. C has since published the six-scope F.01 review and exact-A PG17 Compose reproduction in open PR 17 \[P17\], including 32 environment tests, repeat migration and same-API database outage/recovery. These are reported AI-assisted artifact/infrastructure results; this integration does not rerun them. Personal explanation and joint F.01/F.02 acceptance remain outstanding. C's review recorded one notification-fixture wording finding; A's separate correction candidate \[P19\] does not establish F.01 acceptance.

| **Member** | **Fixed responsibility** | **Contribution status to preserve in the final report** |
| --- | --- | --- |
| A - Jingbo Chai | A1/A2/A3; architecture, own model chain, shared structure and integration | A led AI-assisted delivery of the execution chain (Figures 13-16), shared class/runtime views (Figures 5-11), report integration and later compatibility corrections \[P6, P7, P10, P14, P15\]. Draft index \[P18\] preserves B's ownership. Personal explanation and actual participation in every shared task remain to be confirmed. |
| B - Chengsi Li | B1/B2/B3; own intake chain, Feature/Use-case/model-index integration | Original B delivery includes PR 8 shared models and the PR 14 intake chain (Figures 17-20), followed by separately attributed A/AI corrections \[P6, P14, P15\]. Exact-A consumer approval is recorded \[P11\]. Personal explanation and actual participation in every shared task remain to be confirmed. |
| C - Yuwei Tao | C1/C2/C3; own Risk chain, classification, evaluation and evidence checks | C commissioned AI-assisted delivery of grounding/Risk views (Figures 21-23), the object snapshot (Figure 24), course coverage and clarifications \[P10, P12, P13, P16\]. Later technical review and PG17 reproduction are reported in \[P17\]. Personal explanation and actual participation in every shared task remain to be confirmed. |

The team identities are confirmed above. The final contribution record remains evidence-based. For each member, identify the independent requirement, use case and three behavioural models. For every shared task, record the concrete action, figure or section, attributable revision, and review/explanation status. Class/relationship changes, ports/connectors or substantive corrections are examples. Distinguish authorship, review and integration and retain original PR attribution. Everyone must participate in all shared modelling tasks; report actual parts or evidenced percentages \[C1\]. The planned 45/27/28 split is not measured contribution. Model availability or candidate review does not establish independent completion; unverified work remains pending.

The course coverage map \[P13\] adds the Lab 6 object snapshot to the existing Composite views. Optional rubric modelling rows do not cancel the nine fixed features or each member's selected optional feature. The complete requirements document remains part of Stage 1 submission.

## Report and implementation sequence

Video production is handled separately by the team, outside this report-editing work. A coordinates integration and submission; C checks final evidence and accessibility. The course's stated eight-minute video limit and individual interview preparation remain in scope \[C1\]. Appendix A records the written-submission checks and the scope of this report work.

C's dated Canvas record \[P17\] clarifies one group PDF and the 15 report + 10 interview grouping. The signed-in report and video pages were checked again on 21 September 2026 \[C5, C6\]: one designated member submits the group PDF; the separate video is at most eight minutes and must be uploaded to Canvas. Both pages display 4 October 2026 at 23:59; the 11 October availability end is not an extension. Check the submitting account's timezone, new announcements and each member's assigned Week 11/12 interview slot before submission. Appendix A retains the older observations and the dated update.

Business implementation follows the existing work-package dependencies. Acceptance of the data and interface contract (F.01) permits its dependent schema and integration work. The first executable milestone uses fixed proposals and mock reviews to verify deterministic approval, effects, recovery and audit before an LLM can reach an executable path. B can prepare mock interfaces, and C can prepare offline retrieval/review work within their allowed dependencies. Later, the complete B4 workflow runs on pilot cases before the formal frozen comparison. Selected optional features remain tracked through course release, including A3's unresolved test-access dependency.

Jira records ownership, estimates, planning and status history; GitHub records technical scope, commits, reviews and checks. Each delivery item uses one real Jira key with reciprocal links. Appendix A retains the WBS interpretation and last observed navigation issue.

# <a id="_ula0uicn2uvh"></a>12 Submission checks and unresolved decisions

The following decisions remain open rather than silently adopted. B with A must agree a contract-consistent customer recovery experience when an accepted creation response and its receipt are unavailable and no case identifier is known; the current API contains no customer case-search endpoint. A with C must record attempt ID/count mapping and compatibility impact: frozen rc.5 still accepts zero, so this report adopts no new one-based wire minimum. A with C must specify authority/concurrency at provider dispatch and tests for uncertain effects; a database transaction cannot make an external provider atomic. C with team review must refine claim support, material conflict and question criteria, and freeze benchmark eligibility, timing and missing-output rules before formal runs. C with A/B must define image-observation admission, unreadability and injection cases without adding approval authority. A must obtain authorised A3 logistics test access or record an explicitly accepted scope change; the core mock does not count again as that extension. Each decision requires a dated owner response and updates to affected requirements, models and tests. These statements identify required decisions, not completed implementation or acceptance.

Before submission, each member must explain one normal and one principal exception across their requirement, use case, three behavioural models and shared structure; record authority/state changes and attributable contributions in Section 11.

The report retains the stated nine-feature scope and reviewed model sources. The open alternatives above are not adopted API rules or implementation results. A3 remains subject to actual test access and the required scope/tutor decision.

Written submission remains subject to the final contribution record and team review, accurate AI acknowledgement, inclusion of the complete requirements document, export checks and the remaining task-specific details. Video production is managed separately by the team; personal interview preparation remains each member's responsibility. Implementation evidence remains distinct from Stage 1 design completion.

# <a id="_ccpv0bmju8cr"></a>13 References

\[C1\] ELEC5620 teaching team. Project Stage 1 Marking Criteria. Local course PDF, pages 1–2. Individual chains, shared modelling, video and interview requirements.

\[C2\] ELEC5620 teaching team. Project Description. Local course PDF, pages 1–2. Requirements documentation, architecture, modelling, assumptions and later prototype delivery.

\[C3\] ELEC5620 teaching team. Laboratory 5. Local course PDF, page 1. Architecture patterns, rationale, class attributes/methods, interfaces and multiplicities.

\[C4\] University of Sydney. ELEC5620 2026 unit outline, Semester 2 (S2C-ND-CC). Assessment and use of generative artificial intelligence. Accessed Sep 8, 2026. [Official ELEC5620 2026 unit outline](<https://www.sydney.edu.au/units/ELEC5620/2026-S2C-ND-CC>)

\[R1\] Australian Competition and Consumer Commission. Repair replace refund cancel. Accessed Sep 7, 2026. [ACCC remedy guidance](<https://www.accc.gov.au/business/problem-with-a-product-or-service-you-sold/repair-replace-refund-cancel>)

\[R2\] Australian Competition and Consumer Commission. Receipts bills proof of purchase. Accessed Sep 7, 2026. [ACCC proof of purchase](<https://www.accc.gov.au/business/selling-products-and-services/receipts-bills-proof-of-purchase>)

\[R3\] Shopify. returnCreate mutation, Admin GraphQL API 2025-10. Accessed Sep 7, 2026. [Shopify returnCreate API](<https://shopify.dev/docs/api/admin-graphql/2025-10/mutations/returnCreate>)

\[R4\] Office of the Australian Information Commissioner. Small business. Accessed Sep 7, 2026. [OAIC small business guidance](<https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/small-business>)

\[P1\] ReturnOps AU. F.01 rc.5 review and source tree. [PR 11](<https://github.com/shuxiachai/returnops-au/pull/11>); source commit 64582a3007fea0fa3d1b1c3c212168b96af6b607. New report-specific content is not in that commit.

\[P2\] ReturnOps AU. Project definition, frozen allocation and delivery work packages. [Product definition](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/00-project-definition-v1.md>), [fixed allocation](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/07-frozen-work-allocation.md>), and [delivery work packages](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/08-delivery-work-packages.md>), pinned to the technical reference revision.

\[P3\] ReturnOps AU. [Requirements Desk-Research Evidence Register](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/06-requirements-desk-research-evidence.md>). Frozen research cut-off Aug 25, 2026; report summarises its design implications.

\[P4\] ReturnOps AU. [A3 Logistics Sandbox Feasibility](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/17-logistics-sandbox-feasibility.md>). User-confirmed absence of Australia Post/StarTrack contract and test access, with unresolved options.

\[P5\] ReturnOps AU. [Laboratory 3 Requirement Modelling](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/05-lab-3-requirement-modelling.md>). Six source use-case specifications and ad-hoc requirement mapping.

\[P6\] ReturnOps AU. Shared class and feature/use-case models, MA-0.3, CS-0.2 and PD-0.2. [Class model](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/diagrams/01-domain-class-diagram.md>), [A models](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/12-member-a-model-chain.md>), [shared runtime structure](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/13-shared-composite-structure.md>), and [package/deployment](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/15-package-deployment-models.md>). Prior B contribution: [B shared-model PR 8](<https://github.com/shuxiachai/returnops-au/pull/8>).

\[P7\] ReturnOps AU. [Member A Design Decisions](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/14-member-a-design-decisions.md>) and [Demo Identity/Authorization](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/16-demo-identity-authorization.md>). Proposed recovery, work coordination and trusted-context rules.

\[P8\] ReturnOps AU. [PR CI run](<https://github.com/shuxiachai/returnops-au/actions/runs/34124765642>) and [push CI run](<https://github.com/shuxiachai/returnops-au/actions/runs/34124762875>). Source head 64582a3; PR synthetic checkout b3fe4d07ac805bc0e1d1870f1404416636be63d0.

\[P9\] ReturnOps AU. [Stage 1 readiness and recorded Canvas observations](<https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/11-stage1-readiness.md>). [Canvas report entry](<https://canvas.sydney.edu.au/courses/74323/assignments/695832>); [Canvas video entry](<https://canvas.sydney.edu.au/courses/74323/assignments/695833>). Prior C Jira-guide contribution: [C Jira-guide PR 7](<https://github.com/shuxiachai/returnops-au/pull/7>).

\[P10\] ReturnOps AU. [C models](<https://github.com/shuxiachai/returnops-au/blob/32c704f6bf4b86139b0bcbe53419fe23530fdd97/docs/18-member-c-model-chain.md>), [C report contribution](<https://github.com/shuxiachai/returnops-au/blob/32c704f6bf4b86139b0bcbe53419fe23530fdd97/docs/reports/member-c-stage1-draft.md>) and [C follow-up](<https://github.com/shuxiachai/returnops-au/blob/32c704f6bf4b86139b0bcbe53419fe23530fdd97/docs/reviews/member-c-followup-20260914.md>) at commit 32c704f; [A correction](<https://github.com/shuxiachai/returnops-au/commit/3dd1ff637693a826990eee5712cfb239a3c3da7b>) at 3dd1ff6; MC-D01–03 technical disposition in [PR #12 review](<https://github.com/shuxiachai/returnops-au/pull/12#pullrequestreview-5196102404>). Exact sources for the earlier C integration and its limits.

\[P11\] ReturnOps AU. B consumer-boundary review of the exact A source at 3dd1ff6: [PR #11 review](<https://github.com/shuxiachai/returnops-au/pull/11#pullrequestreview-5196057965>).

\[P12\] ReturnOps AU. [C model chain](<https://github.com/shuxiachai/returnops-au/blob/c9f205d578595fd7c9b4e65c67c6ff3c65d3fa44/docs/18-member-c-model-chain.md>) and [report contribution](<https://github.com/shuxiachai/returnops-au/blob/c9f205d578595fd7c9b4e65c67c6ff3c65d3fa44/docs/reports/member-c-stage1-draft.md>), MC-0.1.2/MC-RPT-0.3 at c9f205d; Figures 22–24 retain its report views; Figures 21A–B adapt the C activity model with dated AI-assisted clarification on 21 September 2026.

\[P13\] ReturnOps AU. [Course assessment requirements](<https://github.com/shuxiachai/returnops-au/blob/b3b3b5869d33704e9f1da5b777c8c9338de6b565/docs/19-course-assessment-requirements.md>) at b3b3b586; recorded rubric and Lab 6 coverage, not a fresh Canvas check.

\[P14\] ReturnOps AU. [Original B delivery](<https://github.com/shuxiachai/returnops-au/commit/92cd717a87a1aff745044342498d4caae196dc15>) at 92cd717; MB-0.2 compatibility correction at 4d91a58: [B model chain](<https://github.com/shuxiachai/returnops-au/blob/4d91a58f8f05f489ac61e05605852df4bc428c24/docs/19-member-b-model-chain.md>), [report contribution](<https://github.com/shuxiachai/returnops-au/blob/4d91a58f8f05f489ac61e05605852df4bc428c24/docs/reports/member-b-stage1-draft.md>) and [correction disposition](<https://github.com/shuxiachai/returnops-au/blob/4d91a58f8f05f489ac61e05605852df4bc428c24/docs/reviews/b-model-compatibility-disposition-20260914.md>). Original B authorship, A-led AI-assisted correction and the derived report views are distinct; B's personal explanation/acceptance remain pending; later shared candidates and index are separately cited in \[P15\].

\[P15\] ReturnOps AU. Shared candidates and model-index correction at 1b094289c219727d9e42e694ade6f13431c34c7b: [overall use-case model](<https://github.com/shuxiachai/returnops-au/blob/1b094289c219727d9e42e694ade6f13431c34c7b/docs/diagrams/05-use-case-diagram.md>), [object snapshot](<https://github.com/shuxiachai/returnops-au/blob/1b094289c219727d9e42e694ade6f13431c34c7b/docs/diagrams/06-object-diagram.md>), [collaboration model](<https://github.com/shuxiachai/returnops-au/blob/1b094289c219727d9e42e694ade6f13431c34c7b/docs/diagrams/07-collaboration-diagram.md>), [shared index and traceability](<https://github.com/shuxiachai/returnops-au/blob/1b094289c219727d9e42e694ade6f13431c34c7b/docs/reports/stage-1-team-report.md>), and [correction disposition](<https://github.com/shuxiachai/returnops-au/blob/1b094289c219727d9e42e694ade6f13431c34c7b/docs/reviews/b-shared-model-followup-20260917.md>). Original B delivery and A-led, AI-assisted corrections remain distinct; final shared acceptance is pending.

\[P16\] ReturnOps AU. [C boundary clarifications](<https://github.com/shuxiachai/returnops-au/blob/15c136a1f717ba074d4aa77a0572d159c28cda8c/docs/reports/member-c-stage1-draft.md>) at 15c136a, selected from MC-RPT-0.4; [C integration review](<https://github.com/shuxiachai/returnops-au/pull/14#issuecomment-5696352699>) is an AI-assisted static review, not C's personal sign-off. The later text adds no new figure or runtime evidence; \[P12\] retains the current C figure sources.

\[P17\] ReturnOps AU. C evidence and signed-in Canvas observations recorded on Sep 20, 2026. Source a3679456 ([open PR 17](<https://github.com/shuxiachai/returnops-au/pull/17>)): [unlocked report rules](<https://github.com/shuxiachai/returnops-au/blob/a3679456e1df78d6190e03933f2079d29206ceb7/README.md#unlocked-canvas-report-rules-verified-on-september-20>) and [contribution record](<https://github.com/shuxiachai/returnops-au/blob/a3679456e1df78d6190e03933f2079d29206ceb7/docs/reports/member-c-contribution-and-interview.md>), [six-scope F.01 review](<https://github.com/shuxiachai/returnops-au/blob/a3679456e1df78d6190e03933f2079d29206ceb7/docs/reviews/member-c-f01-review-20260920.md>), [PG17 Compose reproduction](<https://github.com/shuxiachai/returnops-au/blob/a3679456e1df78d6190e03933f2079d29206ceb7/docs/reviews/member-c-pg17-reproduction-20260920.md>). Technical execution was AI-assisted under C's authorization; this report cites those records and does not independently repeat the runs or Canvas access.

\[P18\] ReturnOps AU. A-led [model-index and report-navigation draft](<https://github.com/shuxiachai/returnops-au/blob/d26d68aaedfbaded363c7751701a22b201ba3a8d/docs/stage1-model-index.md>) at d26d68aa, [PR 18](<https://github.com/shuxiachai/returnops-au/pull/18>). It is an unmerged preparation artifact for B-owned M-S.03; no change of ownership or completed shared contribution is inferred.

\[P19\] ReturnOps AU. A [notification-fixture correction candidate](<https://github.com/shuxiachai/returnops-au/blob/73e0166383805e1b4cb3a9cf558114d8cf3f4252/docs/reviews/a-notification-fixture-disposition-20260921.md>) at 73e01663, [PR 19](<https://github.com/shuxiachai/returnops-au/pull/19>), following C-F01-20260920-01. Six synthetic snapshots receive consistent customer text; public schemas, saved outcomes and state rules are unchanged. This separate unmerged candidate retains C's designated review and joint-acceptance requirements.

# <a id="_bntzqq9itovk"></a>14 Model figures

<a id="c7ki4yqx189b"></a>

**Figure 1  Stakeholder requirements and their design consequences**

![Embedded report image](assets/figure-01.png)

Source: requirements-map.puml \| report discussion candidate

<a id="9na5boaialtk"></a>

**Figure 2  Mandatory capabilities and product family options**

![Embedded report image](assets/figure-02.png)

Source: feature-overview.puml \| report discussion candidate

<a id="pepro98kty7x"></a>

**Figure 3  Overall use case model with human and external actors**

![Embedded report image](assets/figure-03.png)

Source: use-case-overview.puml \| report discussion candidate

<a id="4ela4qpnujhf"></a>

**Figure 4  Shared package responsibilities**

![Embedded report image](assets/figure-04.png)

Source: package-dependencies.puml \| report discussion candidate

<a id="s615ajmpz53u"></a>

**Figure 5  Core case and evidence classes**

![Embedded report image](assets/figure-05.png)

Source: domain-records.puml \| report discussion candidate

<a id="ijxbxjks2oqf"></a>

**Figure 6  Decision and execution record relationships**

![Embedded report image](assets/figure-06.png)

Source: v0.3 Figure 6, based on \[P6, P7, P10\]; AI-assisted reconstruction, 21 Sep 2026. Naming/mapping clarification only.

<a id="rlvg4gylu6r4"></a>

**Figure 7  Approval and service interfaces**

![Embedded report image](assets/figure-07.png)

Source: domain-services.puml \| report discussion candidate

<a id="k3gl7y2tpnn1"></a>

**Figure 8  Analysis classes, typed ports and AI role responsibilities**

![Embedded report image](assets/figure-08.png)

Source: domain-analysis.puml \| report discussion candidate

<a id="7tu4fcoddh47"></a>

**Figure 9  Runtime parts and ports of the governed case system**

![Embedded report image](assets/figure-09.png)

Source: governed-case-composite.puml \| report discussion candidate

<a id="b91m03xhe4bo"></a>

**Figure 10  Analysis collaboration with independent Risk**

![Embedded report image](assets/figure-10.png)

Source: governed-analysis-composite.puml \| report discussion candidate

<a id="w2e8swrr131b"></a>

**Figure 11  Execution collaboration with approvals and audit**

![Embedded report image](assets/figure-11.png)

Source: governed-execution-composite.puml \| report discussion candidate

<a id="xllaw9m8qlsx"></a>

**Figure 12  Proposed local deployment and trust boundaries**

![Embedded report image](assets/figure-12.png)

Source: deployment-topology.puml \| report discussion candidate

<a id="5cmh8j5fbczt"></a>

**Figure 13  A activity for governed execution and outcome notification**

![Embedded report image](assets/figure-13.png)

Source: governed-execution-activity.puml \| report discussion candidate

<a id="5vqmlb2gq640"></a>

**Figure 14  A interaction for exact scope approval and dispatch**

![Embedded report image](assets/figure-14.png)

Source: exact-scope-sequence.puml \| report discussion candidate

<a id="dkvrqlqj8lky"></a>

**Figure 15  A interaction for recovery and notification**

![Embedded report image](assets/figure-15.png)

Source: recovery-notification-sequence.puml \| report discussion candidate

<a id="9bmil9zcr6vt"></a>

**Figure 16  A OperationAttempt state machine**

![Embedded report image](assets/figure-16.png)

Source: operation-attempt-state.puml \| report discussion candidate

<a id="9rlzgp8ypdk9"></a>

**Figure 17**  **MB-ACT-0.2 — One intake traversal: admission prefix and one processing invocation.**

![Embedded report image](assets/figure-17.png)

Source: member-b-activity-report.puml \| report adaptation of B MB-0.2 \[P14\].

Admission prefixes exclude the processing ref; stops end this traversal, not the durable session.

<a id="2wco8e7ki64s"></a>

**Figure 18**  **MB-SEQ-0.2a — sd CustomerIntake; only fresh acceptance invokes processing.**

![Embedded report image](assets/figure-18.png)

Source: member-b-sequence-admission-report.puml \| report adaptation of B MB-0.2 \[P14\].

G-A/R1/R2 and complete admission/replay guards are defined in Section 7.

<a id="g8ggbkj0bxq9"></a>

**Figure 19**  **MB-SEQ-0.2b — Independent sd ProcessAcceptedIntake; accepted work only.**

![Embedded report image](assets/figure-19.png)

Source: member-b-sequence-processing-report.puml \| independent interaction view \[P14\].

<a id="caaa9cna8q2c"></a>

**Figure 20**  **MB-STM-0.2 — Durable IntakeSession, quiescent states and guarded re-entry.**

![Embedded report image](assets/figure-20.png)

Source: member-b-state-report.puml \| durable IntakeSession report view \[P14\].

<a id="yob7ra45allo"></a>

**Figure 21A  C activity: complete-input validation and bounded recovery**

![Embedded report image](assets/figure-21.png)

Source: C model chain \[P12\]; AI-assisted control-flow clarification, 21 Sep 2026. Continue with Figure 21B.

**Figure 21B C activity: routing the five accepted business outcomes**

![Embedded report image](assets/figure-22.png)

Source: C model chain and revision bound \[P12, P13\]; AI-assisted control-flow clarification, 21 Sep 2026. Candidate design, not runtime or personal acceptance.

<a id="pl3vpuim0rgt"></a>

**Figure 22  C interaction: accepted evidence and an independent reviewer**

![Embedded report image](assets/figure-23.png)

Source: member-c-sequence-report.puml \| C-published discussion view \[P12\]

<a id="n7wv812z15mp"></a>

**Figure 23  C state model: review acceptance, failure and historical validity**

![Embedded report image](assets/figure-24.png)

Source: member-c-state-report.puml \| C-published discussion view \[P12\]

**Figure 24  C object snapshot: source conflict before the Founder decision**

![Embedded report image](assets/figure-25.png)

Source: member-c-object-conflict.puml \| synthetic design snapshot \[P12, P13\]

# <a id="_2yt60knmpb6r"></a>Appendix A Review and provenance notes

## <a id="_r66cx977yuo1"></a>Technical reference and report provenance

The technical reference is the rc.5 review tree at commit 64582a3007fea0fa3d1b1c3c212168b96af6b607, available through PR 11 \[P1\]. The original v0.1 report was prepared after that commit; current B report views derive from the published compatibility correction \[P14\], and current C-published figure sources are identified in \[P12\]. They are not included in its CI runs, rc.5 publication hash manifest or existing PR; their source and render checks must be reported separately.

## <a id="_3gnbmrpghkmo"></a>Meaning of preparation evidence

The original discussion candidates were prepared under the lead's direction; current B originals and A/AI-assisted corrections are distinguished in \[P14\], and C-published report views are attributed in \[P12\]. Their existence does not establish member approval, completed implementation or independent assessment completion. A's model syntax checks do not establish runtime safety. Publication, green checks, model syntax and personal authorship are distinct facts. Actual contribution and review records remain necessary. The unit outline permits AI with acknowledgement \[C4\]; the dated Canvas task-page verification is recorded below, while final announcements and the assigned interview slot remain to be checked. Permitted assistance does not establish independent authorship or satisfy the rubric's individual and shared-contribution conditions by itself.

## <a id="_mx64xf2lsihc"></a>Recorded rc.5 checks

At the Sep 7, 2026 review snapshot, PR 11 contained source head 64582a3. Both push and PR CI runs succeeded \[P8\]. Each reported 56 contract checks, six static checking groups, 12 model-checker regressions, five runner regressions, 15 Mermaid parses and 32 environment/API/PostgreSQL tests, including four database tests. The PR workflow checked a synthetic merge commit; the push workflow checked the source head. These are implementation-preparation checks, not business-runtime, benchmark or team-acceptance evidence.

## <a id="_5u8g3lf76q4b"></a>C follow-up evidence and limits

C supplied MC-0.1.1/MC-RPT-0.2 at 32c704f \[P10\]. The earlier integration verified C’s saved evidence/logs and source correspondence: 58 contract tests against reconstructed source and a 15-case binding/coverage matrix for the published A correction at 3dd1ff6. It is not a fresh clean-Git run and does not implement Domain/history services, prove claim support or prompt independence, or replace C’s clean Git/PG17 Compose reproduction, personal explanation, A’s personal confirmation or joint acceptance. Later exact-source technical evidence is separately recorded in \[P17\].

B formally approved the exact A source at 3dd1ff6 for five consumer-boundary items \[P11\]. This does not establish joint F.01 acceptance; B's personal chain has been delivered and compatibility-corrected \[P14\]; later shared candidates and index have a separately sourced correction \[P15\]; personal explanation and final shared acceptance remain outstanding.

## <a id="_728afrn3vrzg"></a>Team-managed production and report scope

Video production and timing are managed directly by the team, outside this report-editing work. This document sets no recording booking or production task. The remaining written-submission work is accurate contribution attribution, unresolved-design disclosure and the required course checks.

## <a id="_36hh67q40p90"></a>Recorded assessment details and remaining checks — updated 21 September 2026

On Sep 8, 2026, the Canvas-hosted two-page rubric was rechecked and matched the local copy: 15 report points, five video points and ten interview points \[C1\]. The report assignment still displayed 25 possible points, a deadline of Oct 4, 2026 at 23:59, and unlocking on Sep 20, 2026 at 00:00; its task instructions remained locked \[P9\]. C's later signed-in page record \[P17\] resolves the grouping: report 15 plus individual interview 10. One designated member submits one group PDF. It records the same due date/time, without a displayed timezone, and requires accurate acknowledgement of assistance and retention of submitted work, drafts, AI outputs and research materials for one year. This report cites that record rather than claiming independent Canvas access. The 21 September signed-in recheck \[C5, C6\] confirms PDF report upload, one designated group submitter, a separate video item, and the same 4 October 23:59 deadline. Both pages allow unlimited attempts and remain available until 11 October; that availability end is not an extension. The video must be uploaded to Canvas, with a YouTube link only as an optional supplement. The Project Description \[C2\] calls for slides covering requirements/classification, design rationale including rejected alternatives, models, and change/acceptance criteria; no separate PPTX upload requirement was found. Interviews are in practical sessions in Weeks 11–12 \[C1\]; verify the assigned slot, submitting-account timezone and any new announcements. The same dated record specifies a video of at most eight minutes (5 points), uploaded to Canvas; a YouTube link is supplementary. The team manages that production and submission separately, and this report makes no completion claim. The official unit outline permits AI in Project Stage 1 and requires acknowledgement, while directing students to Canvas for task-specific instructions \[C4\]. This report claims neither submission nor tutor acceptance.

## <a id="_sld8js1ht2lk"></a>Planning-record interpretation and navigation

The 89 WBS entries are acceptance checks, not an instruction to create 89 separate cards. F.01 is mapped to [KAN-32](<https://lucastaooo.atlassian.net/browse/KAN-32>) and F.02 to [KAN-33](<https://lucastaooo.atlassian.net/browse/KAN-33>), both linked to PR 11. C's dated update \[P17\] records In Review; this report does not re-audit the live board. Technical reproduction is recorded in \[P17\]; joint F.01/F.02 acceptance remains outstanding.

## <a id="_hnh27r8g0zy2"></a>Sources for the 21 September update

\[C5\] ELEC5620 Canvas. *Stage One Report Submission*. Course 74323, assignment 695832. Inspected 21 September 2026.[ ](<https://canvas.sydney.edu.au/courses/74323/assignments/695832>)[Official report assignment](<https://canvas.sydney.edu.au/courses/74323/assignments/695832>).

\[C6\] ELEC5620 Canvas. *Stage One Video Presentation Submission*. Course 74323, assignment 695833. Inspected 21 September 2026.[ ](<https://canvas.sydney.edu.au/courses/74323/assignments/695833>)[Official video assignment](<https://canvas.sydney.edu.au/courses/74323/assignments/695833>).

21 September 2026 editing record: C authorised AI-assisted clarification of class/DTO naming, C activity control-flow presentation, open-decision responsibilities and current assessment-page observations. Source attribution and pending personal/shared contribution confirmation remain intact. This edit does not constitute team acceptance, business implementation, a completed video or assessment submission.

**Video rehearsal materials**

Shared on 21 September 2026 for team review and rehearsal. These files accompany the report; they are not a completed video or a Canvas submission.

[ReturnOps Stage 1 Video PPT](<https://docs.google.com/presentation/d/1oE-d_TP1XjoBB7gYHby2aZRRSqM9tBBB/edit?usp=drive_link&rtpof=true&sd=true>): nine editable slides with speaker notes.

[ReturnOps Stage 1 ABC Script](<https://docs.google.com/document/d/1wum-DFCBYcmXA8seB770K_n2R4qxWb7t/edit?usp=drive_link&rtpof=true&sd=true>): English narration, Chinese comprehension prompts, timing and visual cues.

Both files are in the[ ](<https://drive.google.com/drive/folders/1bAjQFmkBl-zXthEj2G8a4MybvuaGkfMS>)[2026S2 ELEC5620 shared folder](<https://drive.google.com/drive/folders/1bAjQFmkBl-zXthEj2G8a4MybvuaGkfMS>). A versioned copy is provided through[ ](<https://github.com/shuxiachai/returnops-au/pull/20>)[GitHub PR 20](<https://github.com/shuxiachai/returnops-au/pull/20>), published for review and not merged into main at this dated update.

Proposed speaking allocation: A covers slides 1, 3 and 7; B covers slides 2, 4 and 5; C covers slides 6 and 8. A and C share slide 9. The script plans approximately 7 minutes 30 seconds. Each member should rehearse and verify the explanation, then check the actual final recording remains within eight minutes.

The materials were prepared with AI assistance. Personal understanding, actual contribution confirmation, joint acceptance, recording and formal submission remain separate team responsibilities. The final video must be uploaded to Canvas; these presentation-file links do not replace that upload.
