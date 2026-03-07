# Helly v1 Task Execution Matrix

## Purpose

This document is the full implementation backlog for taking the current repository to a production-ready Helly v1 system aligned with the SRS in [helly-v1-srs.md](/Users/vladigolub/Desktop/telegrambot/docs/helly-v1-srs.md).

This is not a high-level roadmap. This is the execution matrix that should be used task-by-task until production.

Related documents:

- [helly-v1-srs.md](/Users/vladigolub/Desktop/telegrambot/docs/helly-v1-srs.md)
- [helly-target-architecture.md](/Users/vladigolub/Desktop/telegrambot/docs/helly-target-architecture.md)
- [helly-v1-implementation-plan.md](/Users/vladigolub/Desktop/telegrambot/docs/helly-v1-implementation-plan.md)
- [helly-db-schema-audit.md](/Users/vladigolub/Desktop/telegrambot/docs/helly-db-schema-audit.md)
- [matching-lifecycle-inventory.md](/Users/vladigolub/Desktop/telegrambot/docs/matching-lifecycle-inventory.md)
- [legacy-lifecycle-cleanup-plan.md](/Users/vladigolub/Desktop/telegrambot/docs/legacy-lifecycle-cleanup-plan.md)
- [remaining-lifecycle-drift.md](/Users/vladigolub/Desktop/telegrambot/docs/remaining-lifecycle-drift.md)

## How To Use This Document

- Implement tasks in order unless a task explicitly says it can be parallelized.
- Do not delete legacy code before the listed replacement task and cleanup gate are complete.
- Prefer additive schema and sidecar runtime integration before cutover.
- Before starting a task, verify its dependencies are done.
- Before marking a task done, verify the acceptance criteria and tests.

## Status Legend

- `TODO`: not started
- `IN PROGRESS`: currently being implemented
- `BLOCKED`: cannot proceed without external input or earlier task
- `DONE`: implemented and verified
- `DEFERRED`: intentionally postponed to post-v1

## Risk Legend

- `L`: low implementation risk
- `M`: medium implementation risk
- `H`: high implementation risk

## Release Gates

Production is not allowed until all of the following are true:

1. DB schema is complete for Helly v1.
2. Multi-vacancy manager flow works.
3. Candidate onboarding reaches READY with video verification.
4. Manager onboarding reaches vacancy OPEN.
5. Matching runs by vacancy.
6. Interview invitation and interview waves work.
7. Manager only sees candidates after interview and evaluation.
8. Canonical lifecycle owns runtime-critical states or legacy fallback is intentionally preserved with no drift.
9. Prompt set is complete and evaluated.
10. Queues/workers own heavy async processing.
11. Raw messages and files are stored.
12. Deletion flows are correct.
13. E2E tests cover the core product path.
14. Production health checks and rollback plan exist.

## Current Known Facts That Affect Task Order

- Live Supabase access is available.
- Live DB currently has only 21 applied migrations.
- Live DB is missing:
  - `candidate_profiles`
  - `job_profiles`
  - `matches.canonical_match_status`
  - `interview_runs.canonical_interview_status`
  - `user_states.canonical_interview_status`
- Current `jobs` schema is still one-manager-one-job.
- Current runtime still allows candidate browse/apply semantics that conflict with the SRS.
- Local JSON storage is still part of runtime persistence ownership.

## Master Backlog

## Stream A. Migration Control and Safety

### A-001

- Status: `TODO`
- Task: Create a migration tracking checklist for the real Supabase environment.
- Why: live DB is behind the repository schema.
- Depends on: none
- Output:
  - migration checklist doc section or dedicated file
  - list of already applied vs missing migrations
- Acceptance:
  - exact live migration gap is documented
  - current prod/staging DB state is known before schema changes
- Risk: `L`

### A-002

- Status: `TODO`
- Task: Add a release-safe procedure for schema application and verification.
- Why: runtime and DB are already diverged.
- Depends on: A-001
- Output:
  - repeatable schema apply process
  - rollback notes
  - post-migration verification commands
- Acceptance:
  - schema changes can be applied without guessing
  - verification path is documented
- Risk: `M`

### A-003

- Status: `TODO`
- Task: Expand DB status diagnostics to reflect the real Helly v1 required schema.
- Why: current `DbStatusService` only checks the older MVP schema.
- Depends on: A-001
- Output:
  - updated [db-status.service.ts](/Users/vladigolub/Desktop/telegrambot/src/admin/db-status.service.ts)
  - new required table/column inventory
- Acceptance:
  - admin DB status endpoint can detect missing Helly v1 schema parts
- Risk: `L`

### A-004

- Status: `TODO`
- Task: Add a production-safe migration dry-run checklist.
- Why: later schema steps are non-trivial.
- Depends on: A-002
- Output:
  - checklist for applying schema changes against live DB
- Acceptance:
  - every future schema task has an execution and verification pattern
- Risk: `L`

## Stream B. Schema Sync to Current Repository

### B-001

- Status: `TODO`
- Task: Apply missing repository migrations already assumed by code.
- Why: runtime already expects canonical profile tables and canonical lifecycle columns.
- Depends on: A-002
- Output:
  - live DB includes:
    - `candidate_profiles`
    - `job_profiles`
    - `matches.canonical_match_status`
    - `interview_runs.canonical_interview_status`
    - `user_states.canonical_interview_status`
- Acceptance:
  - live schema matches current repository assumptions
  - canonical persistence tests are no longer relying on columns absent in DB
- Risk: `M`

### B-002

- Status: `TODO`
- Task: Verify all existing repositories against the live DB after schema sync.
- Why: current repo and live DB drift must be closed before new schema work.
- Depends on: B-001
- Output:
  - repository-to-live-schema validation report
- Acceptance:
  - no repository writes target nonexistent columns/tables
- Risk: `L`

## Stream C. Vacancy-First Schema Foundation

### C-001

