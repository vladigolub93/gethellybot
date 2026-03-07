# HELLY v1

AI-Powered Telegram Recruitment Matching Platform  
Software Requirements Specification (SRS)

Version: 1.0  
Status: Master Specification  
Date: 2026-03-07

## 1. Document Purpose

This document defines the product, functional, technical, and operational requirements for Helly v1.

It is intended to serve as the master specification for implementation through coding agents such as Cursor/Codex and for alignment across product, engineering, AI, QA, and operations.

This specification is normative unless explicitly marked as an example or future extension.

## 2. Product Summary

### 2.1 Product Name

Helly

### 2.2 Product Type

Telegram-first AI recruiting platform.

### 2.3 Product Goal

Helly automates early-stage recruiting by:

- collecting structured candidate profiles
- collecting structured vacancy profiles
- performing AI-based candidate-vacancy matching
- conducting short AI-driven interviews for matched candidates
- delivering only qualified candidates to hiring managers

The platform is designed to reduce manual resume screening and replace unstructured inbound recruiting noise with structured conversational workflows.

### 2.4 Product Positioning

Helly is not a job board. Candidates do not browse open roles manually. The system proactively offers opportunities only when matching quality meets configured thresholds.

## 3. Scope

### 3.1 In Scope for v1

- Telegram bot onboarding for candidates and hiring managers
- candidate profile collection through conversational flow
- vacancy profile collection through conversational flow
- CV and JD ingestion from multiple media types
- AI extraction of structured profile data
- hard-filter + embedding + deterministic + LLM reranking matching pipeline
- interview invitations for shortlisted candidates
- AI-led first-round interview inside Telegram
- automatic candidate evaluation after interview
- manager review and approve/reject workflow
- candidate-manager introduction after approval
- deletion flows for candidate profiles and vacancies
- event logging, raw message storage, and state transition auditing

### 3.2 Out of Scope for v1

- employer web dashboard
- candidate job browsing marketplace
- payment processing
- full ATS synchronization
- calendar scheduling integration
- multi-round interview orchestration beyond the AI first round
- recruiter seat management and RBAC beyond basic manager identity

## 4. Roles and Actors

### 4.1 Candidate

A Telegram user seeking employment.

Candidate capabilities:

- share contact
- choose candidate role
- upload CV or provide work experience in conversational form
- approve or edit AI-generated profile summary
- answer mandatory profile questions
- submit verification video
- accept or skip interview invitations
- complete AI interview
- delete profile

### 4.2 Hiring Manager

A Telegram user representing a company or hiring team.

Hiring manager capabilities:

- share contact
- choose hiring manager role
- create one or more vacancies
- provide job description using supported formats
- answer vacancy clarification questions
- receive only post-interview candidate packages
- approve or reject candidates
- delete vacancies

### 4.3 System

Helly backend services, including:

- Telegram update handler
- conversation state machine
- LLM orchestration layer
- extraction and matching pipeline
- storage layer
- asynchronous job workers
- notification and interview orchestration logic

### 4.4 External Systems

- Telegram Bot API
- LLM provider API
- embedding model provider
- object/file storage
- database
- queue/job runner
- speech-to-text and document text extraction components if separate from the core LLM provider

## 5. Product Principles

### 5.1 Telegram-First

All end-user interaction occurs inside Telegram.

Supported inbound content types:

- text
- document
- voice message
- video message
- video note
- contact
- location

Every inbound and outbound message must be persisted in raw form together with metadata.

### 5.2 Conversational AI with System Control

The system must behave as a conversational assistant, but workflow progression is controlled by deterministic backend logic.

The LLM may:

- interpret intent
- extract structured fields
- summarize content
- generate natural-language responses
- generate clarification prompts

The LLM may not:

- change business state directly
- skip required steps
- bypass validation rules
- approve candidates or vacancies autonomously outside configured business rules

### 5.3 State Machine First

All core journeys must be backed by explicit state machines.

The backend must determine:

- current step
- allowed actions
- required inputs
- retry limits
- completion status

### 5.4 Auditability

Every important business event must be traceable through stored raw messages, parsed artifacts, state transitions, and job execution logs.

## 6. Success Criteria

Helly v1 is considered functionally successful if:

