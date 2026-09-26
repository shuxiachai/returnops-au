# Stage 1 Video Presentation — Script, Storyboard and Slide Outline (`VID-1`)

> **Deliverable type**: Stage 1 group video presentation script and storyboard (`VID-1`)
>
> **Project Specification**: ELEC5620 Model-Based Software Engineering, Stage 1 — Video Presentation, **5 marks**, hard limit **8 minutes** (Hard Rule `H7`)
>
> **Status — 2026-09-21**: Candidate script published under Task T16. **Not yet rehearsed against a clock; not yet reviewed by Members A and C.** See §7.
>
> **Contribution Statement (Hard Rules `H5` & `H11`)**:
> - **Member B (Chengsi Li — Primary Author, drafting)**: Compiled the time and word budget, the storyboard, the slide outline, and the first draft of all six spoken segments from the team's merged Stage 1 documents; authored and delivers segment S1 (context), S2 (requirements classification) and S6 (close).
> - **Member A (Jingbo Chai — Segment Owner & Secondary Reviewer)**: Owns and delivers segment S3 (design, rationale, discarded choices) and S4a (requirements, use case and structure models). **Must revise the draft wording into his own before recording** — the interview marks each member on his own explanation.
> - **Member C (Lucas Tao — Segment Owner & Secondary Reviewer)**: Owns and delivers segment S4b (architecture views and individual chains) and S5 (change assessment and acceptance determination). **Must revise the draft wording into his own before recording.**
>
> *Planned project effort split remains 45% (Member A) / 27% (Member B) / 28% (Member C) per [`docs/07-frozen-work-allocation.md`](07-frozen-work-allocation.md). All three members speak on camera, satisfying `H11` for this group task.*
>
> **Source baseline — every factual claim in the script traces to a merged document, and no new facts are introduced here.** Primary sources: [Stage 1 Team Report](reports/stage-1-team-report.md) §1–§8, §10, §14, §15; [System Design](02-system-design.md) §8, §10; [Requirements and Backlog](04-requirements-and-backlog.md); [Desk-Research Evidence Register](06-requirements-desk-research-evidence.md) (`EVD-001`, `CP-009`); [Course Assessment Requirements](19-course-assessment-requirements.md) §5.
>
> **§5 is checked against the course material itself**, quoted verbatim — the marking criteria sheet, the Project Description and Tutorial 1 — rather than against any internal summary of them.

---

## 1. The constraint, and how the budget was derived

The criteria state a **maximum of 8 minutes**. Over-length is the one failure mode the criteria
name as a hard limit, so the script is budgeted to land at **7:35**, leaving 25 seconds of headroom.

| Parameter | Value | Why |
|---|---|---|
| Hard limit | 8:00 | `H7`, Project Description and criteria sheet |
| **Scripted words** | **990** | Counted from §3 of this file by script, not estimated — see the counting rule below. Per-segment counts are in the segment headings |
| Assumed delivery rate | **135 words per minute** | Conservative for technical content delivered by non-native English speakers. A confident native rate is 150–160 wpm; assuming that rate and then speaking slower is how groups overrun |
| Speech time at 135 wpm | **7:20** | 990 ÷ 135 = 440 s exactly |
| Pauses between segments | **+15 s** | **Three speaker hand-offs** (B→A, A→C, C→B) at 3 s, plus three same-speaker segment breaks at 2 s. This is an assumption, not a measurement. An earlier draft counted six hand-offs; there are only three, because S1→S2, S3→S4a and S4b→S5 do not change speaker |
| **Projected running time** | **7:35** | 25 s headroom; a video at 8:05 loses marks a video at 7:35 cannot |

**The counting rule, so that a re-count agrees with this table.** Count the blockquote text of each
§3 segment. Delete `*` and backticks rather than replacing them with spaces — replacing them turns
`**Coordinator**,` into two tokens and silently inflates the count. Treat em and en dashes as
separators and hyphenated compounds as single words. Count the `⟨group identifier⟩` placeholder in
S1 as **6** words, which is roughly what "Group Twelve, Thursday two p.m." costs to say.
*(An earlier draft of this document counted emphasis markers as spaces and the placeholder as 2,
and reported 993 where the rule above gives 990. An independent reviewer caught it. If your
re-count disagrees with a heading, check the rule before changing the heading.)*

