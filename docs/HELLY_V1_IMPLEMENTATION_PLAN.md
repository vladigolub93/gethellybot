# HELLY v1 Implementation Plan

Delivery Roadmap, Epics, and Task Decomposition Guide

Version: 1.0  
Date: 2026-03-07

## 1. Purpose

This document converts the Helly v1 product and architecture documentation into a practical delivery plan.

It is intended to guide:

- engineering sequencing
- milestone definition
- task decomposition
- dependency ordering
- acceptance planning

This is not a sprint commitment document. It is the canonical implementation roadmap used to create task backlogs.

## 2. Planning Assumptions

This roadmap assumes:

- one primary backend codebase
- modular monolith plus workers
- Telegram-first delivery
- no web dashboard in v1
- one core engineering effort rather than many independent teams

## 3. Recommended Milestones

Recommended milestone structure:

1. Foundation
2. State-Aware Conversation Layer
3. Candidate Intake
4. Vacancy Intake
5. Matching
6. Interviewing
7. Evaluation and Manager Review
8. Hardening and Launch Readiness

## 4. Milestone 1: Foundation

Goal:

Establish the technical skeleton needed for every later feature.

## 4.1 Epics

- project bootstrap
- infrastructure baseline
- persistence baseline
- Telegram integration baseline
- observability baseline
- prompt asset baseline

## 4.2 Deliverables

- backend service skeleton
- worker process skeleton
- migration setup
- raw message persistence
- Telegram update deduplication
- user/contact model
- consent capture
- config and secrets handling
- structured logging
- AI trace wrapper

## 4.3 Suggested Tasks

- create repository structure for API, workers, prompts, tests, and docs
- set up FastAPI app and health endpoints
- set up PostgreSQL connection and migrations
- define base entities: `users`, `files`, `raw_messages`, `state_transition_logs`, `job_execution_logs`
- implement Telegram webhook endpoint
- persist raw updates before business handling
- add update idempotency by `telegram_update_id`
- build Telegram outbound gateway abstraction
- implement contact capture handling
- implement consent capture and persistence
- add structured logger and request correlation IDs
- add AI client abstraction with prompt version tagging
- add queue and worker bootstrap

## 4.4 Exit Criteria

- duplicate Telegram updates are safe
- raw messages are stored
- users can start and share contact
- consent can be recorded
- jobs can be enqueued and processed
- logs and traces contain correlation IDs

## 4.5 Cross-Cutting Requirement: State-Aware Conversation

Every milestone after Foundation must follow the same control model:

- deterministic states remain authoritative
- the AI assists intelligently inside each state
- off-happy-path messages must not collapse into rigid repeated prompts
- every major state defines allowed actions and in-state assistance behavior

## 4.6 Milestone 1A: State-Aware Conversation Layer

Goal:

Make Helly helpful inside every active state without giving state authority to the LLM.

## 4.6.1 Epics

- state policy contract
- global bot controller
- state-specific policy prompts
- safe proposed-action validation
- off-happy-path conversational tests

## 4.6.2 Deliverables

- unified decision contract for in-state AI assistance
- allowed-action registry per major state
- policy prompt family for candidate, vacancy, interview, and review states
- safe no-op handling for help, objections, and clarification questions
- regression tests for common off-happy-path interactions

## 4.6.3 Suggested Tasks

- define policy input/output schema for state-aware conversation
- implement controller that receives current state, allowed actions, and latest user message
- implement policy families for candidate onboarding states
- implement policy families for vacancy onboarding states
- implement policy families for interview and review states
- validate AI-proposed actions against backend guards
- add integration tests for messages like `I do not have a CV`, `why do you need this`, and `what should I do next`

## 4.6.4 Exit Criteria

- major states can handle help requests without breaking flow
- the bot can suggest alternative valid inputs inside the current state
- invalid AI proposals cannot mutate state
- user experience no longer depends on rigid fixed replies alone