- a candidate can complete onboarding end-to-end inside Telegram
- a hiring manager can create and activate a vacancy end-to-end inside Telegram
- the system can run matching asynchronously and create ranked candidate shortlists
- invited candidates can complete AI interviews inside Telegram
- hiring managers receive structured candidate packages only after interview completion
- approved candidates and managers can be introduced through Telegram

## 7. Assumptions

- Each Telegram account maps to one Helly user account.
- A user can act in one primary role per conversation session, but a shared `User` entity may support both role profiles in storage.
- Telegram chat is the primary user identity channel for v1.
- LLM outputs are probabilistic and must always be validated before state mutation.
- Matching and interview evaluation run asynchronously.

## 8. User Flows

## 8.1 Candidate Flow Overview

1. User starts bot.
2. System requests contact sharing and consent.
3. User selects `Candidate`.
4. User uploads CV or submits equivalent experience input.
5. System extracts and generates structured summary.
6. User approves or edits summary.
7. User answers mandatory profile questions.
8. User submits verification video with phrase.
9. Candidate profile becomes `READY`.
10. Matching engine may later invite the candidate to an interview for a specific vacancy.
11. Candidate accepts or skips.
12. Candidate completes AI interview.
13. Candidate may be auto-rejected, shortlisted to manager, or later approved/rejected by manager.

## 8.2 Hiring Manager Flow Overview

1. User starts bot.
2. System requests contact sharing and consent.
3. User selects `Hiring Manager`.
4. User submits job description.
5. System extracts vacancy structure and inconsistencies.
6. System asks clarification questions.
7. Manager answers required vacancy questions.
8. Vacancy becomes `OPEN`.
9. Matching pipeline runs asynchronously.
10. Candidate interview waves are executed.
11. Manager receives qualified candidate packages.
12. Manager approves or rejects.
13. Approved candidate and manager are introduced.

## 9. Functional Requirements

Each requirement below is mandatory unless marked otherwise.

## 9.1 Identity, Consent, and Session Entry

### FR-001 Contact Sharing

The system must request the user's Telegram contact before role-based onboarding begins.

Acceptance:

- user cannot proceed into candidate or manager flow without contact sharing
- shared contact is stored in structured form
- original contact payload is stored as a raw message artifact

### FR-002 Consent

The system must request user consent before creating a candidate profile or vacancy profile containing personal or business data.

Acceptance:

- consent timestamp is stored
- if consent is declined, no profile is activated

### FR-003 Role Selection

After contact sharing, the system must allow the user to select `Candidate` or `Hiring Manager`.

Acceptance:

- selection is explicit
- role-specific state machine starts only after selection

## 9.2 Candidate Intake

### FR-010 Candidate CV/Experience Input

The system must accept candidate experience in the following formats:

- PDF
- DOCX
- TXT
- pasted text
- voice description

Optional support for video description may be enabled if transcription is available.

Acceptance:

- uploaded file metadata is stored
- extracted text is stored separately from the binary
- original artifact remains retrievable

### FR-011 Candidate Text Extraction

The system must extract text from candidate inputs before profile summarization.

Acceptance:

- OCR/transcription/parsing failures create recoverable error states
- the system asks for resubmission if extraction fails

### FR-012 Candidate Summary Generation

The system must generate a structured candidate summary from CV/experience input.

The summary must include, where available:

- target role
- seniority estimate
- years of experience
- primary skills
- tech stack
- domain experience
- recent roles
- education if present
- languages if present

### FR-013 Candidate Summary Approval

The candidate must review and either approve or edit the generated summary.

Acceptance:

- system shows generated summary in human-readable format
- candidate can approve directly
- candidate can submit corrections
- corrections are merged into the structured summary
- maximum correction loops: 3
- after 3 failed loops, the system must ask for a final confirmation or manual rewrite in free text

### FR-014 Mandatory Candidate Questions

The system must collect the following mandatory candidate fields:

- salary expectations
- current location
- preferred work format

Allowed work format values:

- remote
- hybrid
- office

Supported answer formats:

- text
- voice
- video

Acceptance:

- fields are parsed into structured values
- one follow-up question is allowed per field if needed
- unanswered or invalid mandatory fields block transition to `READY`

### FR-015 Candidate Validation Rules

The system must validate candidate inputs before marking the profile ready.

Validation includes:

- contact exists
- consent exists
- summary approved
- mandatory fields resolved
- verification video completed

## 9.3 Candidate Verification

### FR-020 Verification Phrase Generation

