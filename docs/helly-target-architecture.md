# Helly v1 Target Architecture

## 1. Product Overview

### What Helly is
Helly is a Telegram-first AI-powered recruitment platform that operates through guided conversational workflows. It supports two primary roles:
- Candidate
- Hiring Manager

The product goal is to automate and control the full pipeline from profile/vacancy intake to interview, evaluation, and candidate-manager connection.

### Candidate role
A candidate interacts with the bot to:
1. Upload CV (file/photo/text-derived data).
2. Receive AI-generated profile summary.
3. Approve or edit summary.
4. Answer mandatory constraints (salary expectation, location, work format).
5. Complete video verification.
6. Become ready for matching.
7. Complete role-specific interviews when invited.

Candidates do not browse vacancies manually; the system pushes relevant opportunities.

### Hiring Manager role
A hiring manager interacts with the bot to:
1. Create one or more vacancies from text/file/voice/video job descriptions.
2. Answer clarification questions (budget, allowed countries, work format, team, project, stack).
3. Trigger matching.
4. Review candidate packages after interview/evaluation.
5. Approve or reject candidates.
6. If approved, initiate candidate-manager connection via bot.

### High-level platform logic
1. Intake (candidate profile + manager vacancy).
2. Structured enrichment (mandatory fields + clarifications).
3. Hybrid matching (hard filters -> embedding retrieval -> deterministic scoring -> LLM rerank).
4. Interview invitation and wave execution.
5. Final evaluation and candidate package delivery.
6. Manager decision.
7. Connection or rejection handling.

---

## 2. Core Architecture Principles

1. Telegram-first
   - Telegram update stream is the primary interaction interface.
   - Supported modalities: buttons, text, voice, file, video.

2. LLM everywhere for conversation quality, not control authority
   - LLM is used for extraction, summarization, intent hints, reranking, and explanation.
   - LLM output must be treated as untrusted suggestions.

3. State engine is the source of truth
   - Backend state machine owns legal transitions.
   - No state transition may happen outside the state engine.

4. No direct state changes from LLM
   - LLM cannot mutate workflow state directly.
   - LLM outputs are mapped into typed commands, validated, then routed through transition guards.

5. Modular architecture by domain
   - Candidate, manager, matching, interview, deletion, and shared infrastructure are isolated.
   - Each module exposes explicit use-cases and contracts.

6. Queue-based heavy processing
   - CPU/API expensive or long-running work runs in async workers.
   - Webhook path stays fast and deterministic.

7. DB-first persistence
   - Canonical state/entities live in database repositories.
   - Local files may be used only as controlled caches or temporary assets, not source of truth.

---

## 3. Main Flows

### 3.1 Candidate onboarding flow
1. Candidate starts onboarding.
2. CV received and stored.
3. CV analysis job extracts structured profile draft.
4. Candidate reviews AI summary.
5. Candidate approves or edits summary.
6. Candidate answers mandatory constraints:
   - salary expectation
   - location/country
   - work format
7. Candidate completes video verification.
8. State becomes `candidate_ready_for_matching`.

State notes:
- Every step is explicit and resumable.
- Missing mandatory fields block readiness transition.

### 3.2 Hiring manager vacancy creation flow
1. Manager starts vacancy creation.
2. Job description received (text/file/voice/video).
3. JD analysis job extracts structured vacancy draft.
4. Manager answers clarification questions:
   - budget
   - allowed countries
   - work format
   - team
   - project
   - stack
5. Vacancy saved as active and matchable.
6. Manager may repeat flow to create additional vacancies.

State notes:
- Vacancy lifecycle is independent per vacancy.
- Manager has a workspace of vacancies, one active conversation context at a time.

### 3.3 Matching flow
1. Trigger: candidate-ready event, vacancy-ready event, or scheduled recompute.
2. Hard filtering removes incompatible pairs.
3. Embedding retrieval produces shortlist.
4. Deterministic scoring computes final structured score.
5. LLM reranking adjusts order within bounded policy.
6. Candidate receives interview invite for selected vacancy.

State notes:
- Matching decision is persisted with traceable score components.
- Matching itself does not skip interview gate.

### 3.4 Interview wave flow
1. Eligible candidate-vacancy pairs enter interview queue.
2. Wave scheduler batches invites per vacancy and policy limits.
3. Candidate can have only one active interview at a time.
4. Interview engine runs main + optional follow-up questions.
5. Answers are evaluated and interview status finalized.

State notes:
- Wave policy controls concurrency and pacing.
- Follow-up constraint: max one follow-up per main question.