## 5. Milestone 2: Candidate Intake

Goal:

Enable candidates to complete profile onboarding to `READY`.

## 5.1 Epics

- candidate state machine
- multimodal CV intake
- candidate summary generation
- mandatory candidate field collection
- verification flow

## 5.2 Deliverables

- candidate profile entity and transitions
- file upload handling for CV and equivalent input
- transcription/extraction pipeline
- summary approval/edit loop
- salary/location/work format capture
- verification phrase and video flow
- ready-state validation

## 5.3 Suggested Tasks

- create `candidate_profiles` and `candidate_profile_versions`
- define candidate state transition rules
- implement candidate role selection flow
- implement CV file registration and object storage upload
- implement pasted-text experience input path
- implement voice experience input path
- build document extraction job and result persistence
- build transcription job and transcript persistence
- create `candidate_cv_extract` prompt asset
- create structured candidate summary schema
- implement summary review message rendering
- implement summary approve path
- implement summary correction path with exactly 1 correction round
- ask `Does this summary look correct, or would you like to change anything?`
- allow the user to describe what is wrong in natural language rather than only fixed command syntax
- create `candidate_summary_merge` prompt asset
- implement mandatory Q&A handler for salary/location/work format
- normalize work format to enum
- normalize salary into range/currency structure
- implement one follow-up rule for unresolved mandatory fields
- implement verification phrase generation and persistence
- implement verification video intake and storage
- implement `READY` eligibility validator

## 5.4 Exit Criteria

- candidate can reach `READY` entirely inside Telegram
- raw artifacts and structured outputs are stored
- invalid or incomplete answers do not bypass required states
- verification video is attached to profile

## 6. Milestone 3: Vacancy Intake

Goal:

Enable hiring managers to create and open structured vacancies.

## 6.1 Epics

- manager role flow
- vacancy entity and state machine
- JD intake and parsing
- clarification flow
- vacancy activation

## 6.2 Deliverables

- vacancy model and transitions
- manager role selection and access path
- multimodal JD ingestion
- extracted vacancy summary
- inconsistency detection
- mandatory vacancy clarifications
- `OPEN` activation logic

## 6.3 Suggested Tasks

- create `vacancies` and `vacancy_versions`
- define vacancy state machine
- implement manager role selection flow
- implement vacancy creation command/path
- build JD file intake and storage
- build voice/video JD transcription path
- create `vacancy_jd_extract` prompt asset
- create `vacancy_inconsistency_detect` prompt asset
- implement structured vacancy normalized schema
- implement in-state help and alternative-input guidance for `JD_PENDING`
- render vacancy clarification prompts
- implement mandatory fields: budget, countries, work format, team size, project description, primary tech stack
- implement one follow-up rule for unresolved vacancy fields
- implement in-state help and policy answers for `CLARIFICATION_QA`
- implement `OPEN` validation
- enqueue embedding refresh and matching trigger when vacancy opens

## 6.4 Exit Criteria

- manager can create and open a vacancy inside Telegram
- all mandatory vacancy fields are normalized and stored
- vacancy opening triggers downstream matching preparation

## 7. Milestone 4: Matching

Goal:

Produce ranked candidate shortlists for open vacancies.

## 7.1 Epics

- profile normalization
- embeddings
- hard filters
- deterministic scoring
- reranking
- match persistence

## 7.2 Deliverables

- embedding generation pipeline
- vector search support
- hard-filter engine
- transparent deterministic scoring
- reranking prompt and schema
- match records with stage breakdown

## 7.3 Suggested Tasks

- add embedding vector storage strategy
- build candidate embedding refresh job
- build vacancy embedding refresh job
- define normalized matching profile shape
- implement location compatibility rules
- implement salary compatibility rules
- implement work format compatibility rules
- implement seniority compatibility rules
- produce hard-filter reason codes
- implement top-N retrieval
- implement deterministic scoring formula and score explanation object
- create `candidate_rerank` prompt asset
- validate reranker output schema
- persist `matches` records with stage scores and rationales
- add re-trigger logic for candidate-ready and vacancy-open events