The system must generate a unique short phrase for candidate video verification.

Acceptance:

- phrase is stored with issuance timestamp
- phrase is bound to the current verification attempt

### FR-021 Verification Video Collection

The system must collect a short candidate video message for verification.

Acceptance:

- submitted video is stored in object storage
- Telegram metadata is stored
- linkage between video and phrase is stored

### FR-022 Verification Review Status

For v1, verification may be recorded and passed through to hiring managers even if automated facial/liveness verification is not implemented.

Acceptance:

- verification asset is attached to candidate package
- candidate cannot become `READY` without a submitted verification video

## 9.4 Candidate Ready State

### FR-030 Candidate Ready

The candidate profile must transition to `READY` only when all mandatory profile and verification steps are complete.

Acceptance:

- ready timestamp is stored
- candidate becomes eligible for matching

## 9.5 Vacancy Intake

### FR-040 Vacancy Creation

The system must allow a hiring manager to create one or more vacancies.

Supported input formats:

- text
- document
- voice
- video

### FR-041 Vacancy Extraction

The system must extract structured vacancy data from the submitted job description.

Structured output should include, where available:

- role title
- seniority
- primary tech stack
- secondary tech stack
- project description
- responsibilities
- required skills
- nice-to-have skills
- budget signals
- location constraints
- work format

### FR-042 Vacancy Inconsistency Detection

The system must detect likely inconsistencies or ambiguity in vacancy input.

Examples:

- incompatible tech stacks listed as mandatory without explanation
- mismatched seniority and budget
- unclear role title
- remote role but limited geography without rationale

Acceptance:

- inconsistencies are stored as structured findings
- findings may influence clarification prompts

### FR-043 Vacancy Clarification Questions

The system must collect the following mandatory vacancy fields:

- budget range
- countries allowed for hiring
- work format
- team size
- project description
- primary tech stack

Acceptance:

- answers may be parsed from text, voice, or video
- one follow-up question is allowed per field if required
- vacancy cannot open without all mandatory fields resolved

### FR-044 Vacancy Activation

When all required vacancy information is collected and validated, the vacancy must transition to `OPEN`.

Acceptance:

- open timestamp is stored
- matching job is enqueued automatically

## 9.6 Matching Engine

### FR-050 Matching Trigger

Matching must be triggered when:

- a vacancy becomes `OPEN`
- a candidate becomes `READY`
- relevant candidate or vacancy data changes materially

### FR-051 Hard Filters

The system must apply hard filters before semantic matching.

Required filters:

- location compatibility
- work format compatibility
- salary compatibility
- seniority compatibility

Candidates failing any hard filter must be excluded from the vacancy's active pool.

### FR-052 Embedding Retrieval

The system must transform candidate and vacancy profiles into embeddings and retrieve semantically similar candidates.

Default target:

- top 50 candidates after vector retrieval

This threshold must be configurable.

### FR-053 Deterministic Scoring

The system must score retrieved candidates using deterministic business rules.

Scoring inputs:

- skill overlap
- years of experience
- tech stack match
- seniority fit
- domain fit if available

Default target:

- top 10 candidates passed to LLM reranking

This threshold must be configurable.

### FR-054 LLM Reranking

The system must use an LLM to rerank shortlisted candidates after deterministic scoring.

The LLM output must produce:

- ranked ordering
- concise reasoning
- identified strengths
- identified gaps or risks

Default shortlist size:

- 3 to 6 candidates

This threshold must be configurable per vacancy or globally.

### FR-055 Match Entity Creation

The system must persist match candidates and ranking results.

Each match record must include:

- candidate ID
- vacancy ID
- current match stage
- scores from each stage
- reranking rationale
- invitation status

## 9.7 Interview Invitations

### FR-060 Candidate Invitation

Selected candidates must receive a Telegram invitation to complete an interview for a specific vacancy.

Candidate response options:

- accept interview
- skip opportunity

Acceptance:

- invitation timestamp is stored
- candidate response timestamp is stored

### FR-061 Invite Expiration

Invitations should expire after a configurable period.

Default recommendation:

- 48 hours

Expired invitations may trigger the next wave.

## 9.8 AI Interview

### FR-070 Interview Session Creation

When a candidate accepts an invitation, the system must create an interview session bound to the candidate and vacancy.

### FR-071 Interview Question Set

The system must conduct an AI interview consisting of 5 to 7 vacancy-related questions.

