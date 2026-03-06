# Matching & Interview Lifecycle Inventory (Legacy -> Canonical)

This document inventories current legacy lifecycle behavior for matching/interview orchestration and proposes a compatibility mapping toward canonical contracts in `src/core/matching/`.

Scope of this inventory:
- Analysis only (no runtime behavior changes).
- Legacy values observed in code and schema.
- Canonical mapping proposal for gradual refactor.

Reference canonical contracts:
- `src/core/matching/match-statuses.ts`
- `src/core/matching/interview-statuses.ts`
- `src/core/matching/evaluation-statuses.ts`
- `src/core/matching/matching-events.ts`

## 1. Current Legacy Match Lifecycle

### 1.1 Observed match lifecycle fields

Legacy match lifecycle is currently represented by a combination of fields, not by one strict status machine:

1. `matches.status` (`MatchRecord.status`)
- Source: `src/decisions/match.types.ts`, `src/storage/match-storage.service.ts`
- Values: `proposed`, `candidate_applied`, `candidate_rejected`, `manager_accepted`, `manager_rejected`, `contact_pending`, `contact_shared`, `closed`

2. `matches.candidate_decision`
- Source: `src/decisions/match.types.ts`, `src/storage/match-storage.service.ts`
- Values: `pending`, `applied`, `rejected`

3. `matches.manager_decision`
- Source: `src/decisions/match.types.ts`, `src/storage/match-storage.service.ts`
- Values: `pending`, `accepted`, `rejected`

4. User/session state used as decision-stage proxy
- Source: `src/shared/types/state.types.ts`, `src/notifications/notification.engine.ts`
- Values relevant to match decision UX: `waiting_candidate_decision`, `waiting_manager_decision`, `contact_shared`

5. Job status gating match actions
- Source: `src/db/repositories/jobs.repo.ts`
- Values: `draft`, `active`, `paused`, `closed`
- In decision flow, manager/candidate actions are validated against job status via `DecisionService.ensureJobActive`.

### 1.2 Observed legacy match statuses and usage

| Legacy value | Where set | Where validated/used | Notes |
|---|---|---|---|
| `proposed` | `MatchStorageService.createForJob` | Candidate can act only in this status (`DecisionService.ensureCandidateCanActOnMatch`) | Initial status for newly stored match records |
| `candidate_applied` | `applyCandidateDecision("applied")` | Manager can act only in this status (`ensureManagerCanActOnMatch`) | Candidate accepted interest |
| `candidate_rejected` | `applyCandidateDecision("rejected")` | Checked by matching history logic (`hasCandidateRejectedSameJob`) | Candidate declined |
| `manager_accepted` | `applyManagerDecision("accepted")` | Consent callbacks require this status | Manager accepted candidate |
| `manager_rejected` | `applyManagerDecision("rejected")` | Checked by matching history logic (`hasManagerSkippedSameCandidate`) | Manager declined |
| `contact_pending` | `setContactPending` exists in storage | No observed runtime caller | Currently dead/unreached status |
| `contact_shared` | `markContactShared` | Terminal check in `DecisionService.markContactShared`; admin stats | Contact exchange completed |
| `closed` | Type union only | No observed writer/transition | Currently dead/unreached status |

### 1.3 Observed transition points

Primary mutation points:

1. Match creation
- `MatchingEngine` creates records via `MatchStorageService.createForJob(...)`
- Sources: `src/matching/matching.engine.ts`, `src/router/state.router.ts` (`publishManagerMatches`)

2. Candidate decision
- `DecisionService.candidateApply` -> `candidate_applied`
- `DecisionService.candidateReject` -> `candidate_rejected`
- Entrypoints: callback buttons and text-driven action dispatch (`CallbackRouter.executeMatchAction`)

3. Manager decision
- `DecisionService.managerAccept` -> `manager_accepted`
- `DecisionService.managerReject` -> `manager_rejected`