### 3.5 Final evaluation flow
1. Interview result and candidate profile are assembled into candidate package.
2. Package sent to hiring manager for decision.
3. Manager approves or rejects.
4. If approved, bot shares connection details (or opens mutual contact flow).
5. If rejected, candidate returns to matchable pool according to policy.

### 3.6 Deletion flows
#### Candidate deletion
1. Candidate requests profile deletion.
2. Bot requests confirmation.
3. On confirm, system performs cleanup jobs (profile, vectors, files, pending processes).
4. State transitions to deleted/closed.

#### Vacancy deletion
1. Manager requests vacancy deletion.
2. Bot requests confirmation.
3. On confirm, system cancels pending interview invites/jobs tied to vacancy and marks vacancy deleted.
4. Other manager vacancies remain intact.

---

## 4. Core Domain Modules

### Telegram adapter
Responsibilities:
- Normalize Telegram updates into internal message/event model.
- Map callbacks/buttons/media into typed interaction inputs.
- Send outbound messages/media with retry/idempotency wrappers.

### State engine
Responsibilities:
- Own finite state models for candidate, manager, vacancy, interview session.
- Validate transition rules and guard conditions.
- Persist transition history for audit/debug.

### Candidate module
Responsibilities:
- Onboarding orchestration.
- CV intake + profile draft lifecycle.
- Mandatory field collection and readiness checks.

### Manager module
Responsibilities:
- Vacancy draft creation/update/activation.
- Clarification Q&A loop.
- Multi-vacancy management for a single manager.

### Matching module
Responsibilities:
- Pair generation and hard filtering.
- Vector retrieval and shortlist selection.
- Deterministic scoring and ranking.
- LLM rerank integration with bounded controls.

### Interview module
Responsibilities:
- Interview invitation lifecycle.
- Question plan generation.
- Answer evaluation and final interview scoring.
- Wave scheduling constraints and candidate exclusivity.

### Deletion module
Responsibilities:
- Candidate and vacancy deletion workflows with confirmation.
- Cascading cleanup orchestration.
- Compliance-safe audit records.

### LLM service layer
Responsibilities:
- Provide typed LLM capabilities: summarize/extract/classify/rerank/evaluate.
- Apply prompt templates + model routing.
- Enforce schema validation and safety fallbacks.

### Queue/workers
Responsibilities:
- Execute asynchronous domain jobs.
- Retry with idempotency keys.
- Report job status/events back to orchestrator.

### Repositories/data layer
Responsibilities:
- DB-first entity persistence.
- Transaction boundaries for multi-entity updates.
- Query interfaces optimized per module use-case.

### Storage/transcription layer
Responsibilities:
- Store CV/audio/video files.
- Handle transcription for voice/video.
- Return normalized artifacts to domain modules.

---

## 5. Target Folder Structure

```text
src/
  bootstrap/
    app.ts
    container.ts

  adapters/
    telegram/
      webhook.controller.ts
      update-normalizer.ts
      telegram.client.ts
      callback-map.ts

  core/
    events/
      domain-events.ts
      command-types.ts
    state/
      state-engine.ts
      transition-rules.ts
      guard-rules.ts
      state-types.ts

  modules/
    candidate/
      candidate.controller.ts
      candidate.flow.ts
      candidate.service.ts
      candidate.states.ts
    manager/
      manager.controller.ts
      vacancy.flow.ts
      vacancy.service.ts
      vacancy.states.ts
    matching/
      matching.orchestrator.ts
      hard-filters.ts
      retrieval.service.ts
      scoring.service.ts
      rerank.service.ts
    interview/
      interview.orchestrator.ts
      interview.service.ts
      wave.scheduler.ts
      evaluation.service.ts
    deletion/
      deletion.orchestrator.ts
      candidate-deletion.service.ts
      vacancy-deletion.service.ts

  services/
    llm/
      llm.gateway.ts
      llm.schemas.ts
      prompt-registry.ts
    storage/
      file-storage.service.ts
      transcription.service.ts

  infrastructure/
    db/
      client/
      repositories/
      migrations/
    queue/
      queue.client.ts
      job-types.ts
      enqueue.service.ts

  workers/
    cv-analysis.worker.ts
    jd-analysis.worker.ts
    transcription.worker.ts
    matching.worker.ts
    rerank.worker.ts
    interview-generation.worker.ts
    final-evaluation.worker.ts
    reminders.worker.ts
    deletion-cleanup.worker.ts

  api/
    admin/

  shared/
    observability/
    utils/
    contracts/
```