- Status: `TODO`
- Task: Design the target `vacancies` table.
- Why: current `jobs` table is structurally incompatible with SRS multi-vacancy behavior.
- Depends on: B-002
- Output:
  - SQL migration for `vacancies`
  - field ownership decisions
- Acceptance:
  - vacancy is first-class and manager-scoped, not manager-singleton
- Risk: `M`

### C-002

- Status: `TODO`
- Task: Design the target `vacancy_profiles` table.
- Why: vacancy structured profile cannot remain manager-singleton.
- Depends on: C-001
- Output:
  - SQL migration for `vacancy_profiles`
- Acceptance:
  - structured job profile is owned by `vacancy_id`
- Risk: `M`

### C-003

- Status: `TODO`
- Task: Add canonical vacancy lifecycle fields and indexes.
- Why: vacancy will become matching/interview unit.
- Depends on: C-001
- Output:
  - vacancy lifecycle columns
  - indexes for manager lookup, status lookup, matching readiness
- Acceptance:
  - vacancy rows can support draft/review/open/paused/deleted style lifecycle
- Risk: `M`

### C-004

- Status: `TODO`
- Task: Add migration path from `jobs` to `vacancies`.
- Why: old data must remain interpretable while runtime is migrated.
- Depends on: C-001, C-002
- Output:
  - compatibility mapping strategy
  - optional data backfill script or migration notes
- Acceptance:
  - `jobs` can be preserved during cutover without blocking new vacancy model
- Risk: `H`

### C-005

- Status: `TODO`
- Task: Introduce repository layer for `vacancies`.
- Why: runtime cannot move without a first-class vacancy repository.
- Depends on: C-001, C-002
- Output:
  - new repository module
  - tests
- Acceptance:
  - create/read/update/list vacancy behavior exists independently from `jobs`
- Risk: `M`

## Stream D. Raw Messages and File Storage Schema

### D-001

- Status: `TODO`
- Task: Design the `files` table.
- Why: SRS requires documents, voice, video, and verification media to be stored and linked.
- Depends on: B-002
- Output:
  - SQL migration for `files`
- Acceptance:
  - all uploaded assets can have a first-class record
- Risk: `M`

### D-002

- Status: `TODO`
- Task: Design the `raw_messages` table.
- Why: SRS requires every message to be stored in raw form.
- Depends on: B-002
- Output:
  - SQL migration for `raw_messages`
- Acceptance:
  - every Telegram update can be persisted with raw payload and normalized metadata
- Risk: `M`

### D-003

- Status: `TODO`
- Task: Add indexes and linking fields for `raw_messages` and `files`.
- Why: later flows need correlation by user, update, message, vacancy, match, interview.
- Depends on: D-001, D-002
- Output:
  - indexes
  - foreign-key or reference strategy
- Acceptance:
  - read-side tracing is feasible
- Risk: `L`

### D-004

- Status: `TODO`
- Task: Create repository layer for `files` and `raw_messages`.
- Why: runtime integration should not write to raw SQL directly.
- Depends on: D-001, D-002
- Output:
  - repositories
  - tests
- Acceptance:
  - file and raw message persistence are available as isolated services
- Risk: `M`

## Stream E. Verification and Evaluation Schema

### E-001

- Status: `TODO`
- Task: Design the `candidate_verifications` table.
- Why: video verification is mandatory in the SRS.
- Depends on: B-002, D-001, D-002
- Output:
  - SQL migration for `candidate_verifications`
- Acceptance:
  - issued phrase, submitted video, result, timestamps and links are all persistable
- Risk: `M`

### E-002

- Status: `TODO`
- Task: Design the `evaluation_results` table.
- Why: final evaluation must be explicit and reusable for manager review.
- Depends on: B-002
- Output:
  - SQL migration for `evaluation_results`
- Acceptance:
  - score, strengths, risks, recommendation and model metadata are persistable
- Risk: `M`

### E-003

- Status: `TODO`
- Task: Add repositories for verifications and evaluations.
- Depends on: E-001, E-002
- Output:
  - repositories
  - tests
- Acceptance:
  - read/write contracts exist for verification/evaluation storage
- Risk: `M`

## Stream F. Interview Invitation and Wave Schema

### F-001

- Status: `TODO`
- Task: Design the `interview_invitations` table.
- Why: waves and invitation lifecycle require first-class persistence.
- Depends on: C-001, E-002
- Output:
  - SQL migration for `interview_invitations`
- Acceptance:
  - invitation lifecycle can be tracked independently of interview completion
- Risk: `M`

### F-002

- Status: `TODO`
- Task: Add wave-tracking fields or companion table for per-vacancy invite waves.
- Why: wave logic is part of the SRS and cannot live only in memory.
- Depends on: F-001
- Output:
  - wave metadata schema
- Acceptance:
  - per-vacancy wave number and thresholds can be stored
- Risk: `M`

### F-003

- Status: `TODO`
- Task: Add repository layer for interview invitations and waves.
- Depends on: F-001, F-002
- Output:
  - repositories
  - tests
- Acceptance:
  - invite creation, decision update, wave queries are possible
- Risk: `M`

## Stream G. Canonical Interview Session Ownership

### G-001

- Status: `TODO`
- Task: Decide whether to repurpose `interviews` or create `interview_sessions`.
- Why: current interview persistence is split and ambiguous.
- Depends on: B-002, F-001
- Output:
  - architecture decision record
- Acceptance:
  - one canonical table is chosen for active interview session ownership
- Risk: `M`

### G-002

- Status: `TODO`
- Task: Implement the canonical interview session schema.
- Depends on: G-001
- Output:
  - migration for canonical interview session table/columns
- Acceptance:
  - active interview session has a clean persistent home
- Risk: `H`

### G-003

- Status: `TODO`
- Task: Model first-class interview answers or settle the canonical answer storage strategy.
- Why: answers are currently embedded JSON only.
- Depends on: G-001
- Output:
  - either `interview_answers` table or a documented canonical embedded-contract decision