## 7.4 Exit Criteria

- open vacancy produces ranked candidate match records
- excluded candidates have explicit reason codes
- shortlisted candidates have deterministic and LLM-derived rationale

## 8. Milestone 5: Interviewing

Goal:

Run invitation waves and AI interviews inside Telegram.

## 8.1 Epics

- invitation lifecycle
- wave orchestration
- interview session state machine
- question generation
- answer handling
- reminder and expiration logic

## 8.2 Deliverables

- invitation sending flow
- accept/skip path
- interview session model
- 5 to 7 question plan generation
- follow-up limit enforcement
- transcript handling for voice/video interview answers

## 8.3 Suggested Tasks

- create `interview_sessions`, `interview_questions`, and `interview_answers`
- implement match invitation statuses
- implement invitation creation with expiration timestamp
- build wave policy configuration
- implement wave scheduler job
- persist `invite_waves` records linked to matching runs
- create first invitation wave during invite dispatch
- evaluate active invite waves and enqueue expansion waves when completion threshold is missed
- prevent empty expansion waves when shortlist is exhausted
- schedule reminder jobs for due invite waves
- send reminder notifications only to still-invited candidates
- expire stale unanswered invitations during wave evaluation
- implement accept interview path
- implement skip opportunity path
- create `interview_question_plan` prompt asset
- version and persist question plans
- implement current question pointer logic
- implement text answer capture
- implement voice/video answer transcription and storage
- create `interview_followup_decision` prompt asset
- enforce maximum one follow-up per question
- implement session expiration and reminder messages
- implement interview completion transition

## 8.4 Exit Criteria

- shortlisted candidates can be invited in waves
- candidate can complete interview inside Telegram
- session resumes correctly after interruption
- follow-up limits are enforced
- baseline reminder and expiration handling works for invite waves

## 9. Milestone 6: Evaluation and Manager Review

Goal:

Evaluate interview results and deliver qualified candidate packages to managers.

## 9.1 Epics

- interview evaluation
- auto-rejection
- manager candidate package builder
- approve/reject flow
- introduction flow

## 9.2 Deliverables

- evaluation worker
- configurable threshold logic
- manager package delivery
- baseline structured candidate package assembly
- manager approve/reject controls
- introduction strategy implementation
- first Telegram contact handoff mode after approval

## 9.3 Suggested Tasks

- create `evaluation_results`
- create `candidate_evaluate` prompt asset
- define evaluation output schema
- implement evaluation worker over candidate profile + vacancy + interview session
- implement threshold policy and auto-reject path
- implement manager candidate package assembly
- implement manager-facing summary rendering
- implement approve candidate path
- implement reject candidate path
- implement introduction strategy interface
- implement first introduction mode
- log introduction outcomes
- evolve package rendering from baseline structured notification content to a richer artifact bundle

## 9.4 Exit Criteria

- completed interviews generate evaluation results
- weak candidates can be auto-rejected
- managers receive baseline structured candidate packages
- managers can approve/reject
- approved candidates and managers can be introduced through the first Telegram handoff mode

## 10. Milestone 7: Hardening and Launch Readiness

Goal:

Make the system operationally safe and testable for launch.

## 10.1 Epics

- deletion flows
- observability expansion
- AI evaluation suite
- reliability hardening
- security/privacy hardening
- operational tooling

## 10.2 Deliverables

- candidate deletion flow
- vacancy deletion flow
- retry-safe job policies
- dead-letter review path
- benchmark datasets for AI subsystems
- alerting baseline
- retention and file access policy implementation

## 10.3 Suggested Tasks