Question generation inputs:

- vacancy profile
- candidate summary
- known risks/gaps from matching

Supported answer formats:

- text
- voice
- video

### FR-072 Follow-Up Rule

If an answer lacks critical information, the system may ask one follow-up question.

Constraints:

- maximum follow-up per question: 1
- follow-up to a follow-up is not allowed

### FR-073 Interview Completion

An interview is complete when all required questions are answered or the session is explicitly abandoned or expired.

Acceptance:

- completion status is stored
- all answers and media artifacts are stored

## 9.9 Interview Waves

### FR-080 Wave-Based Invites

The system must support invitation waves to reduce delay from unresponsive candidates.

Example policy:

- invite 3 candidates in wave 1
- if fewer than 2 complete interviews within the configured SLA, invite the next candidates

Wave rules must be configurable.

### FR-081 No Over-Inviting

The system must not exceed configured concurrent invitation limits for a vacancy unless an override is explicitly configured.

## 9.10 Interview Evaluation

### FR-090 Evaluation Inputs

After interview completion, the system must evaluate the candidate using:

- candidate summary/CV
- interview answers
- vacancy requirements

### FR-091 Evaluation Output

Evaluation must produce:

- final score
- strengths
- risks
- hiring recommendation

### FR-092 Auto-Rejection Threshold

Candidates below a configured threshold must be auto-rejected and not shown to the hiring manager.

Acceptance:

- threshold is configurable
- rejection reason summary is stored

## 9.11 Manager Review

### FR-100 Candidate Package Delivery

The hiring manager must receive a candidate package only after interview completion and evaluation.

The package must include:

- original CV or submitted profile artifact
- candidate summary
- verification video
- interview summary
- evaluation report

### FR-101 Manager Decision

The hiring manager must be able to:

- approve candidate
- reject candidate

Acceptance:

- manager decision and timestamp are stored
- candidate status updates accordingly

## 9.12 Candidate Introduction

### FR-110 Introduction

If approved, Helly must introduce the candidate and hiring manager through Telegram.

For v1, acceptable introduction modes are:

- group chat creation if supported operationally
- mutual contact/message handoff mediated by the bot

The exact introduction mechanism may depend on Telegram technical constraints and bot permissions.

Acceptance:

- introduction event is logged
- both parties receive a confirmation

## 9.13 Deletion Flows

### FR-120 Candidate Deletion

The candidate must be able to delete their profile with confirmation.

Deletion side effects:

- remove candidate from active matching pool
- cancel pending invitations where possible
- cancel active interviews where possible
- mark profile as deleted

Hard physical deletion is optional for v1; soft deletion plus privacy controls is acceptable if legal obligations require retention windows.

### FR-121 Vacancy Deletion

The hiring manager must be able to delete a vacancy with confirmation.

Deletion side effects:

- stop further matching
- cancel pending invitations where possible
- close active interview waves if business rules require
- mark vacancy as deleted

## 9.14 Conversation and UX Rules

### FR-130 Small Talk Handling

The conversational layer may respond to small talk, but the system must preserve onboarding/interview context and resume required steps.

### FR-131 Intent Recovery

If the user sends unsupported or unrelated content during a required step, the system must explain the expected input and keep the current state unchanged.

### FR-132 Multimodal Parsing

Voice and video answers that require structured extraction must be transcribed before parsing.

If transcription confidence is too low, the system must ask for clarification or resubmission.

## 10. State Machines

## 10.1 Candidate Profile States

Candidate profile states:

- `NEW`
- `CONTACT_COLLECTED`
- `CONSENTED`
- `ROLE_CONFIRMED`
- `CV_PENDING`
- `CV_PROCESSING`
- `SUMMARY_REVIEW`
- `MANDATORY_QA`
- `VERIFICATION_PENDING`
- `READY`
- `MATCHED`
- `INTERVIEW_INVITED`
- `INTERVIEW_IN_PROGRESS`
- `INTERVIEW_COMPLETED`
- `UNDER_MANAGER_REVIEW`
- `APPROVED`
- `REJECTED`
- `DELETED`

Rules:

- transitions must be explicit and logged
- invalid transitions must be rejected
- asynchronous processing states must be resumable

## 10.2 Vacancy States

Vacancy states:

- `NEW`
- `INTAKE_PENDING`
- `JD_PROCESSING`
- `CLARIFICATION_QA`
- `OPEN`
- `MATCHING`
- `INTERVIEWING`
- `AWAITING_MANAGER_DECISION`
- `FILLED`
- `CLOSED`
- `DELETED`

## 10.3 Interview Session States

Interview session states:

- `CREATED`
- `INVITED`
- `ACCEPTED`
- `IN_PROGRESS`
- `COMPLETED`
- `EXPIRED`
- `ABANDONED`
- `EVALUATED`

## 11. Data Requirements

## 11.1 Core Entities

The system must support at minimum the following entities:

- `User`
- `CandidateProfile`
- `CandidateVerification`
- `Vacancy`
- `VacancyProfile`
- `Match`
- `InterviewSession`
- `InterviewQuestion`
- `InterviewAnswer`
- `EvaluationResult`
- `File`
- `RawMessage`
- `StateTransitionLog`
- `JobExecutionLog`

## 11.2 Suggested High-Level Schemas

### User

Fields:

- `id`
- `telegram_user_id`
- `telegram_chat_id`
- `phone_number`
- `display_name`
- `role_flags`
- `consent_given_at`
- `created_at`
- `updated_at`

### CandidateProfile

Fields:

- `id`
- `user_id`
- `state`
- `summary_json`
- `salary_expectation`
- `location_text`
- `country_code`
- `work_format`
- `seniority_normalized`
- `primary_skills`
- `embedding_vector_ref`
- `ready_at`
- `deleted_at`
- `created_at`
- `updated_at`

### Vacancy

Fields:

- `id`
- `manager_user_id`
- `state`
- `title`
- `budget_min`
- `budget_max`
- `currency`
- `countries_allowed`
- `work_format`
- `team_size`
- `project_description`
- `primary_stack`
- `required_skills`
- `nice_to_have_skills`
- `seniority_target`
- `embedding_vector_ref`
- `opened_at`
- `deleted_at`
- `created_at`
- `updated_at`

### Match

Fields:

- `id`
- `candidate_profile_id`
- `vacancy_id`
- `hard_filter_pass`
- `embedding_score`
- `deterministic_score`
- `llm_rank_score`
- `llm_reasoning`
- `status`
- `wave_number`
- `invited_at`
- `responded_at`
- `created_at`
- `updated_at`

### InterviewSession

Fields:

- `id`
- `match_id`
- `candidate_profile_id`
- `vacancy_id`
- `state`
- `question_plan_json`
- `started_at`
- `completed_at`
- `expires_at`
- `created_at`
- `updated_at`

### RawMessage

Fields:

- `id`
- `user_id`
- `telegram_update_id`
- `telegram_message_id`
- `direction`
- `content_type`
- `raw_payload_json`
- `text_content`
- `file_id`
- `created_at`

## 11.3 Data Retention

Retention policy must be configurable.

Minimum retention principles:

- raw messages are retained for audit and debugging subject to privacy policy
- deleted profiles must be excluded from active matching immediately
- access to files and transcripts must be restricted

## 12. Technical Architecture Requirements

## 12.1 Architecture Style

Helly v1 should be implemented as a modular backend with asynchronous workers.

Recommended baseline architecture:

- Telegram webhook or long-polling ingestion service
- application API/service layer
- state machine/orchestration layer
- LLM integration layer
- extraction/transcription/document parsing layer
- matching engine
- interview engine
- queue/worker subsystem
- relational database
- object storage
- vector storage or vector-capable database extension

## 12.2 Required Logical Modules

The codebase should be organized into the following modules or equivalent bounded contexts:

- `telegram`
- `identity`
- `conversation`
- `candidate_profile`
- `vacancy`
- `files`
- `llm`
- `matching`
- `interview`
- `evaluation`
- `notifications`
- `storage`
- `jobs`
- `observability`

## 12.3 Integration Boundaries

External provider calls must be encapsulated behind internal interfaces so they can be swapped or mocked in tests.

Required abstractions:

- `TelegramGateway`
- `LLMClient`
- `EmbeddingClient`
- `TranscriptionClient`
- `DocumentParser`
- `FileStorage`
- `QueueClient`

## 13. Telegram Integration Requirements

### TSR-001 Update Handling

Telegram updates must be processed idempotently.

Acceptance:

- duplicate updates do not create duplicate state transitions
- duplicate messages do not create duplicate jobs

### TSR-002 Raw Storage