- Acceptance:
  - answer ownership is explicit and durable
- Risk: `M`

### G-004

- Status: `TODO`
- Task: Add canonical interview session repository/service layer.
- Depends on: G-002
- Output:
  - repositories/services
  - tests
- Acceptance:
  - start/update/complete interview session behavior exists without relying on local JSON
- Risk: `H`

## Stream H. State Transition Auditability

### H-001

- Status: `TODO`
- Task: Design the `state_transition_logs` table.
- Why: state engine actions must be auditable in production.
- Depends on: B-002
- Output:
  - migration for transition log table
- Acceptance:
  - transitions can be recorded with action/reason/metadata
- Risk: `L`

### H-002

- Status: `TODO`
- Task: Add a transition logging service and repository.
- Depends on: H-001
- Output:
  - service/repository
  - tests
- Acceptance:
  - state machine transitions can be persisted reliably
- Risk: `L`

## Stream I. DB-First Persistence Cutover Foundation

### I-001

- Status: `TODO`
- Task: Inventory all local JSON owners and identify cutover seams.
- Depends on: B-002
- Output:
  - explicit list of file-backed owners and replacement targets
- Acceptance:
  - no hidden JSON-primary path remains undocumented
- Risk: `L`

### I-002

- Status: `TODO`
- Task: Make session persistence DB-primary with local file fallback only for emergency compatibility.
- Depends on: B-002, H-002
- Output:
  - updated state persistence ownership
  - tests
- Acceptance:
  - `user_states` is the primary session owner
- Risk: `M`

### I-003

- Status: `TODO`
- Task: Make match persistence DB-primary.
- Depends on: B-002
- Output:
  - updated match storage ownership
  - tests
- Acceptance:
  - `matches` is primary, local file storage is sidecar or removable
- Risk: `M`

### I-004

- Status: `TODO`
- Task: Make interview persistence DB-primary.
- Depends on: G-004
- Output:
  - updated interview storage ownership
  - tests
- Acceptance:
  - interview lifecycle no longer depends on local file ownership
- Risk: `H`

## Stream J. Prompt Inventory and Governance

### J-001

- Status: `TODO`
- Task: Create the complete prompt inventory.
- Depends on: none
- Output:
  - prompt registry doc or code-side map
- Acceptance:
  - every LLM prompt has owner, purpose, input/output contract and version slot
- Risk: `L`

### J-002

- Status: `TODO`
- Task: Define prompt versioning and naming rules.
- Depends on: J-001
- Output:
  - versioning convention
- Acceptance:
  - prompt changes can be compared and traced
- Risk: `L`

### J-003

- Status: `TODO`
- Task: Rewrite action routing prompts.
- Depends on: J-001
- Output:
  - revised typed action router prompts
  - eval cases
- Acceptance:
  - routing prompts are stage-aware and schema-bound
- Risk: `M`

### J-004

- Status: `TODO`
- Task: Rewrite candidate CV analysis and summary prompts.
- Depends on: J-001
- Output:
  - CV extraction prompt
  - CV summary prompt
  - summary edit merge prompt
- Acceptance:
  - candidate onboarding prompt family is complete
- Risk: `M`

### J-005

- Status: `TODO`
- Task: Rewrite candidate mandatory parsing prompts.
- Depends on: J-001
- Output:
  - salary/location/work-format parsers
  - follow-up generator prompt
- Acceptance:
  - mandatory answers have structured extraction outputs
- Risk: `M`

### J-006

- Status: `TODO`
- Task: Rewrite manager JD analysis and review prompts.
- Depends on: J-001
- Output:
  - JD extraction prompt
  - inconsistency prompt
  - summary/edit prompts
- Acceptance:
  - manager intake prompt family is complete
- Risk: `M`

### J-007

- Status: `TODO`
- Task: Rewrite manager mandatory parsing prompts.
- Depends on: J-001
- Output:
  - budget/country/work-format/team/project/stack parsers
- Acceptance:
  - vacancy mandatory parsing is complete
- Risk: `M`

### J-008

- Status: `TODO`
- Task: Rewrite matching rerank and explanation prompts.
- Depends on: J-001
- Output:
  - rerank prompt
  - shortlist explanation prompt
- Acceptance:
  - matching prompt family is complete
- Risk: `M`

### J-009

- Status: `TODO`
- Task: Rewrite interview generation and answer prompts.
- Depends on: J-001, G-001
- Output:
  - vacancy-specific interview question generation prompt
  - follow-up prompt
  - answer parsing prompt
- Acceptance:
  - interview prompt family is complete and post-match aligned
- Risk: `H`

### J-010

- Status: `TODO`
- Task: Rewrite final evaluation prompts.
- Depends on: J-001
- Output:
  - evaluation prompt family
- Acceptance:
  - strengths, risks, recommendation and score are schema-bound
- Risk: `M`

### J-011

- Status: `TODO`
- Task: Rewrite manager package composition prompts.
- Depends on: J-001, E-002
- Output:
  - manager-facing candidate package summary prompt(s)
- Acceptance:
  - manager package prompt family is complete
- Risk: `M`

## Stream K. LLM Eval, Tracing, and Quality Harness

### K-001

- Status: `TODO`
- Task: Add a unified LLM trace envelope to all important LLM calls.
- Depends on: J-001
- Output:
  - tracing contract
  - logs and metadata
- Acceptance:
  - every major LLM call can be traced by prompt version and model
- Risk: `M`

### K-002

- Status: `TODO`
- Task: Create evaluation datasets for action routing.
- Depends on: J-003
- Output:
  - routing eval dataset
- Acceptance:
  - routing changes can be regression-tested
- Risk: `L`

### K-003

- Status: `TODO`
- Task: Create evaluation datasets for CV/JD extraction.
- Depends on: J-004, J-006
- Output:
  - extraction eval datasets