Notes:
- Structure is target-state guidance; migration will be incremental.
- Existing files remain until each responsibility is safely extracted.

---

## 6. Domain Invariants

Non-negotiable rules:
1. One hiring manager can have many vacancies.
2. One candidate can match many vacancies.
3. One candidate can have only one active interview at a time.
4. One vacancy can have multiple active interview invites, constrained by wave policy.
5. Follow-up limit: maximum one follow-up question per main question.
6. Deletion operations (candidate/vacancy) must require explicit confirmation.
7. State transitions must go through the state engine only.
8. LLM outputs cannot directly mutate workflow state.
9. Mandatory candidate fields are required before matchable status.
10. Vacancy clarifications are required before vacancy enters active matching pool.

Enforcement locations:
- State transitions: state engine guards.
- Cross-entity uniqueness/concurrency: DB constraints + repository checks.
- Interview exclusivity and wave limits: interview module + queue scheduler.

---

## 7. Async Jobs

Required worker jobs:
1. CV analysis
   - Input: candidate CV asset reference
   - Output: structured candidate draft profile

2. JD analysis
   - Input: vacancy description assets/content
   - Output: structured vacancy draft

3. Transcription
   - Input: voice/video asset reference
   - Output: transcript text + confidence metadata

4. Matching
   - Input: candidate/vacancy trigger event
   - Output: shortlisted candidate-vacancy pairs

5. Reranking
   - Input: deterministic shortlist with features
   - Output: reranked shortlist + rationale

6. Interview generation
   - Input: candidate-vacancy pair and context
   - Output: interview question plan

7. Final evaluation
   - Input: interview answers + profile/vacancy context
   - Output: final score/band + package payload

8. Reminders
   - Input: pending step/interview deadlines
   - Output: outbound reminder events/messages

9. Deletion cleanup
   - Input: confirmed candidate/vacancy deletion request
   - Output: cascaded cleanup completion event

Job requirements:
- Idempotency key per domain object + operation.
- Retry policy with dead-letter handling.
- Structured status tracking in DB.

---

## 8. Migration Strategy

Migration goals:
- Keep current bot operational.
- Avoid destructive changes.
- Move to modular architecture in vertical slices.

Phased approach:
1. Baseline and lock behavior
   - Add characterization tests around critical flows.
   - Document current state/event map.

2. Introduce target contracts without rewiring runtime
   - Add core event/command/state contracts.
   - Add module boundaries and interfaces.

3. Add async infrastructure in parallel
   - Implement queue abstraction and workers.
   - Keep existing synchronous paths as fallback until parity is proven.

4. Additive data model evolution
   - Introduce vacancy model supporting one manager to many vacancies.
   - Keep compatibility with existing job/profile data during transition.

5. Strangler extraction from monolithic router
   - Extract one flow at a time (candidate, manager, matching, interview).
   - Route extracted flows through new module entrypoints behind feature flags.

6. Shift heavy tasks to workers
   - Move analysis/matching/rerank/evaluation off webhook path.
   - Ensure idempotent enqueueing.

7. Harden invariants
   - Enforce one active interview per candidate and wave limits in DB + service guards.

8. Decommission legacy internals gradually
   - After parity tests and production soak, retire deprecated paths.

Safety controls throughout:
- No `.env` or secret changes.
- No deletion of existing files during early phases.
- Rollout with feature flags and observability metrics.

---

## 9. Immediate Refactor Priorities

Ordered, safe, implementation-oriented steps:
1. Add this architecture document and treat it as reference baseline.
2. Add a current-flow inventory document (states, transitions, key handlers).
3. Add characterization tests for candidate onboarding and manager vacancy creation.
4. Add characterization tests for deletion confirmation paths.
5. Introduce typed domain command/event contracts (no runtime switch yet).
6. Implement queue interface with initial in-memory or adapter-backed implementation.
7. Extend Telegram normalized update model for video/video-note support.
8. Add additive DB schema for `vacancies` (manager -> many vacancies), without removing current tables.
9. Implement new `VacancyRepository` and compatibility mapping layer.
10. Extract first minimal manager-vacancy flow into a dedicated module behind feature flag.
11. Add worker pipeline for CV/JD analysis while keeping synchronous fallback.
12. Add interview wave scheduler skeleton with invariant checks (no full rollout yet).

Definition of done for immediate phase:
- No production behavior regression in baseline tests.
- New contracts/modules exist and are usable.
- Existing runtime path remains intact and deployable.