**The one number worth remembering: the script fits inside 8:00 at any delivery rate of
128 words per minute or more.** Below that it overruns and §6's cut list must be applied.

*(The exact threshold is 127.7 wpm. Every rate floor in this document is rounded **up**, because
rounding a floor down names a rate at which the video actually overruns — a reviewer found one
floor in §6 rounded the wrong way, where the stated rate produced 8:00.2.)*

> **The rate assumption is the largest risk in this document.** It is an estimate, not a
> measurement. §7's first action is to read the script aloud against a stopwatch and record the
> *actual* rate. At 130 wpm the video runs 7:52 — inside the limit, but with eight seconds spare;
> at 125 wpm it runs 8:11 and must lose 22 words; at 120 wpm it runs 8:30 and must lose 60.
>
> **The second risk is growth, not slowness.** §7 items 3 and 4 require Members A and C to rewrite
> 686 of these 990 words into their own voice. A rewrite that grows 5% breaks the limit just as
> surely as a slow delivery, so those items carry a hard word ceiling.

---

## 2. Storyboard — six segments, three speakers

Cue times below are computed from the counted words at 135 wpm, plus 3 seconds at each speaker
hand-off and 2 seconds at each same-speaker segment break. They are targets to rehearse against,
not a rigid timeline.

| # | Cue in | Words | Speech | Speaker | Required topic | Slides |
|---|---|---:|---:|:---:|---|---|
| **S1** | 0:00 | 100 | 44 s | **B** | Context (criteria sheet: *"introduce your project"*) | 1–2 |
| **S2** | 0:46 | 147 | 65 s | **B** | **Topic 1** — requirements and their classification | 3–4 |
| **S3** | 1:54 | 263 | 117 s | **A** | **Topic 2** — design, rationale and **discarded choices** | 5–7 |
| **S4a** | 3:53 | 130 | 58 s | **A** | **Topic 3** — models, part one | 8–9 |
| **S4b** | 4:54 | 135 | 60 s | **C** | **Topic 3** — models, part two | 10–11 |
| **S5** | 5:56 | 158 | 70 s | **C** | **Topic 4** — **change assessment and acceptance determination** | 12–13 |
| **S6** | 7:09 | 57 | 25 s | **B** | Contribution statement and close (`H5`) | 14 |
| | **ends 7:34** | **990** | **7:20** | | | |

**Speaking time by member** — A 175 s (40%), B 134 s (31%), C 130 s (30%).

**Be careful what this split is claimed to prove.** It is *not* the frozen effort allocation
(45/27/28) and should not be presented as matching it. What it does establish is that all three
members speak, and that no member is a token presence — which is what `H11` asks of a group task.
`H11` is only fully met once §7 items 3 and 4 are done: until then the video's *authorship* is one
member's, whatever the speaking time says.

**Topics 2 and 4 get the most time on purpose.** They are the two items groups routinely drop, and
both are named explicitly in the criteria. Together they take 187 of the 439 seconds of speech.

---

## 3. The script

> **Read this as a draft, not as lines to memorise.** Segments S3, S4a, S4b and S5 are written in
> Member B's voice from the team's merged documents; A and C must rewrite them into their own words
> before recording. A member who recites a sentence he cannot unpack will be asked to unpack it at
> the interview, which is worth twice what this video is.
>
> Numerals are written as they should be **spoken** (`two point four seven`, not `2.47`).

### S1 · Member B · cue 0:00 · 100 words · 44 s

> Hello. We are Group ⟨lab session and group number — blocked on `OQ-002`, see §7⟩, and
> our project is **ReturnOps AU** — a human-governed, multi-agent returns management system for a
> single Australian online retailer.
>
> In the government-commissioned Australian Consumer Survey of twenty twenty-three, businesses
> **self-estimated a mean of two point four seven hours** to handle a typical repair, replacement
> or refund problem. That figure is cross-industry and self-reported, so we use it as motivation
> and measure our own baseline separately. For a solo founder it is a bottleneck, and outcomes end
> up inconsistent.
>
> Our system automates the fact gathering. It deliberately does **not** automate the decision.