- Acceptance:
  - extraction quality can be compared before prompt/model changes
- Risk: `L`

### K-004

- Status: `TODO`
- Task: Create evaluation datasets for mandatory answer parsing.
- Depends on: J-005, J-007
- Output:
  - parsing eval datasets
- Acceptance:
  - incomplete/ambiguous answer handling is testable
- Risk: `L`

### K-005

- Status: `TODO`
- Task: Create evaluation datasets for interview evaluation outputs.
- Depends on: J-010
- Output:
  - interview evaluation benchmark set
- Acceptance:
  - evaluation drift can be measured
- Risk: `M`

### K-006

- Status: `TODO`
- Task: Add a prompt/model comparison harness for high-risk prompts.
- Depends on: K-001
- Output:
  - comparison scripts or test harness
- Acceptance:
  - prompt/model alternatives can be compared before rollout
- Risk: `M`

## Stream L. Document Ingestion and Parser Benchmark

### L-001

- Status: `TODO`
- Task: Inventory all current document extraction paths for CV/JD intake.
- Depends on: none
- Output:
  - extraction path inventory
- Acceptance:
  - current parser chain is documented
- Risk: `L`

### L-002

- Status: `TODO`
- Task: Define document extraction benchmark cases.
- Depends on: L-001
- Output:
  - benchmark sample set
- Acceptance:
  - representative CV/JD docs exist for parser comparison
- Risk: `L`

### L-003

- Status: `TODO`
- Task: Compare current parser with improved fallback options.
- Depends on: L-002
- Output:
  - parser benchmark results
- Acceptance:
  - chosen extraction chain is evidence-based
- Risk: `M`

### L-004

- Status: `TODO`
- Task: Implement final document extraction fallback chain.
- Depends on: L-003
- Output:
  - chosen parser integration
  - tests
- Acceptance:
  - CV/JD extraction quality is improved and deterministic
- Risk: `M`

## Stream M. Voice and Media Processing Pipeline

### M-001

- Status: `TODO`
- Task: Add normalized support for video message and video note in Telegram model.
- Depends on: D-001, D-002
- Output:
  - updated telegram input model
- Acceptance:
  - runtime can recognize and persist all required SRS modalities
- Risk: `M`

### M-002

- Status: `TODO`
- Task: Build transcript-first voice artifact pipeline.
- Depends on: D-001, D-004
- Output:
  - transcription artifact contract
  - structured parse contract
- Acceptance:
  - voice processing is split into media, transcript, and parsed artifact stages
- Risk: `M`

### M-003

- Status: `TODO`
- Task: Add quality checks and fallback behavior for low-confidence transcription.
- Depends on: M-002
- Output:
  - transcription quality policy
- Acceptance:
  - low-confidence audio does not silently corrupt structured profile data
- Risk: `M`

### M-004

- Status: `TODO`
- Task: Ensure all media uploads persist file records and raw message records.
- Depends on: D-004, M-001
- Output:
  - runtime media persistence wiring
- Acceptance:
  - every media-bearing message is traceable through `files` and `raw_messages`
- Risk: `M`

## Stream N. Queue and Worker Ownership

### N-001

- Status: `TODO`
- Task: Choose and implement the real queue backend.
- Depends on: none
- Output:
  - queue backend decision
  - worker bootstrap
- Acceptance:
  - placeholder queue modules are replaced by a real job system
- Risk: `M`

### N-002

- Status: `TODO`
- Task: Implement CV analysis job.
- Depends on: N-001, J-004
- Output:
  - CV analysis worker
- Acceptance:
  - CV processing no longer blocks Telegram runtime
- Risk: `M`

### N-003

- Status: `TODO`
- Task: Implement JD analysis job.
- Depends on: N-001, J-006
- Output:
  - JD analysis worker
- Acceptance:
  - JD processing no longer blocks Telegram runtime
- Risk: `M`

### N-004

- Status: `TODO`
- Task: Implement transcription job.
- Depends on: N-001, M-002
- Output:
  - transcription worker
- Acceptance:
  - voice/video audio extraction can run asynchronously
- Risk: `M`

### N-005

- Status: `TODO`
- Task: Implement matching job.
- Depends on: N-001, C-005
- Output:
  - matching worker
- Acceptance:
  - matching is queue-owned
- Risk: `H`

### N-006

- Status: `TODO`
- Task: Implement rerank job.
- Depends on: N-005, J-008
- Output:
  - rerank worker
- Acceptance:
  - ranking-heavy LLM work is async
- Risk: `M`

### N-007

- Status: `TODO`
- Task: Implement interview generation job.
- Depends on: N-001, J-009, G-004
- Output:
  - interview question generation worker
- Acceptance:
  - vacancy-specific interview plans can be generated asynchronously
- Risk: `M`

### N-008

- Status: `TODO`
- Task: Implement final evaluation job.
- Depends on: N-001, J-010, E-003
- Output:
  - evaluation worker
- Acceptance:
  - final evaluation is async and persisted
- Risk: `M`

### N-009

- Status: `TODO`
- Task: Implement reminder jobs.
- Depends on: N-001, F-003
- Output:
  - reminder worker set
- Acceptance:
  - incomplete onboarding/interview/review reminders exist
- Risk: `M`

### N-010

- Status: `TODO`
- Task: Implement deletion cleanup jobs.
- Depends on: N-001, E-003
- Output:
  - async cleanup workers
- Acceptance:
  - heavy deletion side effects do not block runtime
- Risk: `M`

## Stream O. Candidate Onboarding Completion

### O-001

- Status: `TODO`
- Task: Audit candidate onboarding runtime branch against the SRS order.
- Depends on: none
- Output:
  - exact mapping of current branch vs target order
- Acceptance:
  - no ambiguity remains about required cutovers
- Risk: `L`

### O-002

- Status: `TODO`
- Task: Finalize typed routing coverage for full candidate onboarding.
- Depends on: J-003
- Output:
  - typed routing coverage for contact, role, CV, review, mandatory, verification