4. Contact exchange completion
- `DecisionService.markContactShared` -> `contact_shared`
- Trigger path: consent callbacks in `CallbackRouter`

Session-state transitions associated with match UX:
- `NotificationEngine.notifyCandidateOpportunity` -> `waiting_candidate_decision`
- `NotificationEngine.notifyManagerCandidateApplied` -> `waiting_manager_decision`
- `NotificationEngine.notifyContactsShared` -> both sides `contact_shared`

### 1.4 Important legacy inconsistency

Admin metrics currently count `candidate_decision === "apply"`, but runtime writes `"applied"`.
- Source: `src/admin/admin-webapp.service.ts` (`candidatesApplied` metric)
- Source of truth values: `src/decisions/match.types.ts`

This makes one admin metric incorrect and indicates status vocabulary drift.

## 2. Current Legacy Interview Lifecycle

### 2.1 Runtime interview lifecycle signals

Interview lifecycle is currently represented by session state + payload markers:

1. Session states
- Candidate track: `waiting_resume` -> `extracting_resume` -> `interviewing_candidate` -> `candidate_profile_ready`
- Manager track: `waiting_job` -> `extracting_job` -> `interviewing_manager` -> `job_profile_ready`
- Source: `src/shared/types/state.types.ts`, `src/state/transition-rules.ts`, `src/router/state.router.ts`

2. Interview runtime markers in session payload
- `interviewPlan` (presence = active context)
- `interviewStartedAt`, `interviewCompletedAt`
- `currentQuestionIndex`, `pendingFollowUp`, `skippedQuestionIndexes`
- `answers[]` where each answer has `status: draft | final`
- Source: `src/state/state.service.ts`, `src/shared/types/state.types.ts`

3. Per-answer result kinds (transient lifecycle states)
- `next_question`
- `reanswer_required`
- `completed`
- Source: `InterviewEngine.submitAnswer` return type in `src/interviews/interview.engine.ts`

### 2.2 Interview persistence layers

1. File persistence
- Completed interviews saved to `data/interviews/*.json`
- Source: `src/storage/interview-storage.service.ts`

2. Supabase persistence
- Completed interviews inserted into `interview_runs`
- Source: `src/db/repositories/interviews.repo.ts`, migration `src/db/migrations/003_interview_runs.sql`

3. Legacy table not used by runtime writer
- Migration defines `public.interviews` with `status in ('active','completed','abandoned')`
- Source: `src/db/migrations/019_interviews_table.sql`
- Current repository writes `interview_runs` only, not `interviews`

### 2.3 Observed interview status vocabularies

1. Answer-level status
- `draft`, `final`
- Source: `InterviewAnswer.status`

2. Legacy DB status vocabulary (table-level, currently not wired)
- `active`, `completed`, `abandoned`

3. Admin-derived interview progress status (computed, not persisted)
- `not_started`, `in_progress`, `completed`
- Source: `resolveInterviewStatus(...)` in `src/admin/admin-webapp.service.ts`

### 2.4 Transition ownership

Interview transitions happen in multiple places:
- Router sets extracting/interviewing states (`StateRouter` document/text intake branches)
- `InterviewEngine` computes completion result and completed target state
- Router performs final `stateService.transition(...)` based on engine result

So interview lifecycle is split between router orchestration and engine output, not centralized in one lifecycle service.

## 3. Current Evaluation Outcomes

No single canonical evaluation status currently exists in runtime. Instead, evaluation/recommendation is distributed across several fields:

1. Resume analysis profile status
- `analysis_ready`, `rejected_non_technical`
- Source: `CandidateResumeAnalysisService`, `ProfilesRepository`

2. Candidate interview confidence
- `interview_confidence_level`: `low`, `medium`, `high`
- Source: `CandidateTechnicalSummaryV1`

3. Answer quality / authenticity signals
- `should_request_reanswer`, `ai_assisted_likelihood`, `ai_assisted_confidence`
- Source: `AnswerEvaluatorService`