*(Source: `EVD-001` in [docs/06-requirements-desk-research-evidence.md](06-requirements-desk-research-evidence.md),
read directly rather than through a summary. **The wording matters.** `EVD-001`'s own limits column
states the figure is cross-industry **end-to-end** problem handling — it is not e-commerce active
handling, not SME-only, and it does not supply the value for `NFR-005`. Change proposal `CP-009`
further requires that manual-handling duration is never presented as established fact. A draft of
this segment said "active manual handling", which overstates the source. Team report §1.1 carried
the same wording and **was corrected in the same change as this script**; both now reproduce
`EVD-001`'s limits rather than paraphrasing past them.)*

### S2 · Member B · cue 0:46 · 147 words · 65 s

> Our requirements are classified in three parts, as the project description requires.
>
> **First, the agreement** — what the system guarantees, and what it excludes. We guarantee
> non-personal audit integrity, preservation of the customer's original statement while it is
> available, non-executable AI output, and an independent risk review with five-outcome routing. We
> exclude three
> things by name: no automated approval of a disputed refund without founder sign-off; no direct
> language-model write access to the database; and no live credit-card chargebacks.
>
> **Second, the mandatory capabilities** — twelve functional requirements across intake,
> assessment, governance and audit; nine non-functional requirements; and twelve business rules.
>
> **Third, the optional features** — each of us owns exactly one.
>
> Underneath all of that sit nineteen ad-hoc requirements written in the user's own words. Mine is
> `AH-01` — *"let me describe the return or product issue without navigating internal systems."*
> Every model we drew descends from one of those nineteen.

*(Source: team report §2.1.1 agreement, §2.1.2 mandatory, §2.1.3 optional. The **nineteen**
`AH-01`–`AH-19` are enumerated in [docs/05-lab-3-requirement-modelling.md](05-lab-3-requirement-modelling.md),
not in team report §2.2, which lists only the three personally-owned ones.)*

### S3 · Member A · cue 1:54 · 263 words · 117 s

> The architecture is a **modular monolith with three differentiated AI roles around a
> deterministic core.**
>
> Three roles: a **Customer Case Coordinator**, a **Returns Assessment Agent**, and a
> **Compliance and Risk Reviewer**, which returns one of five outcomes — pass, pass with warning,
> revise, needs information, or escalate.
>
> By design: no agent writes authoritative state; no agent creates an approval; only a
> deterministic Operations Service performs effects, and only against an exact-scope approval
> granted by the human founder. Design requirements — not yet built, not yet proven.
>
> So what does the language model actually **do**? It reads free text and infers intent, so the
> customer writes in plain language instead of working through administrative dropdowns. It
> drafts the questions that close an evidence gap. It
> synthesises a conditional, cited proposal from passages retrieval has already verified. And in a
> separate invocation it argues against that proposal. Retrieval itself is deterministic keyword
> search — not a fourth agent.
>
> Now the choices we **discarded** — they explain the design better than the design does.
>
> We rejected a seven-agent microservice fleet — disproportionate complexity, token latency, and no
> clear accountability. We rejected unrestricted agents calling each other, for a domain-controlled
> workflow. We rejected free-form language-model actions, for typed tool commands. We rejected
> fully autonomous refunding, for human approval before impact. We rejected production payment and
> logistics access, for mock adapters. We rejected open web search, for a small approved corpus
> with verifiable provenance. And we rejected a client-side delete endpoint, because destroying a
> case record breaks the audit trail.
>
> Every one of those trades capability for accountability. That is the deliberate choice.

*(Source: system design §10.1, §10.2; team report §10.1, §15.3.)*

### S4a · Member A · cue 3:53 · 130 words · 58 s

> Our models. **Requirements first.** A user requirement diagram traces each informal need down
> four tiers — ad-hoc need, use case, formal specification, and governing business rule — and a
> feature diagram decomposes the product into mandatory core features, optional modules, and
> alternative workflow paths.
>
> **Then behaviour scope.** An overall use case diagram in UML two point five, backed by six full
> specifications — from `UC-01`, lodging a return, through `UC-03`, the founder decision gate, to
> `UC-05`, audit.
>
> **Then structure.** The design-time class diagram carries the domain entities, the port
> interfaces and the association semantics. Runtime structure needed three complementary models: a
> **named-instance** object diagram freezing a **synthetic** case at the decision gate, a
> collaboration diagram numbering the messages through the approval guard, and a composite
> structure diagram of the orchestration's parts and connectors.

*(Source: team report §3.1, §3.2, §4.1, §4.2, §5, §6. **Do not call `OBJ-1` a real case.** Team
report §6.1.1 states the snapshot is synthetic and that its contents are "teaching fixtures, not
retrieved legal quotations, a measured run or Gold evidence"; `docs/19-course-assessment-requirements.md`
§3 permits a clearly-labelled synthetic design snapshot precisely so long as it does not pretend to
have run. A draft of this segment said "one real case" and was corrected.)*

### S4b · Member C · cue 4:54 · 135 words · 60 s

> **For architecture we applied Kruchten's four plus one.** The package diagram is the development
> view: twelve packages, every dependency arrow pointing inward, and a domain package with **zero
> outgoing dependencies**. The deployment diagram is the physical view, and it is honest about
> scope — green is deployed and verified today, yellow is planned, blue is both at once, and
> every published port binds to loopback only.
>
> Each of us then drew **our own** behaviour chain from **our own** ad-hoc requirement: an activity
> diagram, an interaction diagram and a state machine. Mine follows a case from a detected source
> conflict through to a safe escalation — my ad-hoc requirement was *"show material source
> conflicts; if they prevent a safe proposal, **stop** and hand the case to me."* These are
> individually authored, and each of us defends his own.

*(Source: team report §7.1, §7.2, §7.3, §8.1, §8.3, §8.4; `AH-08`.)*

### S5 · Member C · cue 5:56 · 158 words · 70 s

> Finally — how we decide whether a **change** is accepted, and whether a **deliverable** is
> acceptable. Two different questions.
>
> Any proposed change to a requirement, an interface or a model is tested against three questions.
> Does it break the version-one REST contract or a wire schema? Does it violate the
> non-authoritative boundary — would it give an agent write access, or let it manufacture an
> approval? And does it preserve traceability back to an approved ad-hoc requirement?
>
> **Acceptance** rests on four documentation checks. They *support* the decision; they do not
> replace the runtime delivery gates in our work packages. The repository's static checks pass. The
> schema validation and contract tests pass green in continuous integration. A static walk-through
> confirms every entity and transition maps to a registered requirement. And a named reviewer **who
> did not author the work** signs it off, with the finding and its disposition recorded against its
> exact source.
>
> Author and reviewer are never the same person.

*(Source: team report §15.1 change assessment, §15.2 acceptance determination. **Not** system
design §7 — that is the in-product Founder decision gate and has nothing to do with either.)*

### S6 · Member B · cue 7:09 · 57 words · 25 s

> Contributions. Forty-five, twenty-seven and twenty-eight per cent across Jingbo, myself and
> Lucas — that is **planned** allocation, not measured authorship, and section fourteen says so.
> The per-model record is in fourteen point two; where we cannot yet evidence a split, it says that
> rather than inventing one.
>
> Thank you. We look forward to your questions at the interview.

*(Source: team report §3.3, §14.1, §14.2.)*

**Scripted total: 990 spoken words → 7:20 of speech at 135 wpm, 7:35 including inter-segment pauses.**
*(Counts are measured from this file, not estimated. The group-identifier placeholder in S1 is counted as the two words it will become.)*

---

## 4. Slide outline — 14 slides

No slide should carry more than the speaker says about it. Every slide below is a title, a diagram,
or at most five short lines.

| # | Slide title | On the slide | Speaker | Segment |
|---:|---|---|:---:|:---:|
| 1 | **ReturnOps AU** | Project name, one-line descriptor, three member names, group identifier | B | S1 |
| 2 | The problem | The `2.47 h` figure with its source, and one line on inconsistent outcomes | B | S1 |
| 3 | Requirement classification | Three boxes — Agreement · Mandatory · Optional. Nothing else | B | S2 |
| 4 | Requirement inventory | `12 FR · 9 NFR · 12 BR · 19 AH · 6 UC`, and the three optional features against member names | B | S2 |
| 5 | Architecture | `ADH-1` / system-design overview — three agents around the deterministic core | A | S3 |
| 6 | The governance rule | Three lines only: *no agent writes state · no agent creates an approval · only Operations executes, under exact-scope approval* | A | S3 |
| 7 | **Discarded choices** | Two-column table, chosen ↔ discarded, seven rows | A | S3 |
| 8 | Requirements and use case models | `URD-1` and `FEAT-1` side by side, `UCD-1` inset | A | S4a |
| 9 | Structure models | `CLS-1` cropped to one aggregate and its ports. Then **one** of `OBJ-1` / `COL-1` / `SC-1`, cropped to the decision gate — name the other two aloud rather than showing them. See the readability note below: these three are on the dense list, and a thumbnail of a dense diagram is the failure that split the old slide 10 | A | S4a |
| 10 | Architecture views | `PKG-1` cropped to the inward-arrow claim, `DEP-1` cropped to the green/yellow legend. Two diagrams, not eleven | C | S4b |
| 11 | The nine individual chains | A 3 × 3 **text** grid: member × (`ACT` / `INT` / `STM`), each cell the model ID and its `AH-*`. No thumbnails | C | S4b |
| 12 | **Change assessment** | The three test questions, written as questions | C | S5 |
| 13 | **Acceptance gates** | The four gates, numbered | C | S5 |
| 14 | Contributions and thanks | `45 / 27 / 28` labelled **planned allocation**, pointer to report §14.2, and one line: *"Generative AI use is acknowledged in report §17"* | B | S6 |

**Slide rate: 14 slides over 7:35 — about 33 seconds each.** Slides 7, 12 and 13 carry the two
most-forgotten topics and should hold for their full segment rather than being split further.

**Why slide 10 was split.** An earlier draft put `PKG-1`, `DEP-1` and nine behaviour-chain
thumbnails on one slide held for 59 seconds. Eleven diagrams in under a minute is not an overview,
it is a flicker, and cropping cannot fix a density problem caused by *count*. Slide 11 now carries
the nine chains as text, which is all the spoken line needs: the marker is being told the chains
exist and who authored each, not asked to read them.

**Slide 14 carries the generative-AI acknowledgement.** The video is its own Canvas submission and
the unit requires AI use to be disclosed (`OQ-001`; report §17 is the statement). A pointer line
costs no spoken words and no marks; its absence is an integrity exposure for the sake of nothing.

**Readability.** Check every embedded diagram at *normal playback scale*, not zoomed in on the
authoring machine. [`docs/19-course-assessment-requirements.md`](19-course-assessment-requirements.md)
§5 states this explicitly: the report is checked at real reading size and the video at normal
playback size, and a diagram that parses or has an SVG is **not** evidence that the finished frame
is legible. `OBJ-1`, `COL-1`, `URD-1` and `PKG-1` are dense; on slides 8–10, crop to the region
being discussed rather than shrinking the whole diagram to fit.

---

## 5. Coverage proof — every required item has a named slide and a named speaker

Checked against the course material itself, not against a summary of it.

- **Marking criteria sheet, Video Presentation (5 Marks), verbatim:** *"Make a video presentation
  within 8 minutes. It should introduce your project and overview the key agent roles, functions,
  use cases and design models. Upload your video to Canvas before deadline and it is recommended
  you also attach a YouTube link to your presentation."*
- **Project Description, item 2, verbatim:** *"Presentation slides should cover the following"* —
  then the four topics. **The four topics are stated as a requirement on the slides**, not only on
  what is said aloud, which is why §4 assigns every topic a named slide as well as a named speaker.
- **Tutorial 1 restates it as a checklist and adds** *"Slides required"* — a deck is mandatory, not
  a presentation aid the group may skip.

Both lists are discharged below.

| Required item | Source | Slide(s) | Speaker | Segment |
|---|---|---|:---:|:---:|
| A deck exists at all (*"Slides required"*) | Tutorial 1 | 1–14, §4 | — | all |
| Introduce the project | Criteria sheet | 1, 2 | B | S1 |
| Key **agent roles** | Criteria sheet | 5 | A | S3 |
| **What the LLM actually does** | Criteria sheet, *"overview the key agent roles"* | 5, 6 | A | S3 |
| Key **functions** | Criteria sheet | 4, 5 | B, A | S2, S3 |
| **Use cases** | Criteria sheet | 8 | A | S4a |
| **Design models** | Criteria sheet | 8, 9, 10, 11 | A, C | S4a, S4b |
| **Topic 1** — requirements **and their classification** | Project Description | 3, 4 | B | S2 |
| **Topic 2** — design, rationale **and discarded choices** | Project Description | 5, 6, **7** | A | S3 |
| **Topic 3** — overview of the models | Project Description | 8, 9, 10, 11 | A, C | S4a, S4b |
| **Topic 4** — **basis for change assessment and acceptance determination** | Project Description | **12, 13** | C | S5 |
| Contribution statement (`H5`) | Hard rule | 14 | B | S6 |
| Generative-AI use disclosed | Unit Outline (`OQ-001`) | 14 | — | S6 |
| Every member participates (`H11`) | Hard rule | — | A, B and C all speak | all |
| **Within** 8 minutes (`H7`) | Criteria sheet | — | projected 7:35 | §1 |
| Uploaded to Canvas before the deadline | Criteria sheet | — | Task T17 | §7 |
| YouTube link — *recommended*, not required | Criteria sheet | — | Task T17 | §7 |

---

## 6. If the rehearsal runs long — cut in this order

Do **not** cut by speaking faster; that is how a recording becomes unlistenable and a marker stops
following. Cut text, in this order, and re-time after each cut.

Savings below are **measured**, not estimated: each row was applied to the current text and the
result re-counted by §1's rule. Floors are rounded up.

| Order | Cut | Words saved | Covers down to | Why it is safe to cut first |
|---:|---|---:|---:|---|
| 1 | S4a — compress the runtime-models sentence to *"three models: a synthetic named-instance object diagram, a collaboration diagram and a composite structure diagram"* | **21** | **126 wpm** | Slide 9 shows them and the report assesses them. **Keep the word "synthetic"** — dropping it is how an earlier draft came to claim a real case |
| 2 | S3 — delete the closing line (*"Every one of those trades capability for accountability…"*) | **13** | **124 wpm** | Rhetorical rather than evidential; the seven discarded choices have already made the point |
| 3 | S6 — reduce the sign-off to *"Thank you."* | **9** | **123 wpm** | Pure courtesy. The contribution statement before it is the part that carries a mark |
| 4 | S4a — drop the use-case IDs, leaving *"six full specifications, from lodging a return to audit"* | **8** | **122 wpm** | Slide 8 carries them. Cut this only after 1–3, because the criteria sheet names use cases explicitly |

All four together recover 51 words and cover a delivery rate down to 122 wpm. Below that, the
script needs rewriting rather than trimming.

**Three things must never be cut.**

1. **S3's discarded-choices list** — Topic 2, named in the criteria, and the item groups drop.
2. **S5 in its entirety** — Topic 4, the other item groups drop.
3. **S3's "so what does the language model actually do" paragraph** — without it every mention of
   the model in this script is a prohibition, and a marker watching all eight minutes never hears
   what the LLM contributes. The criteria sheet asks the video to *"overview the key agent roles"*.

Also never cut the qualifiers that keep claims inside their evidence: "synthetic" in S4a, "design
requirements — not yet built, not yet proven" in S3, "cross-industry and self-reported" in S1, and
"planned allocation, not measured authorship" in S6. They cost about twenty words between them and
they are the difference between a claim that survives the interview and one that does not.

---

## 7. Before recording — open items, in order

| # | Item | Owner | Blocking? | Status |
|---:|---|:---:|:---:|---|
| 1 | **Read the full script aloud against a stopwatch and record the actual words per minute.** Re-budget §1 from the measured rate, not the assumed one | B | **Yes** | ⬜ |
| 2 | **Group identifier for slide 1 and S1** — lab session and Canvas group number | B | **Yes** — a wrong group number on a group submission is a real risk | ⬜ `OQ-002`; Canvas unlocked 20 Sep |
| 3 | **Member A rewrites S3 and S4a into his own words** and confirms he can unpack every claim unprompted. **Hard ceiling: S3 ≤ 263 words, S4a ≤ 130 words**, counted by §1's rule. Re-count before rehearsal | A | **Yes** (`H11`, interview) | ⬜ |
| 4 | **Member C rewrites S4b and S5 into his own words** and confirms the same. **Hard ceiling: S4b ≤ 135 words, S5 ≤ 158 words**, counted by §1's rule. Re-count before rehearsal | C | **Yes** (`H11`, interview) | ⬜ |
| 5 | Confirm any Canvas-side submission constraint on the video (file size, duration enforcement, upload mechanism) once the assignment page is open. **Hosting is already answered** — §5 quotes the criteria sheet: Canvas upload, YouTube link recommended. `OQ-007` is about the **report document's** format and does not cover this | B | No | ⬜ |
| 6 | Build the deck from §4; check every diagram at normal playback scale | B drafts · A, C review | No | ⬜ |
| 7 | Full three-person rehearsal against a clock, with slides | all | **Yes** | ⬜ |
| 8 | **Complete report §14.2's authorship ledger** before submission. S6 points the marker straight at it, and two rows (`FEAT-1/CLS-1/ADH-1` and `UCD-1/OBJ-1/COL-1`) still record what is *needed* rather than who did it | B compiles · A, C supply | Not for recording; **yes for submission** | ⬜ §14.2 is `[PENDING]` |

**Items 3 and 4 are not a formality.** The interview is worth 10 marks, twice this video, and each
member is questioned separately about models he may not have drawn. A segment delivered in the
speaker's own words is preparation for that; a segment read off a page is not.

**The word ceilings on items 3 and 4 are the real schedule risk, not the delivery rate.** Those two
items rewrite 686 of the 990 words — 69% of the script. §1's 25 seconds of headroom survives a
slightly slow reading; it does not survive a rewrite that grows 5%. Count the rewrite before
rehearsing it, not after, **and count it by §1's rule** — a word processor's count will not
agree, because it counts the markdown.

→ Recording and upload are **Task T17**. Upload to Canvas under the current assignment rules;
[`docs/19-course-assessment-requirements.md`](19-course-assessment-requirements.md) §5 records that a
YouTube link is a **rubric suggestion, not a requirement, and does not substitute for the Canvas
submission**. Verify the runtime is ≤ 8:00 **before** uploading, not after.

---

## 8. Interview questions this artefact invites

Each is a question a marker can ask about something the video asserts in one sentence and the
report justifies over a page.

**Every member prepares every question, and the member who *says* the line prepares it first.** The
per-member interview is separately assessed, and recording the video exempts nobody from it
([`docs/19-course-assessment-requirements.md`](19-course-assessment-requirements.md) §5). The
"first" column below is who delivers the claim on camera — that member is the one a marker will
most obviously put the question to.

1. **(A says it — S3.)** *"You said no agent creates an approval. What in the model actually stops one?"* → `BR-012`,
   `NFR-002`, the `ApprovalGuard` in `PKG-1`'s `packages/execution`, and the domain package's zero
   outgoing dependencies.
2. **(A says it — S3.)** *"You discarded the seven-agent design. What would you have gained by keeping
   it, and what would it have cost you?"* → the **cost** is recorded, in team report §15.3:
   disproportionate engineering complexity, excessive API token latency, non-deterministic race
   conditions, and no clear accountability. *(Watch the citations, because they split. Of the seven
   discarded choices in S3, **five** are in system design §10.2 — unrestricted agents, free-form LLM
   actions, autonomous refunding, production provider access, open web search. **Two** are in team
   report §15.3 — the seven-agent fleet and the client-side delete endpoint. §10.2 also has a sixth
   row, "universal customer support", which S3 does not use.)*
   **The gain is written down nowhere, and that is the point of the question** — a marker asking it
   wants to hear that the discarded option had real merit. Member A should work out that answer
   himself before the interview; nothing in this document is a source for it.
3. **(A says it — S3.)** *"Your risk reviewer has five outcomes. Why five, and what happens on the
   fourth one?"* →
   `PASS`, `PASS_WITH_WARNING`, `REVISE`, `NEEDS_INFORMATION`, `ESCALATE`; team report §10.1's
   routing table gives the continuation for each.
4. **(C says it — S5.)** *"Change assessment and acceptance determination — which of those did you
   just describe?"* →
   both, and they are different questions. §15.1 assesses a proposed change; §15.2 determines
   whether a deliverable is acceptable.
5. **(C says it — S4b.)** *"Your deployment diagram has yellow nodes. What is actually running today?"* → the F.02 Docker
   Compose baseline: `api`, `migrate`, `db`, the named volume, and health endpoints only.
6. **(B says it — S6, and it lands on whoever is asked.)** *"Who wrote the slide you are presenting?"* → the contribution ledger in team report §14.2 and
   this document's header answer it per segment. Answer it the same way in the room.