- Acceptance:
  - candidate onboarding is fully gatekeeper-compatible
- Risk: `M`

### O-003

- Status: `TODO`
- Task: Enforce candidate onboarding order exactly as the SRS requires.
- Depends on: O-001, O-002
- Output:
  - runtime branch corrections
- Acceptance:
  - candidate cannot skip required steps
- Risk: `M`

### O-004

- Status: `TODO`
- Task: Implement candidate summary correction loop limit.
- Depends on: O-003
- Output:
  - deterministic correction loop handling
- Acceptance:
  - max correction loops is enforced
- Risk: `L`

### O-005

- Status: `TODO`
- Task: Implement one-follow-up-per-question discipline for candidate mandatory answers.
- Depends on: J-005, O-003
- Output:
  - follow-up control logic
- Acceptance:
  - no follow-up-to-follow-up behavior remains
- Risk: `M`

### O-006

- Status: `TODO`
- Task: Implement candidate video verification flow.
- Depends on: E-001, M-001, M-004
- Output:
  - verification issuance, submission, storage, review logic
- Acceptance:
  - candidate reaches READY only after verification step is satisfied
- Risk: `H`

### O-007

- Status: `TODO`
- Task: Define and enforce candidate READY state.
- Depends on: O-003, O-006
- Output:
  - readiness evaluator
- Acceptance:
  - only fully onboarded candidates enter matching pool
- Risk: `M`

## Stream P. Manager Onboarding Completion

### P-001

- Status: `TODO`
- Task: Audit manager onboarding runtime branch against vacancy-first target flow.
- Depends on: C-005
- Output:
  - exact current vs target branch map
- Acceptance:
  - manager onboarding cutover is fully scoped
- Risk: `L`

### P-002

- Status: `TODO`
- Task: Finalize typed routing coverage for manager onboarding.
- Depends on: J-003, J-006, J-007
- Output:
  - typed routing for JD intake, review, mandatory questionnaire, decisions
- Acceptance:
  - manager onboarding is fully gatekeeper-compatible
- Risk: `M`

### P-003

- Status: `TODO`
- Task: Create vacancy creation flow against the new vacancy repository.
- Depends on: C-005, P-001
- Output:
  - runtime vacancy creation path
- Acceptance:
  - manager can create a vacancy without relying on singleton `jobs`
- Risk: `H`

### P-004

- Status: `TODO`
- Task: Implement manager JD review/edit loop against vacancy model.
- Depends on: P-003
- Output:
  - vacancy review flow
- Acceptance:
  - generated vacancy summary can be approved/edited safely
- Risk: `M`

### P-005

- Status: `TODO`
- Task: Implement manager mandatory questionnaire completion against vacancy model.
- Depends on: P-003, J-007
- Output:
  - mandatory question flow for vacancy
- Acceptance:
  - budget, countries, work format, team, project, stack are collectable
- Risk: `M`

### P-006

- Status: `TODO`
- Task: Define and enforce vacancy OPEN state.
- Depends on: P-004, P-005
- Output:
  - vacancy completeness evaluator
- Acceptance:
  - only complete vacancies become OPEN and eligible for matching
- Risk: `M`

### P-007

- Status: `TODO`
- Task: Add manager support for multiple vacancies in runtime UI and repositories.
- Depends on: P-003, P-006
- Output:
  - manager vacancy list/create/select behavior
- Acceptance:
  - manager can own and manage multiple vacancies
- Risk: `H`

## Stream Q. Matching Engine Realignment

### Q-001

- Status: `TODO`
- Task: Make vacancy, not manager, the matching unit.
- Depends on: C-005, P-006
- Output:
  - updated matching inputs
- Acceptance:
  - matching run is always vacancy-scoped
- Risk: `H`

### Q-002

- Status: `TODO`
- Task: Formalize hard filter stage and persisted outputs.
- Depends on: Q-001
- Output:
  - hard filter policy
  - persisted filter reason format
- Acceptance:
  - hard filter exclusions are deterministic and inspectable
- Risk: `M`

### Q-003

- Status: `TODO`
- Task: Formalize embedding retrieval stage and persisted outputs.
- Depends on: Q-001
- Output:
  - retrieval contract
- Acceptance:
  - retrieval shortlist can be reproduced and audited
- Risk: `M`

### Q-004

- Status: `TODO`
- Task: Formalize deterministic scoring stage and persisted outputs.
- Depends on: Q-001
- Output:
  - scoring contract
- Acceptance:
  - top candidate scoring is inspectable and stable
- Risk: `M`

### Q-005

- Status: `TODO`
- Task: Formalize rerank stage and shortlist selection.
- Depends on: Q-001, J-008
- Output:
  - rerank contract
- Acceptance:
  - reranked shortlist size and logic are deterministic around the LLM
- Risk: `M`

### Q-006

- Status: `TODO`
- Task: Persist matching run artifacts or summaries needed for debugging/admin.
- Depends on: Q-002, Q-003, Q-004, Q-005
- Output:
  - matching run storage strategy
- Acceptance:
  - support/admin can explain why a match was selected or rejected
- Risk: `M`

## Stream R. Candidate Browse Flow Removal

### R-001

- Status: `TODO`
- Task: Audit all candidate manual browse and match-pull entry points.
- Depends on: none
- Output:
  - list of commands, buttons, and router paths to remove or deprecate
- Acceptance:
  - no hidden candidate browse paths remain undocumented
- Risk: `L`

### R-002

- Status: `TODO`
- Task: Hide candidate manual browse from primary UX.
- Depends on: R-001, S-003
- Output:
  - UI/command cleanup
- Acceptance:
  - candidate is guided by invitations, not browsing
- Risk: `M`

### R-003

- Status: `TODO`
- Task: Remove or isolate legacy candidate browse runtime branches after replacement is live.
- Depends on: Z-003
- Output:
  - deleted or deprecated legacy browse code
