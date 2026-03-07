# Helly v1 Implementation Plan

## Purpose

This document is the execution plan for bringing the current repository to a fully working Helly v1 product aligned with the master SRS in [helly-v1-srs.md](/Users/vladigolub/Desktop/telegrambot/docs/helly-v1-srs.md).

This file is intended to be used as the primary implementation plan for future coding tasks. Future tasks should reference this document before making runtime changes.

## Planning Principles

- Do not replace the entire project.
- Reuse working infrastructure where it is still compatible with the target product.
- Move from sidecar architecture to canonical ownership gradually.
- Keep production behavior stable while replacing legacy internals.
- Do not delete legacy code until its replacement is implemented, verified, and enabled.
- Treat DB schema, state machine, queues, prompts, and lifecycle ownership as first-class migration workstreams.
- Prefer additive migration, then cutover, then cleanup.

## Current Baseline

The current repository already contains:

- a working Telegram bot runtime in Node.js + TypeScript
- state-machine discipline and transition rules
- partial typed action routing and gatekeeper infrastructure
- partial canonical lifecycle modeling for match and interview domains
- candidate and manager onboarding flows in legacy runtime form
- a hybrid matching engine foundation
- admin and diagnostics tooling

The main gaps relative to the SRS are:

- current runtime flow still exposes jobs/matches too early
- interview flow is not yet owned as a post-match vacancy-specific stage
- manager review happens too early
- one-manager-many-vacancies is not properly modeled
- candidate video verification is missing
- message/media ingestion is incomplete for all required modalities
- queue/workers are not yet the real owner of heavy async jobs
- persistence is not yet fully DB-first
- prompts are fragmented and need systematic rewrite
- legacy code still contains product-flow drift and dead vocabulary

## Definition of Done

The project is considered fully implemented when all of the following are true:

1. Candidate flow follows the SRS from start to READY, including video verification.
2. Hiring manager flow supports multiple vacancies per manager and reaches OPEN state correctly.
3. Matching is controlled by hard filters, embeddings, deterministic scoring, and reranking.
4. Candidates do not manually browse jobs in the primary product flow.
5. Interview invitations are sent in waves.
6. Interview happens after match invitation and before manager review.
7. Manager only sees candidate package after interview and evaluation are complete.
8. Candidate and vacancy deletion flows exist with confirmation and correct side effects.
9. All heavy AI/media/matching operations run through queues/workers.
10. DB schema contains all required entities and canonical lifecycle fields.
11. Raw Telegram messages and uploaded media references are stored.
12. Prompts are versioned, rewritten, and mapped to explicit product stages.
13. Legacy runtime paths that conflict with the SRS are either removed or isolated behind deprecated compatibility layers.

## Workstream Overview

This implementation plan is divided into the following workstreams:

1. Product flow correction
2. Data model and DB schema completion
3. Telegram/media ingestion completion
4. LLM prompt and parsing rewrite
5. Queue and worker ownership
6. Matching and interview orchestration correction
7. Manager review and exposure correction
8. Deletion and lifecycle cleanup
9. Legacy removal and final cutover
10. Verification, QA, and production hardening
11. AI engineering adoption items from external reference research

## Phase 0. Freeze the Target and Protect the Migration

### Goal

Lock the target architecture, establish migration guardrails, and make sure further changes are SRS-driven.

### Tasks

#### P0.1 Adopt the SRS as the master product contract

- Use [helly-v1-srs.md](/Users/vladigolub/Desktop/telegrambot/docs/helly-v1-srs.md) as the source of truth for product requirements.
- Use [helly-target-architecture.md](/Users/vladigolub/Desktop/telegrambot/docs/helly-target-architecture.md) as the target module map.
- Use this document as the execution order reference.

#### P0.2 Preserve current regression coverage

- Keep and extend existing characterization tests.
- Add missing black-box tests for any critical path touched later.
- Ensure each refactor phase starts with a test gap review.