- implement candidate deletion confirmation flow
- implement vacancy deletion confirmation flow
- stop deleted entities from active matching immediately
- cancel pending invitations/interviews where appropriate
- add scheduled cleanup or retention jobs
- add AI benchmark fixtures for CV extraction, JD extraction, reranking, and evaluation
- instrument key metrics and dashboards
- add dead-letter queue handling
- add job replay/admin support if needed
- add signed file access or equivalent secure retrieval
- finalize audit logging for state changes
- review and tighten secrets/config handling

## 10.4 Exit Criteria

- deletion flows are safe and auditable
- core AI capabilities have benchmark coverage
- operator can diagnose failed jobs
- launch risks are reduced to known items

## 11. Cross-Cutting Task Streams

These streams should run across milestones rather than waiting until the end.

## 11.1 Prompt Catalog Stream

Maintain a prompt inventory with owners, versions, schemas, and tests for every AI capability.

## 11.2 Evaluation Stream

Build small labeled datasets continuously for:

- candidate extraction
- vacancy extraction
- answer parsing
- reranking
- evaluation

## 11.3 Analytics Stream

Track conversion and drop-off by state:

- candidate onboarding completion
- vacancy activation completion
- invitation acceptance
- interview completion
- manager approval

## 11.4 Documentation Stream

Keep docs updated alongside implementation:

- schema/ERD
- state machine tables
- event catalog
- prompt catalog
- runbooks

## 12. Recommended Epic Structure for Ticketing

Each epic should decompose into ticket classes:

- schema
- domain service
- transport/integration
- async job
- prompt/schema asset
- tests
- observability
- docs

This prevents AI-heavy features from being implemented without operational and testing support.

## 13. Suggested Initial Ticket Backlog Shape

The first practical backlog should likely start with the following ticket order:

1. bootstrap service and worker runtime
2. create core database schema and migration flow
3. implement Telegram update ingestion and dedupe
4. store raw messages and files
5. implement user/contact/consent flow
6. implement candidate state machine skeleton
7. implement vacancy state machine skeleton
8. build document and transcription job pipeline
9. add candidate summary generation and review
10. add vacancy extraction and clarification

This order gets the highest-risk infrastructure and workflow concerns resolved early.

## 14. Dependencies and Critical Path

Critical path dependencies:

- Telegram ingestion before all user-facing flows
- database schema before state machines
- file and parsing pipeline before candidate/vacancy extraction
- candidate and vacancy normalized profiles before matching
- matching before invitation waves
- interview flow before evaluation
- evaluation before manager review

## 15. Definition of Done Guidance

Every feature ticket touching AI logic should only be considered done when all of the following exist:

- domain logic implemented
- prompt/schema contract implemented
- validation rules implemented
- tests added
- logs and trace fields added
- failure path handled
- documentation updated

## 16. Suggested Team Working Rules

To preserve architecture quality during implementation:

- do not call providers directly from route handlers
- do not mutate state from unvalidated LLM output
- do not merge prompt changes without versioning
- do not add new business states without transition table updates
- do not close AI-related tasks without sample evaluation cases

## 17. Risk Register

Key delivery risks:

- underestimating Telegram edge cases and media handling
- allowing AI outputs to bypass domain validation
- weak idempotency around updates and invitations
- schema drift between prompt outputs and persistence models
- delayed observability leading to slow debugging
- overcomplicating v1 with agent frameworks or unnecessary services

## 18. Recommended Next Documents After This Plan

After this roadmap, the next engineering docs should be:

- ERD / physical schema
- state transition matrix
- prompt catalog
- AI eval plan
- API/internal command contract spec
- operations runbook

## 19. Final Planning Position

The correct delivery strategy for Helly is to build the deterministic skeleton first and add AI capabilities into well-defined seams.

If implementation order is inverted and the team starts with "smart AI behaviors" before state, storage, retries, and observability, quality will degrade quickly.

The roadmap above is designed specifically to avoid that failure mode.