- Acceptance:
  - primary candidate journey matches the SRS
- Risk: `M`

## Stream S. Interview Invitation and Decision Flow

### S-001

- Status: `TODO`
- Task: Implement explicit interview invitation runtime state.
- Depends on: F-003, Q-005
- Output:
  - invitation state branch
- Acceptance:
  - invite is a distinct stage from candidate apply/reject
- Risk: `H`

### S-002

- Status: `TODO`
- Task: Implement candidate accept/skip interview invitation flow.
- Depends on: S-001
- Output:
  - runtime decision handling
- Acceptance:
  - invitation decision does not immediately expose candidate to manager
- Risk: `H`

### S-003

- Status: `TODO`
- Task: Replace candidate apply/reject semantics with interview invitation semantics in the primary flow.
- Depends on: S-001, S-002
- Output:
  - corrected decision flow
- Acceptance:
  - old apply flow is no longer the primary product path
- Risk: `H`

### S-004

- Status: `TODO`
- Task: Add interview invitation reminders and expiry handling.
- Depends on: N-009, F-003
- Output:
  - reminder/expiry behavior
- Acceptance:
  - invitations cannot stay unresolved forever without policy
- Risk: `M`

## Stream T. Vacancy-Specific Interview Runtime

### T-001

- Status: `TODO`
- Task: Move interview generation to vacancy-specific post-match context.
- Depends on: J-009, N-007, S-002
- Output:
  - vacancy-specific interview plan generation
- Acceptance:
  - interview questions are generated from vacancy + candidate context
- Risk: `H`

### T-002

- Status: `TODO`
- Task: Implement interview start from accepted invitation only.
- Depends on: T-001, G-004
- Output:
  - corrected interview start seam
- Acceptance:
  - interview no longer functions as the old pre-match flow owner
- Risk: `H`

### T-003

- Status: `TODO`
- Task: Implement interview answer flow for text and voice, and video if supported.
- Depends on: T-002, M-001, M-002
- Output:
  - interview answer runtime handling
- Acceptance:
  - answer submission works for supported modalities and remains state-controlled
- Risk: `M`

### T-004

- Status: `TODO`
- Task: Implement one follow-up max per main interview question.
- Depends on: T-003, J-009
- Output:
  - deterministic follow-up limiter
- Acceptance:
  - follow-up behavior matches the SRS
- Risk: `M`

### T-005

- Status: `TODO`
- Task: Implement interview completion against canonical interview session ownership.
- Depends on: T-003, G-004
- Output:
  - completion seam
- Acceptance:
  - interview completion persists durable artifacts and status
- Risk: `M`

### T-006

- Status: `TODO`
- Task: Ensure one active interview per candidate invariant.
- Depends on: T-002, F-003
- Output:
  - invariant enforcement logic
- Acceptance:
  - candidate cannot have multiple active interviews simultaneously
- Risk: `H`

## Stream U. Interview Waves

### U-001

- Status: `TODO`
- Task: Define wave policy configuration.
- Depends on: F-002
- Output:
  - config for wave size, completion thresholds, timeouts
- Acceptance:
  - wave behavior is explicit, not hidden in code branches
- Risk: `L`

### U-002

- Status: `TODO`
- Task: Implement first-wave invite generation.
- Depends on: F-003, Q-005, U-001
- Output:
  - invite batch creation logic
- Acceptance:
  - shortlisted candidates are invited in controlled batches
- Risk: `M`

### U-003

- Status: `TODO`
- Task: Implement next-wave trigger logic.
- Depends on: U-001, U-002, S-004, T-005
- Output:
  - worker or service logic
- Acceptance:
  - new wave is triggered only when prior wave completion is insufficient
- Risk: `H`

### U-004

- Status: `TODO`
- Task: Add admin/diagnostic visibility for wave progression.
- Depends on: U-002
- Output:
  - admin read-side diagnostics
- Acceptance:
  - wave behavior can be inspected in production
- Risk: `L`

## Stream V. Evaluation and Thresholding

### V-001

- Status: `TODO`
- Task: Implement final evaluation persistence in `evaluation_results`.
- Depends on: E-003, N-008, T-005
- Output:
  - evaluation write path
- Acceptance:
  - completed interviews produce persisted evaluation records
- Risk: `M`

### V-002

- Status: `TODO`
- Task: Implement thresholding policy for manager visibility.
- Depends on: V-001
- Output:
  - threshold evaluator
- Acceptance:
  - weak candidates are filtered before manager exposure
- Risk: `M`

### V-003

- Status: `TODO`
- Task: Define and persist canonical evaluation status if needed.
- Depends on: V-001
- Output:
  - canonical evaluation status decision and schema if adopted
- Acceptance:
  - evaluation outcome has explicit ownership if required
- Risk: `L`

## Stream W. Manager Exposure and Review Correction

### W-001

- Status: `TODO`
- Task: Make `ManagerExposureService` the sole canonical owner of manager exposure.
- Depends on: V-002, C-005
- Output:
  - centralized exposure orchestration
- Acceptance:
  - manager exposure no longer occurs from ad hoc paths
- Risk: `H`

### W-002

- Status: `TODO`
- Task: Ensure manager exposure only happens after interview completion and evaluation pass.
- Depends on: W-001, V-002
- Output:
  - corrected runtime gating
- Acceptance:
  - manager cannot see candidate too early
- Risk: `H`

### W-003

- Status: `TODO`
- Task: Finalize manager review read model using canonical package + persisted canonical lifecycle.
- Depends on: E-003, W-001
- Output:
  - final read model and tests
- Acceptance:
  - manager package is complete and stable
- Risk: `M`

### W-004

- Status: `TODO`
- Task: Include verification video in manager package.
- Depends on: O-006, W-003
- Output:
  - verification attachment in package
- Acceptance:
  - manager package matches the SRS content requirements
- Risk: `M`