Every Telegram update must be stored in raw form before or together with business processing.

### TSR-003 Delivery Resilience

Outbound message failures must be retried with backoff.

### TSR-004 UX Constraints

The bot must provide concise prompts, reply markup where useful, and clear recovery when a user sends unexpected content.

## 14. LLM and AI Requirements

### TSR-010 LLM Use Cases

The LLM layer is used for:

- conversation understanding
- response generation
- CV analysis
- JD analysis
- answer parsing
- follow-up generation
- reranking
- interview evaluation

### TSR-011 Guardrails

LLM outputs must never be trusted directly for state mutation.

Required controls:

- structured output schema validation
- fallback handling on malformed output
- deterministic post-validation
- prompt versioning
- model and prompt trace logging

### TSR-012 Prompting Strategy

Prompt assets should be versioned and separated by use case:

- candidate summary extraction
- vacancy extraction
- clarification parsing
- interview question generation
- follow-up generation
- reranking
- evaluation

### TSR-013 Temperature and Determinism

Extraction and parsing tasks should use low-variance settings.

Generative conversational tasks may use higher-variance settings within controlled bounds.

### TSR-014 Cost Control

The system should minimize unnecessary LLM calls by:

- caching stable derived artifacts
- avoiding repeated parsing of unchanged files
- separating cheap classification from expensive reasoning

## 15. Matching Engine Technical Requirements

### TSR-020 Profile Normalization

Candidate and vacancy profiles must be normalized before matching.

Normalization includes:

- canonical skill names
- normalized seniority labels
- normalized work format
- normalized geography representation
- salary range normalization

### TSR-021 Embedding Pipeline

Embeddings must be regenerated when materially relevant profile fields change.

### TSR-022 Async Execution

Matching must run asynchronously and not block user-facing Telegram response time.

### TSR-023 Explainability

Stored match results should include enough metadata to explain why a candidate was or was not shortlisted.

## 16. Interview Engine Technical Requirements

### TSR-030 Question Planning

Interview question planning must use vacancy requirements and candidate gaps to target missing information rather than repeat already known facts.

### TSR-031 Multimodal Answers

Voice and video interview answers must be transcribed before evaluation.

### TSR-032 Session Recovery

If the conversation is interrupted, interview sessions must resume from the last unanswered question.

### TSR-033 Timeouts

Interview sessions must support expiration and reminder logic.

## 17. Evaluation Requirements

### TSR-040 Evaluation Structure

Evaluation results must be stored in structured and human-readable forms.

Minimum structured fields:

- `final_score`
- `recommendation`
- `strengths[]`
- `risks[]`
- `missing_requirements[]`
- `summary_text`

### TSR-041 Threshold Configuration

Auto-rejection and manager delivery thresholds must be configurable globally and overridable per vacancy if needed.

## 18. Non-Functional Requirements

## 18.1 Reliability

- Telegram updates must be processed idempotently.
- State transitions must be atomic.
- Job execution must be retry-safe.
- Partial failures must not corrupt profile or vacancy state.

## 18.2 Scalability

The system must support at least:

- 10,000 candidate profiles
- 1,000 active vacancies

Matching and evaluation workloads must run asynchronously and scale horizontally through workers.

## 18.3 Performance

Target response times:

- 1 to 3 seconds for normal conversational replies
- under 10 seconds for simple parsing flows where synchronous confirmation is needed
- longer-running tasks must return acknowledgment immediately and continue asynchronously

## 18.4 Observability

The system must log:

- inbound updates
- outbound messages
- state transitions
- parsing attempts
- LLM calls and prompt versions
- matching events
- interview events
- evaluation outcomes
- error events

The system should expose:

- structured logs
- metrics
- trace or correlation IDs

## 18.5 Security

- sensitive data must be stored securely
- secrets must not be hardcoded
- file access must be authenticated and time-limited where applicable
- user consent must be recorded
- least-privilege access must be applied to storage and infrastructure

## 18.6 Privacy

- personal data processing must be documented
- deletion requests must stop active processing promptly
- exported candidate data shown to managers must be limited to business-relevant information

## 18.7 Maintainability

- code must be modular
- external integrations must be interface-driven
- prompt assets must be version-controlled
- core business flows must be covered by automated tests

## 19. Error Handling Requirements

### TSR-050 User-Facing Failures

When parsing, transcription, or generation fails, the user must receive a recovery message with a next action.