4. Matching decision output (notification strategy, not lifecycle status)
- `notify_candidate`, `notify_manager`, `priority`, cooldown values
- Source: `MatchingDecisionService`

5. Deterministic match score
- Numeric score bands drive eligibility and notifications
- Source: `matching-score.v2`, `MatchingEngine`

Inference: there is no persisted field equivalent to canonical `EvaluationStatus` (`STRONG`/`POSSIBLE`/`WEAK`) yet.

## 4. Canonical Mapping Proposal

### 4.1 MatchStatus mapping proposal

Proposed compatibility mapping to `src/core/matching/match-statuses.ts`:

| Legacy signal | Canonical `MatchStatus` | Mapping confidence | Note |
|---|---|---|---|
| `status = proposed` | `PROPOSED` | High | Initial stored match record |
| `status = candidate_rejected` | `DECLINED` | High | Candidate declined |
| `status = candidate_applied` | `SENT_TO_MANAGER` | Medium | Candidate accepted and sent to manager review |
| `status = manager_rejected` | `REJECTED` | High | Manager rejected candidate |
| `status = manager_accepted` | `APPROVED` | Medium | Manager approved candidate (pre-contact exchange completion) |
| `status = contact_pending` | `APPROVED` | Low | Intended consent/contact intermediate state but currently unused |
| `status = contact_shared` | `APPROVED` | Medium | Contact exchange completed after manager approval |
| `status = closed` | `REJECTED_BY_SYSTEM` | Low | No observed runtime usage |

Additional proposed derived mapping:
- If notification sent and no explicit decision yet, legacy still remains `proposed`; canonical shadow may use `INVITED` only after introducing an explicit invitation event field.

### 4.2 InterviewStatus mapping proposal

Because runtime has no single interview status column, mapping must be derived from signals:

| Legacy signal | Canonical `InterviewStatus` |
|---|---|
| `session.state in {interviewing_candidate, interviewing_manager}` and `interviewPlan exists` | `IN_PROGRESS` |
| `interviewStartedAt exists` and active state | `STARTED` |
| `interviewCompletedAt exists` or row in `interview_runs` | `COMPLETED` |
| Legacy table `interviews.status = active` (if ever used) | `IN_PROGRESS` |
| Legacy table `interviews.status = completed` | `COMPLETED` |
| Legacy table `interviews.status = abandoned` | `DROPPED` |

Current code has no explicit legacy equivalent for:
- `INVITED`
- `DECLINED`
- `CANCELLED_BY_MANAGER`
- `CANCELLED_BY_CANDIDATE`

### 4.3 EvaluationStatus mapping proposal

`EvaluationStatus` currently must be inferred:

1. From candidate technical summary confidence
- `high` -> `STRONG`
- `medium` -> `POSSIBLE`
- `low` -> `WEAK`

2. From resume analysis gate
- `rejected_non_technical` -> `WEAK`

3. Optional score-band fallback when confidence is absent
- `score >= 85` -> `STRONG`
- `70 <= score < 85` -> `POSSIBLE`
- `score < 70` -> `WEAK`

Inference note: these mappings are compatibility heuristics until a dedicated evaluation status is persisted explicitly.

## 5. Gaps and Risks

1. Lifecycle split across multiple fields and services
- Match lifecycle uses `status` + `candidate_decision` + `manager_decision` + session `state`.
- Interview lifecycle uses session state, payload markers, and completed-run storage.

2. Dead or unused legacy statuses
- `contact_pending` and `closed` are defined but not actively used in observed runtime transitions.

3. Schema/runtime drift for interview persistence
- Migration `019_interviews_table.sql` defines `interviews` with status, but runtime persists only to `interview_runs`.

4. Admin metric vocabulary mismatch
- Admin counts `candidate_decision === "apply"`, runtime writes `"applied"`.