#### P0.3 Establish a deletion policy for legacy code

- No legacy runtime code is deleted before replacement exists.
- Every future deletion must reference the replacement owner and the tests that cover it.
- Mark drifted statuses, helper methods, and branches as deprecated before removal.

### Exit Criteria

- Planning docs exist and are internally aligned.
- Existing characterization and unit tests remain green.
- Legacy cleanup is governed by replacement-first rules.

## Phase 1. Complete the Domain and Database Foundations

### Goal

Make the database and domain model compatible with the SRS before deeper runtime cutover.

### Task Group 1A. Entity Model Completion

#### P1.1 Define the final v1 entity inventory

Required entities:

- User
- CandidateProfile
- CandidateVerification
- Vacancy
- VacancyProfile
- Match
- InterviewSession
- InterviewAnswer
- EvaluationResult
- File
- RawMessage
- StateTransitionLog

#### P1.2 Map current persistence to target entities

For each current repository/table/file-backed store:

- identify the current owner
- identify whether it is canonical or legacy
- identify missing fields
- identify conflicting ownership

#### P1.3 Create a DB schema inventory document

Create a schema checklist covering:

- current tables
- current columns
- missing tables
- missing columns
- legacy columns to deprecate later
- indexes required for matching, vacancies, interviews, and admin reporting

This can be added as a future doc or migration checklist when implementation starts.

### Task Group 1B. Mandatory DB Schema Additions

#### P1.4 Add true vacancy ownership and multi-vacancy support

Current blocker:

- manager appears to be modeled as a single active job owner

Target:

- one manager can own many vacancies
- vacancy becomes the first-class unit for matching, interview invitation, and manager review

Required schema expectations:

- stable `vacancy_id`
- `manager_user_id`
- vacancy lifecycle fields
- canonical status fields
- vacancy metadata fields from the SRS

#### P1.5 Add raw message persistence

Required table/fields:

- raw Telegram payload
- parsed message type
- sender
- chat
- update id
- message id
- timestamps
- linked user/profile/vacancy/match/interview identifiers when known

#### P1.6 Add canonical lifecycle persistence where missing

Ensure DB storage exists for:

- `canonical_match_status`
- `canonical_interview_status`
- later `canonical_evaluation_status` if needed

#### P1.7 Add candidate verification storage

Required fields:

- verification media file reference
- phrase issued
- phrase match result or review status
- verification timestamp
- verification state

#### P1.8 Add interview wave support

Required fields/tables may include:

- invitation wave number
- invitation sent timestamp
- invitation status
- per-vacancy wave counters
- interview invite throttling metadata

### Exit Criteria

- DB schema fully supports SRS entities and flows.
- No required product concept depends only on JSON/local file state.
- Multi-vacancy is structurally possible.

## Phase 2. Finalize the Canonical State and Flow Model

### Goal

Make the target state machine align with the SRS instead of current legacy product flow.

### Tasks

#### P2.1 Audit all runtime states against the SRS

Produce a state inventory:

- current state name
- current meaning
- target meaning
- keep/adapt/remove decision

#### P2.2 Finalize canonical conversational stages

Target stage groups:

- shared start and identity
- candidate CV intake
- candidate summary review
- candidate mandatory questionnaire
- candidate video verification
- candidate ready
- manager JD intake
- manager JD review
- manager mandatory questionnaire
- vacancy open
- match invitation
- interview invitation
- interview answer flow
- evaluation completed
- manager review
- contact introduction
- deletion flows

#### P2.3 Separate pre-profile questioning from post-match interview

This is a major product correction.

Target:

- onboarding questions remain onboarding
- post-match interview becomes vacancy-specific
- interview invitation becomes a distinct runtime state

#### P2.4 Define legal transitions and gate ownership

State transitions must be owned by:

- state engine
- deterministic services

Not by:

- free-form LLM outputs
- ad hoc router branches

### Exit Criteria