### TSR-051 Internal Failures

Internal failures must be logged with correlation IDs and retried where safe.

### TSR-052 Poison Events

Events that repeatedly fail processing must be quarantined or dead-lettered for operator review.

## 20. Configuration Requirements

The following values must be configurable without code changes or with environment-driven config:

- supported languages
- correction loop limits
- clarification follow-up limits
- interview length
- invitation expiration
- wave size
- concurrent invite cap
- matching thresholds
- evaluation thresholds
- LLM model selection
- retry policies
- retention windows

## 21. Security and Compliance Controls

Minimum controls for v1:

- encrypted transport for all external calls
- encrypted storage for sensitive file/object storage where supported
- access logging for administrative actions
- data access separation between user-facing bot logic and internal operator tooling if operator tooling exists

## 22. Suggested API and Internal Contract Shape

The exact implementation is flexible, but the internal system should support these conceptual operations:

- `ingestTelegramUpdate(update)`
- `processInboundMessage(messageId)`
- `startCandidateFlow(userId)`
- `submitCandidateCV(profileId, fileId | text)`
- `approveCandidateSummary(profileId)`
- `updateCandidateSummary(profileId, patch)`
- `submitCandidateMandatoryAnswer(profileId, field, value)`
- `submitVerificationVideo(profileId, fileId)`
- `createVacancy(managerId, sourceInput)`
- `submitVacancyMandatoryAnswer(vacancyId, field, value)`
- `activateVacancy(vacancyId)`
- `runMatchingForVacancy(vacancyId)`
- `inviteCandidate(matchId)`
- `startInterview(matchId)`
- `submitInterviewAnswer(sessionId, questionId, payload)`
- `evaluateInterview(sessionId)`
- `approveCandidate(matchId, managerId)`
- `rejectCandidate(matchId, managerId)`
- `deleteCandidateProfile(profileId)`
- `deleteVacancy(vacancyId)`

## 23. Testing Requirements

The implementation must include automated tests for:

- Telegram update deduplication
- state machine transition validation
- candidate onboarding happy path
- vacancy onboarding happy path
- parsing validation and recovery
- matching hard-filter logic
- interview follow-up limit enforcement
- deletion side effects
- idempotent job retries

Recommended additional coverage:

- prompt contract validation
- model fallback behavior
- message formatting snapshots
- queue retry/dead-letter behavior

## 24. Acceptance Criteria by Milestone

## 24.1 MVP Functional Acceptance

MVP is accepted when:

- candidate can complete profile creation inside Telegram
- manager can create and open a vacancy inside Telegram
- matching produces ranked candidate shortlist records
- interview invitations can be sent and accepted
- AI interview can be completed inside Telegram
- evaluation is produced automatically
- manager can approve or reject a candidate

## 24.2 MVP Technical Acceptance

MVP is accepted technically when:

- duplicate Telegram updates are safe
- raw messages are stored
- asynchronous jobs are retry-safe
- all core state transitions are logged
- critical paths have automated test coverage

## 25. Implementation Priorities

Recommended implementation order:

1. Telegram ingestion, user identity, consent, and raw message storage
2. Candidate onboarding state machine
3. Vacancy onboarding state machine
4. File extraction and LLM structured parsing
5. Matching pipeline
6. Interview invitation and interview engine
7. Evaluation and manager review
8. Introduction flow, deletion flows, and hardening

## 26. Open Product Decisions

The following decisions should be confirmed during implementation planning because they affect architecture and UX:

- exact languages supported in v1
- whether a user may simultaneously operate as candidate and manager in one bot identity
- introduction mechanism allowed by Telegram permissions and product policy
- whether automated verification checks beyond storing the video are required in v1
- whether candidates receive explicit rejection explanations
- legal retention windows and deletion semantics by jurisdiction

## 27. Future Extensions

Potential post-v1 features:

- company profiles
- recruiter teams and permissions
- multi-stage interviews
- calendar integration
- ATS integrations
- analytics dashboard
- feedback loops for model quality
- human recruiter review console

## 28. Summary

Helly v1 is a Telegram-native AI recruiting system built around controlled conversational flows, structured data extraction, asynchronous matching, and AI-led first-round screening.

The defining architectural constraint is that the conversational layer must remain subordinate to deterministic state machines and validated business logic. Every major user action must be traceable, resumable, and safe under retries.