5. Missing explicit invitation lifecycle persistence
- Candidate/manager decision stages are represented by session states, but invitation-delivery state is not explicitly persisted on match record.

6. Canonical interview cancellation/decline states have no legacy equivalent
- Makes direct mapping partial until explicit fields/events are introduced.

7. No centralized transition guard for match lifecycle
- Transitions are performed in storage/decision/notification/router layers.

8. No explicit persisted `EvaluationStatus`
- Evaluation outcome currently inferred from heterogeneous signals.

## 6. Recommended Refactor Order

1. Lock compatibility contract (read-only)
- Keep legacy behavior unchanged.
- Introduce one typed compatibility map (legacy -> canonical) as documentation/constants only.

2. Add non-invasive lifecycle telemetry
- Emit structured logs/events on every match/interview transition attempt.
- Verify actual production transition frequencies before rewriting.

3. Normalize match lifecycle first (shadow mode)
- Compute canonical match status from legacy fields in one adapter.
- Do not replace legacy columns yet; only add read path adapter.

4. Introduce explicit invitation markers
- Add persisted `invited_at` / `invite_sent` (or equivalent) in shadow read model.
- This closes `PROPOSED` vs `INVITED` ambiguity.

5. Centralize interview status derivation

## 7. Runtime Seam Analysis: `SEND_TO_MANAGER`

### 7.1 Interview completion finalized

Interview completion is finalized in interview orchestration and then persisted into session/profile-ready state:
- `InterviewEngine` returns `completedState` (`candidate_profile_ready` / `job_profile_ready`)
- `StateRouter` applies that transition and follow-up messaging

Relevant points:
- `src/interviews/interview.engine.ts`
- `src/router/state.router.ts` (`result.completedState` handling)

### 7.2 Evaluation readiness considered

Evaluation-like readiness signals are distributed:
- candidate technical summary / confidence
- answer evaluator signals
- profile status (`analysis_ready`, `rejected_non_technical`)

There is no single persisted canonical "evaluation ready" flag that owns manager-delivery gating yet.

### 7.3 Candidate actually sent/shown to manager

Current manager-review delivery is split across at least two runtime paths:

1. Push notification path
- `CallbackRouter.handleCandidateApply` / `executeMatchAction(candidate_apply)`
- `DecisionService.candidateApply`
- `NotificationEngine.notifyManagerCandidateApplied`

2. Pull/read path for manager
- `StateRouter.showTopMatchesWithActions` when manager requests "show matches"
- manager can be shown candidate cards from stored matches independently of push notify

### 7.4 Conclusion for current step

No single safe seam currently owns `INTERVIEW_COMPLETED -> SENT_TO_MANAGER` end-to-end.
Because delivery is split across push and pull paths and evaluation readiness is not centralized, canonical `sendToManager(...)` remains temporary sidecar telemetry at candidate-apply time for now.

Planned future owner seam:
- a dedicated match/interview orchestration layer that:
  - receives interview/evaluation-ready signal
  - decides manager-delivery once
  - emits one canonical `SEND_TO_MANAGER` transition
  - drives both push notify and manager read visibility consistently
- Add one resolver that derives canonical interview status from session + interview_runs.
- Keep current interview engine/router behavior unchanged.

6. Add explicit evaluation normalization layer
- Derive `EvaluationStatus` from existing confidence/score/profile flags in one place.
- Keep raw legacy signals intact for auditability.

7. Move transition writes behind orchestration service (incremental)
- First for match status writes, then interview status writes.
- Preserve existing APIs as wrappers during migration.

8. Enforce invariants at orchestration boundary
- Candidate max one active interview.
- Evaluation cannot complete before interview completion.

9. Decommission dead statuses and stale schema paths
- After parity checks, remove/retire `contact_pending`, `closed` if still unused.
- Align migrations/docs around one interview persistence model.

10. Only then wire canonical statuses into runtime state engine
- Switch from inferred shadow mapping to canonical source-of-truth fields.