### W-005

- Status: `TODO`
- Task: Ensure manager approve/reject is vacancy-scoped and match-scoped.
- Depends on: C-005, W-002
- Output:
  - corrected decision seams
- Acceptance:
  - manager decisions are not ambiguous across vacancies
- Risk: `M`

## Stream X. Candidate Introduction Flow

### X-001

- Status: `TODO`
- Task: Define the exact post-approval introduction mechanism.
- Why: SRS allows candidate-manager connection in Telegram, but implementation details must be explicit.
- Depends on: W-005
- Output:
  - product decision for introduction format
- Acceptance:
  - approved contact introduction is deterministic
- Risk: `L`

### X-002

- Status: `TODO`
- Task: Implement introduction flow after manager approval.
- Depends on: X-001
- Output:
  - introduction runtime behavior
- Acceptance:
  - manager approval leads to connection without changing unrelated flows
- Risk: `M`

## Stream Y. Deletion Flows

### Y-001

- Status: `TODO`
- Task: Implement candidate profile deletion as a scoped domain flow.
- Depends on: O-007, T-006
- Output:
  - candidate deletion orchestration
- Acceptance:
  - pending invites, active interviews, and matching eligibility are cancelled appropriately
- Risk: `H`

### Y-002

- Status: `TODO`
- Task: Implement manager vacancy deletion flow.
- Depends on: P-007, F-003
- Output:
  - vacancy deletion orchestration
- Acceptance:
  - vacancy deletion cancels future matching and related interview flows
- Risk: `H`

### Y-003

- Status: `TODO`
- Task: Separate scoped domain deletion from full hard purge behavior.
- Depends on: Y-001, Y-002
- Output:
  - deletion policy split
- Acceptance:
  - product deletion no longer equals blind data purge
- Risk: `M`

### Y-004

- Status: `TODO`
- Task: Move heavy deletion side effects to queue-owned cleanup jobs.
- Depends on: N-010, Y-003
- Output:
  - deletion cleanup worker integration
- Acceptance:
  - deletion flows remain responsive and safe
- Risk: `M`

## Stream Z. Canonical Lifecycle Runtime Ownership

### Z-001

- Status: `TODO`
- Task: Complete canonical lifecycle persistence for all relevant write paths.
- Depends on: B-001, V-001, W-005
- Output:
  - canonical status persistence coverage report
- Acceptance:
  - key lifecycle writes persist canonical state where intended
- Risk: `M`

### Z-002

- Status: `TODO`
- Task: Shift runtime-critical decisions from legacy-overloaded status logic to canonical ownership where safe.
- Depends on: Z-001
- Output:
  - cutover of decision gates
- Acceptance:
  - candidate and manager gating no longer depends on overloaded legacy status in aligned paths
- Risk: `H`

### Z-003

- Status: `TODO`
- Task: Remove early legacy product semantics after cutover.
- Depends on: S-003, W-002, Z-002
- Output:
  - removal of old apply/browse/early-exposure semantics
- Acceptance:
  - runtime product flow matches Helly v1 semantics
- Risk: `H`

### Z-004

- Status: `TODO`
- Task: Remove deprecated lifecycle vocabulary that no longer owns behavior.
- Depends on: Z-002, Z-003
- Output:
  - removal of dead legacy statuses/helpers
- Acceptance:
  - lifecycle language is coherent and canonical
- Risk: `M`

## Stream AA. Legacy Cleanup

### AA-001

- Status: `TODO`
- Task: Remove manager-singleton assumptions from repositories and runtime.
- Depends on: P-007, C-005, Z-003
- Output:
  - deleted singleton job assumptions
- Acceptance:
  - no runtime-critical path assumes one manager has one job
- Risk: `H`

### AA-002

- Status: `TODO`
- Task: Remove duplicate lifecycle read-side inference paths.
- Depends on: Z-002
- Output:
  - cleaned read-side code
- Acceptance:
  - snapshot/read models are the primary normalized source
- Risk: `M`

### AA-003

- Status: `TODO`
- Task: Remove JSON-primary storage owners.
- Depends on: I-002, I-003, I-004
- Output:
  - deleted or downgraded file-backed storage
- Acceptance:
  - DB is the primary owner of runtime state, match, interview data
- Risk: `H`

### AA-004

- Status: `TODO`
- Task: Remove dead router branches, duplicate typed-routing plumbing, and obsolete compatibility layers.
- Depends on: O-002, P-002, Z-003
- Output:
  - cleaned router/runtime structure
- Acceptance:
  - runtime branches correspond to the final product flow only
- Risk: `M`

### AA-005

- Status: `TODO`
- Task: Remove or isolate obsolete mixed profile storage if superseded cleanly.
- Depends on: C-005, P-007, AA-003
- Output:
  - cleanup of `profiles(kind=job)` and similar drift paths where safe
- Acceptance:
  - profile ownership is coherent
- Risk: `H`

## Stream AB. Admin, Diagnostics, and Support Readiness

### AB-001

- Status: `TODO`
- Task: Update admin read paths to include vacancy-first model and invitation/interview wave visibility.
- Depends on: C-005, F-003, U-004
- Output:
  - admin reporting updates
- Acceptance:
  - support/admin can inspect the real Helly v1 flow
- Risk: `M`

### AB-002

- Status: `TODO`
- Task: Add observability for queues, prompts, evaluations, and manager exposure.
- Depends on: K-001, N-001, W-001
- Output:
  - logs/metrics/tracing additions
- Acceptance:
  - production debugging is realistic
- Risk: `M`

### AB-003

- Status: `TODO`
- Task: Add diagnostics for schema version, worker health, and queue lag.
- Depends on: A-003, N-001
- Output:
  - admin or health diagnostics
- Acceptance:
  - operational status can be checked quickly in production
- Risk: `L`

## Stream AC. Security and Compliance Basics

### AC-001