- Target conversational flow is explicitly modeled.
- Post-match interview is structurally separated from onboarding.
- Runtime stages can be resolved deterministically.

## Phase 3. Complete Telegram and Media Input Coverage

### Goal

Support every required input modality in the SRS with proper persistence and normalization.

### Tasks

#### P3.1 Extend normalized Telegram update model

Support and persist:

- text
- document
- voice
- video message
- video note
- contact
- location

#### P3.2 Create unified media intake contracts

Each media submission should produce:

- raw message record
- file record
- storage reference
- processing status
- normalized artifact reference

#### P3.3 Implement candidate video verification intake

Flow requirements:

- issue unique phrase
- collect video
- store media
- attach to candidate verification entity
- expose later in manager package

#### P3.4 Ensure all media flows are idempotent

Duplicate updates and retried media processing must not corrupt state or duplicate artifacts.

### Exit Criteria

- All SRS-required input types are supported.
- Candidate verification media is collected and stored.
- Raw input persistence exists for all message types.

## Phase 4. Rewrite and Organize LLM Prompts

### Goal

Create a complete, explicit prompt inventory aligned to product stages and domain responsibilities.

### Prompt Principles

- Prompts must not own state transitions.
- Prompts must be stage-specific.
- Prompts must return structured outputs where possible.
- Prompts must be versionable and testable.
- Prompt rewrite must be tied to evaluation datasets.

### Required Prompt Families

#### P4.1 Routing and intent prompts

- typed action router prompt
- fallback intent parsing prompts if needed

#### P4.2 Candidate onboarding prompts

- CV extraction
- CV summarization
- summary edit merge
- salary extraction
- location extraction
- work format extraction
- follow-up question generation for incomplete answers

#### P4.3 Candidate verification prompts

- phrase issuance template
- optional verification assessment prompt if automated review is used

#### P4.4 Manager vacancy prompts

- JD extraction
- JD summary generation
- inconsistency detection
- budget extraction
- country extraction
- work format extraction
- project/team/stack extraction

#### P4.5 Matching prompts

- reranking prompt
- candidate-vacancy relevance explanation prompt

#### P4.6 Interview prompts

- interview question generation
- follow-up generation
- answer parsing
- interview completion summary

#### P4.7 Evaluation prompts

- final evaluation
- strengths
- risks
- recommendation
- threshold-ready structured output

#### P4.8 Manager package prompts

- candidate package summary
- manager-facing candidate explanation

### Task Sequence

#### P4.9 Build a prompt inventory document or directory map

Track for each prompt:

- owner module
- purpose
- input contract
- output contract
- evaluation dataset
- version

#### P4.10 Rewrite prompts one family at a time

The user may provide new prompts or references when each family is implemented.

#### P4.11 Add prompt regression tests

At minimum for:

- action routing
- CV/JD extraction
- mandatory answer parsing
- interview evaluation

### Exit Criteria

- Every LLM task has an explicit owner prompt.
- Prompt set is complete for SRS flows.
- Prompts are no longer scattered as opaque legacy logic.

## Phase 4A. AI Engineering Adoption Items

### Goal

Explicitly incorporate the useful implementation patterns identified from the external reference repository:

- [ai-engineering-hub](https://github.com/patchy631/ai-engineering-hub)

This phase does not mean copying external demo code into the Helly runtime. It means extracting the useful engineering patterns and applying them to the Helly architecture where they fit.

### Adoption Rules

- Use external projects as pattern references, not as the Helly runtime backbone.
- Do not replace the Node.js/TypeScript Telegram runtime with Python demos.
- Do not introduce multi-agent orchestration as the owner of Helly product flow.
- Do not introduce MCP-heavy runtime architecture into the core candidate/manager path.
- Only adopt patterns that improve Helly subsystems directly.

### Adoption Areas

#### P4A.1 LLM eval and observability framework

Inspired by:

- `eval-and-observability`
- `code-model-comparison`

Implementation targets:

- unified trace envelope for every important LLM call
- prompt/model version tagging
- evaluation datasets for structured tasks
- regression harness for prompt changes
- model comparison workflow where prompt/model changes are risky

Helly subsystems that must use this:

- action routing
- CV parsing and summarization
- JD parsing and summarization
- mandatory answer parsing
- interview question generation
- interview evaluation
- manager package generation

#### P4A.2 Document ingestion benchmark and fallback chain

Inspired by:

- `groundX-doc-pipeline`
- `rag-with-dockling`
- `document-chat-rag`

Implementation targets:

- benchmark current CV/JD extraction quality
- compare parser approaches for PDF, DOCX, and messy inputs
- choose a final extraction fallback chain
- normalize extracted artifacts for downstream LLM prompts

Expected final chain should be explicitly designed, for example:

- native text extraction
- enhanced parser path
- OCR fallback if required
- structured extraction prompt

#### P4A.3 Voice artifact pipeline

Inspired by:

- `audio-analysis-toolkit`
- `rag-voice-agent`
- selected media-processing ideas from `real-time-voicebot`

Implementation targets:

- transcript as a first-class persisted artifact
- separation of media storage and transcript storage
- separation of transcription and structured answer parsing
- quality checks for low-confidence audio inputs
- queue-based voice processing

This is relevant for:

- candidate CV voice intake
- manager JD voice intake
- mandatory answers
- interview answers

#### P4A.4 Context assembly layer

Inspired by:

- `context-engineering-pipeline`

Implementation targets:

- explicit context builder for LLM-heavy operations
- source priority rules
- token-budget-aware context assembly
- separation of short-term conversation context, profile memory, retrieved artifacts, and system constraints

Helly subsystems that should eventually use this:

- candidate summary generation
- JD review generation
- interview follow-up generation
- interview evaluation
- manager review package generation

#### P4A.5 Prompt governance and versioning discipline

Inspired by:

- `guidelines-vs-traditional-prompt`
- selected prompt-architecture patterns from `parlant-conversational-agent`

Implementation targets:

- split prompts by stage and responsibility
- avoid giant monolithic prompts
- define structured output contracts per prompt
- define fallback behavior per prompt
- version prompts and tie them to eval datasets

### Exit Criteria

- Useful external AI engineering patterns are explicitly represented in Helly implementation tasks.
- No important adoption area remains implicit or forgotten.
- External references influence Helly subsystem design without replacing Helly core architecture.

## Phase 5. Make Queues and Workers the Owner of Heavy Processing

### Goal

Move heavy processing out of synchronous runtime branches.

### Required Jobs

- CV analysis
- JD analysis
- transcription
- matching
- reranking
- interview generation
- final evaluation
- reminders
- deletion cleanup
- verification processing if needed

### Tasks

#### P5.1 Implement real queue infrastructure

Replace placeholder queue/worker modules with:

- enqueue contracts
- job payload contracts
- retry policy
- dead-letter/failure strategy
- worker bootstrapping

#### P5.2 Move CV processing to workers

#### P5.3 Move JD processing to workers

#### P5.4 Move transcription to workers

#### P5.5 Move matching runs to workers

#### P5.6 Move evaluation generation to workers

#### P5.7 Add reminder workers

Reminder use cases:

- incomplete onboarding
- pending interview invitation
- incomplete interview
- manager review waiting too long

### Exit Criteria

- Heavy LLM/media/matching operations are queue-owned.
- Telegram runtime remains responsive.
- Async job retries and failures are observable.

## Phase 6. Correct the Candidate and Manager Product Flows

### Goal

Bring onboarding flows into exact SRS compliance.

### Candidate Flow Tasks

#### P6.1 Finish typed routing integration for all onboarding stages

Ensure typed routing covers:

- contact
- role
- CV intake
- summary review
- mandatory questionnaire
- verification
- onboarding decisions where needed

#### P6.2 Enforce candidate onboarding ordering

Target order:

1. contact
2. role
3. CV
4. summary review
5. mandatory answers
6. video verification
7. READY

#### P6.3 Add incomplete answer follow-up discipline

- max one follow-up per main question
- no follow-up to follow-up

#### P6.4 Remove candidate manual browse flow from primary UX

Candidate must not manually browse jobs in the SRS product flow.

Legacy commands may be:

- deprecated first
- hidden from primary UX
- removed only after controlled interview invitation flow is live

### Manager Flow Tasks

#### P6.5 Convert manager job model to vacancy model

- manager can create multiple vacancies
- each vacancy has its own lifecycle
- each vacancy owns its own matching/interview waves

#### P6.6 Enforce manager vacancy creation ordering

Target order:

1. contact
2. role
3. JD input
4. JD review
5. mandatory clarification questions
6. vacancy OPEN

#### P6.7 Add manager vacancy deletion flow

- confirmation required
- vacancy-scoped cancellation effects

### Exit Criteria

- Candidate and manager onboarding both match the SRS.
- Candidate READY and vacancy OPEN are canonical readiness states.
- Multi-vacancy manager behavior works.

## Phase 7. Rebuild Matching, Invitation, and Interview Flow Around the SRS

### Goal

Correct the core product flow from matching through manager review.

### Tasks

#### P7.1 Make vacancy the matching unit

Matching should run against vacancies, not a manager singleton profile.

#### P7.2 Keep the hybrid matching pipeline but formalize stage ownership

Stages:

1. hard filters
2. embedding retrieval
3. deterministic scoring
4. LLM reranking

For each stage define:

- inputs
- outputs
- persistence artifacts
- cutoff thresholds

#### P7.3 Introduce explicit interview invitation flow

Target:

- candidate is invited to interview for a matched vacancy
- candidate can accept or skip
- invitation is tracked independently from later interview completion

#### P7.4 Move interview to post-match runtime ownership

This is one of the main cutover tasks.

Target:

- interview only starts after invitation acceptance
- interview is vacancy-specific
- interview session belongs to candidate + vacancy + match

#### P7.5 Implement interview waves

Need logic for:

- wave size
- completion thresholds
- next-wave triggers
- invite throttling
- preventing too many active concurrent interview invitations

#### P7.6 Enforce one active interview per candidate

This invariant must be enforced at runtime and preferably at the persistence layer where possible.

#### P7.7 Ensure weak candidates are filtered before manager review

Manager receives candidate only after:

- interview completed
- evaluation completed
- candidate passes threshold

### Exit Criteria

- Match invitation and interview are distinct lifecycle stages.
- Interview becomes post-match as required by the SRS.
- Waves work and manager does not see pre-interview candidates.

## Phase 8. Correct Manager Exposure and Review

### Goal

Make manager exposure happen at the right time and from a single canonical seam.

### Tasks

#### P8.1 Make ManagerExposureService the canonical owner

The service should own the meaning:

"candidate becomes visible to manager for review"

#### P8.2 Remove early manager exposure paths

Any path that exposes candidate before interview and evaluation are complete must be:

- deprecated
- replaced
- removed after replacement verification

#### P8.3 Finalize manager-facing candidate package

Package contents per SRS:

- CV
- candidate summary
- verification video
- interview summary
- evaluation report

#### P8.4 Ensure manager actions are vacancy-scoped

Manager approve/reject must operate on:

- candidate
- vacancy
- match

not on ambiguous manager-level state

### Exit Criteria

- Manager review happens only after evaluation-complete candidates are exposed.
- Candidate package is SRS-complete.
- Manager exposure ownership is centralized.

## Phase 9. Finish Deletion Flows and Lifecycle Ownership

### Goal

Make deletion flows safe, explicit, and domain-correct.

### Tasks

#### P9.1 Candidate profile deletion flow

Requirements:

- two-step confirmation if desired by current UX
- cancel pending interview invites
- cancel active interview participation
- remove from matching pool
- preserve audit/log behavior as required

#### P9.2 Vacancy deletion flow

Requirements:

- confirmation
- stop future matching
- cancel pending interview invites
- cancel relevant open review flows

#### P9.3 Separate domain deletion from full destructive purge

Current broad deletion behavior should be narrowed.

Target:

- domain-safe deactivation/cancellation flow
- optional later hard-delete/archive policy

#### P9.4 Finalize lifecycle canonical ownership

By this phase:

- canonical match status should be the owner of match lifecycle
- canonical interview status should be the owner of interview lifecycle
- legacy drift should be isolated or removed

### Exit Criteria

- Deletion flows follow the SRS.
- Lifecycle ownership is no longer ambiguous.

## Phase 10. Remove Unneeded Legacy Behavior and Code

### Goal

Delete what no longer belongs in Helly v1 after replacements are live and verified.

### Important Rule

Deletion is allowed only after:

1. replacement exists
2. tests exist
3. feature-flag cutover is complete
4. no active runtime dependency remains

### Cleanup Targets

#### P10.1 Remove manual candidate browse UX

Legacy commands and branches that let candidates browse jobs directly should be removed from primary runtime once interview invitation flow is live.

#### P10.2 Remove manager-singleton vacancy assumptions

Delete code that assumes a single job per manager.

#### P10.3 Remove overloaded lifecycle vocabulary

Examples:

- `candidate_applied` when overloaded
- `contact_pending`
- `closed`

after canonical ownership is complete

#### P10.4 Remove JSON-primary persistence paths

If DB-first persistence is implemented, legacy file-backed paths should be deleted or retained only for import/migration tooling.

#### P10.5 Remove dead router branches and duplicate read-model logic

Particularly:

- duplicated lifecycle interpretation
- duplicate manager exposure paths
- obsolete typed-routing fallbacks once cutover is complete

### Exit Criteria

- Repository no longer contains product-defining legacy drift paths.
- Remaining compatibility code is intentionally documented, small, and non-owner.

## Phase 11. Verification, Hardening, and Release Readiness

### Goal

Prove the product is actually ready.

### Tasks

#### P11.1 Full end-to-end scenario test suite

Must cover:

- candidate onboarding to READY
- manager vacancy creation to OPEN
- matching
- interview invitation
- interview completion
- evaluation
- manager review
- candidate introduction
- candidate deletion
- vacancy deletion

#### P11.2 Prompt quality and model regression suite

#### P11.3 Data migration verification

Ensure legacy data can be interpreted or migrated safely where needed.

#### P11.4 Production observability checklist

Need dashboards/log visibility for:

- state transitions
- queue failures
- LLM failures
- matching failures
- interview completion
- manager exposure
- deletion side effects

#### P11.5 Deployment verification

- startup checks
- migration checks
- worker health checks
- environment variable checklist

### Exit Criteria

- Product is functionally complete against the SRS.
- Operational safety checks exist.
- Release candidate can be deployed safely.

## Detailed Task Backlog in Recommended Execution Order

The following is the recommended execution order for actual implementation tasks.

### Foundation and Safety

1. Audit current DB schema and create a missing-table/missing-column checklist.
2. Add or validate canonical DB columns for match and interview lifecycle.
3. Design and add vacancy-first schema for multi-vacancy managers.
4. Add raw message storage schema.
5. Add candidate verification schema.
6. Add interview wave schema support.
7. Expand characterization tests for flows that will be changed next.

### Media and Input Completion

8. Add normalized support for video message and video note.
9. Persist raw Telegram updates and media references.
10. Create unified file/media artifact model.
11. Implement transcription worker contracts.
12. Implement candidate verification intake flow.

### Prompt System

13. Build prompt inventory and ownership map.
14. Rewrite routing prompts.
15. Rewrite candidate onboarding prompts.
16. Rewrite manager vacancy prompts.
17. Rewrite matching/reranking prompts.
18. Rewrite interview prompts.
19. Rewrite evaluation prompts.
20. Add prompt regression datasets and tests.
21. Add LLM tracing, prompt versioning, and evaluation harness.
22. Build context assembly contracts for LLM-heavy stages.
23. Run document extraction benchmark and choose the final parser fallback chain.
24. Build the voice artifact pipeline around transcript-first processing.

### Queue Ownership

25. Replace placeholder queue infrastructure with real jobs/workers.
26. Move CV analysis to queue.
27. Move JD analysis to queue.
28. Move transcription to queue.
29. Move matching to queue.
30. Move evaluation generation to queue.
31. Add reminder workers.

### Product Flow Correction

32. Convert manager-singleton job model into vacancy model in runtime and repositories.
33. Update manager onboarding to create and manage multiple vacancies.
34. Make vacancy OPEN the canonical ready state for matching.
35. Separate onboarding interview behavior from post-match interview behavior.
36. Implement explicit interview invitation flow.
37. Implement interview waves.
38. Enforce one active interview per candidate.
39. Move manager exposure to post-interview, post-evaluation only.
40. Remove candidate manual browse flow from the primary UX.

### Manager Review and Deletion

41. Finalize manager review package, including verification video.
42. Ensure manager approve/reject operates on vacancy-scoped match entities.
43. Implement candidate profile deletion flow with correct cancellation side effects.
44. Implement vacancy deletion flow with correct cancellation side effects.

### Lifecycle Cutover and Cleanup

45. Make canonical lifecycle the owner of runtime decisions where safe.
46. Reduce legacy lifecycle writes and derived gate logic.
47. Remove deprecated lifecycle vocabulary after cutover.
48. Remove duplicate read-side lifecycle interpretation.
49. Remove JSON-primary persistence paths.
50. Remove dead routing branches and obsolete legacy commands.

### Final Hardening

51. Complete E2E flow coverage.
52. Run prompt/evaluation bake-offs.
53. Verify DB migrations against staging/production-like data.
54. Perform release-readiness checklist and production deploy validation.

## Prompt Rewrite Readiness Checklist

Before rewriting prompts for a subsystem, verify:

- the subsystem owner is known
- the structured output contract is defined
- failure/fallback behavior is defined
- evaluation examples exist
- the prompt does not own state transitions

## Database Readiness Checklist

Before claiming the product is complete, verify the DB includes:

- users
- candidate profiles
- candidate verification
- vacancies
- vacancy structured profile
- matches
- canonical match status
- interview sessions
- interview answers
- canonical interview status
- evaluation results
- files
- raw messages
- state transition logs
- deletion audit/support fields if required
- indexes for manager vacancy lookup
- indexes for candidate matching pool lookup
- indexes for active interview lookups

## Legacy Deletion Checklist

Before deleting a legacy path, verify:

- replacement owner exists
- runtime path is switched
- unit tests exist
- integration tests exist
- no production config depends on the old branch
- deprecation note can be removed safely

## Execution Notes for Future Tasks

- Read this document and [helly-v1-srs.md](/Users/vladigolub/Desktop/telegrambot/docs/helly-v1-srs.md) before implementing each new major task.
- Work in small, safe, test-backed increments.
- Prefer feature flags for runtime cutovers.
- Do not perform broad deletions until the replacement path is verified.
- When prompt tasks are reached, prompt content may be supplied or refined externally, but ownership, contracts, and tests should still be implemented here.

## Immediate Next Recommended Task

The next implementation task should be:

**Create a DB schema audit and migration checklist document, then map the current repositories/tables to the target Helly v1 entity model.**

Reason:

- multi-vacancy support, verification flow, raw messages, queue ownership, and lifecycle correctness all depend on the schema being complete
- this is the safest next step before major runtime refactor