- Status: `TODO`
- Task: Review and document sensitive data handling for contact data, CVs, videos, and evaluations.
- Depends on: D-001, D-002, E-001, E-002
- Output:
  - data handling notes
- Acceptance:
  - sensitive storage owners are explicit
- Risk: `L`

### AC-002

- Status: `TODO`
- Task: Ensure user consent is captured before full profile creation where required by product/legal policy.
- Depends on: O-003
- Output:
  - consent handling in runtime
- Acceptance:
  - consent requirement is explicit and testable
- Risk: `M`

### AC-003

- Status: `TODO`
- Task: Review deletion and retention policy for stored files and raw messages.
- Depends on: Y-003, D-001, D-002
- Output:
  - retention policy implementation notes
- Acceptance:
  - deletion semantics are consistent with stored artifacts
- Risk: `M`

## Stream AD. Testing and Verification

### AD-001

- Status: `TODO`
- Task: Extend characterization coverage as each major flow is replaced.
- Depends on: ongoing
- Output:
  - expanded characterization tests
- Acceptance:
  - legacy-to-new regressions are caught early
- Risk: `L`

### AD-002

- Status: `TODO`
- Task: Add end-to-end test for full candidate onboarding to READY with video verification.
- Depends on: O-006, O-007
- Output:
  - E2E test
- Acceptance:
  - candidate flow is proven end-to-end
- Risk: `M`

### AD-003

- Status: `TODO`
- Task: Add end-to-end test for manager onboarding to vacancy OPEN.
- Depends on: P-006, P-007
- Output:
  - E2E test
- Acceptance:
  - manager multi-vacancy flow is proven end-to-end
- Risk: `M`

### AD-004

- Status: `TODO`
- Task: Add end-to-end test for matching -> invitation -> interview -> evaluation -> manager review.
- Depends on: Q-005, S-003, T-005, V-001, W-002
- Output:
  - E2E test
- Acceptance:
  - core product path is proven end-to-end
- Risk: `H`

### AD-005

- Status: `TODO`
- Task: Add end-to-end test for candidate introduction after approval.
- Depends on: X-002
- Output:
  - E2E test
- Acceptance:
  - final product conversion path is proven
- Risk: `M`

### AD-006

- Status: `TODO`
- Task: Add end-to-end tests for candidate and vacancy deletion.
- Depends on: Y-001, Y-002
- Output:
  - E2E tests
- Acceptance:
  - deletion flows are proven safe
- Risk: `M`

### AD-007

- Status: `TODO`
- Task: Add production-like migration verification test/checklist.
- Depends on: A-004, all schema streams
- Output:
  - migration verification routine
- Acceptance:
  - schema rollout to production is verified before real deploy
- Risk: `M`

## Stream AE. Release and Production Hardening

### AE-001

- Status: `TODO`
- Task: Create final environment checklist for bot runtime, workers, DB, vector store, and LLM configuration.
- Depends on: N-001, all schema streams
- Output:
  - environment checklist
- Acceptance:
  - no required production dependency is implicit
- Risk: `L`

### AE-002

- Status: `TODO`
- Task: Add startup health checks for runtime-critical dependencies.
- Depends on: AE-001
- Output:
  - startup health validation
- Acceptance:
  - app can fail fast if DB/vector/LLM critical dependencies are unavailable
- Risk: `L`

### AE-003

- Status: `TODO`
- Task: Add worker health checks and queue backlog visibility.
- Depends on: N-001, AB-003
- Output:
  - health endpoints or admin diagnostics
- Acceptance:
  - background job system health is observable
- Risk: `M`

### AE-004

- Status: `TODO`
- Task: Run release candidate verification against the full release gates.
- Depends on: all streams except cleanup tasks explicitly marked post-cutover
- Output:
  - release candidate checklist result
- Acceptance:
  - every release gate is explicitly checked and signed off
- Risk: `M`

### AE-005

- Status: `TODO`
- Task: Deploy Helly v1 release candidate and run post-deploy verification.
- Depends on: AE-004
- Output:
  - deployment verification report
- Acceptance:
  - production deployment is confirmed healthy
- Risk: `H`

## Post-Production Cleanup Tasks

These are not required before first working production if backward-compatible compatibility layers remain safe, but should be completed soon after initial stable release.

### POST-001

- Status: `TODO`
- Task: Remove fully obsolete legacy tables or columns after confirmed cutover and retention window.
- Depends on: AA-003, AA-005, production stability window
- Risk: `H`

### POST-002

- Status: `TODO`
- Task: Backfill or archive historical data into final canonical tables if needed.
- Depends on: stable production schema
- Risk: `M`

### POST-003

- Status: `TODO`
- Task: Remove long-lived feature flags that are no longer needed.
- Depends on: stable cutover
- Risk: `L`

## Critical Path To First Production-Ready Helly v1

The shortest correct path to production is:

1. A-001 to A-004
2. B-001 to B-002
3. C-001 to C-005
4. D-001 to D-004
5. E-001 to E-003
6. F-001 to F-003
7. G-001 to G-004
8. I-002 to I-004
9. J-001 to J-011
10. K-001 to K-006
11. L-001 to L-004
12. M-001 to M-004
13. N-001 to N-010
14. O-001 to O-007
15. P-001 to P-007
16. Q-001 to Q-006
17. S-001 to S-004
18. T-001 to T-006
19. U-001 to U-004
20. V-001 to V-003
21. W-001 to W-005
22. X-001 to X-002
23. Y-001 to Y-004
24. Z-001 to Z-004
25. AA-001 to AA-004
26. AB-001 to AB-003
27. AC-001 to AC-003
28. AD-001 to AD-007
29. AE-001 to AE-005

## Recommended Immediate Next Task

The next task to execute from this matrix is:

**A-001: Create a migration tracking checklist for the real Supabase environment.**

Reason:

- live DB is already confirmed to be behind repository migrations
- no serious runtime or schema work should proceed without closing that visibility gap first

