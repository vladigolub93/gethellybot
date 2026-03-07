# Legacy Lifecycle Drift Inventory and Cleanup Plan

This document captures the current lifecycle drift after introducing canonical sidecars (`MatchLifecycleService`, `InterviewLifecycleService`, `ManagerExposureService`) and defines a safe cleanup order.

Scope:
- Analysis and planning only.
- No runtime behavior changes.
- No persistence changes.

## 1. Current legacy lifecycle write points

### A. Match lifecycle drift

#### A.1 Primary write points

| Write point | File | Legacy fields written |
|---|---|---|
| Match creation | `src/storage/match-storage.service.ts` (`createForJob`) | `status=proposed`, `candidateDecision=pending`, `managerDecision=pending` |
| Candidate apply/reject | `src/storage/match-storage.service.ts` (`applyCandidateDecision`) via `src/decisions/decision.service.ts` | `candidateDecision`, `status=candidate_applied|candidate_rejected` |
| Manager accept/reject | `src/storage/match-storage.service.ts` (`applyManagerDecision`) via `src/decisions/decision.service.ts` | `managerDecision`, `status=manager_accepted|manager_rejected` |
| Contact shared on match | `src/storage/match-storage.service.ts` (`markContactShared`) via `src/decisions/decision.service.ts` | `status=contact_shared` |
| Match persistence mirror | `src/db/repositories/matches.repo.ts` | persists legacy `status`, `candidate_decision`, `manager_decision` |

#### A.2 Legacy inference points (not writes)

| Inference point | File | Drift risk |
|---|---|---|
| Candidate action gate (`status === proposed`) | `src/decisions/decision.service.ts` | Canonical service expects `INVITED` before candidate accepts/declines |
| Manager action gate (`status === candidate_applied`) | `src/decisions/decision.service.ts` | Legacy status encodes both “candidate accepted” and “visible to manager” |
| Matching history suppression by decisions | `src/matching/matching.engine.ts` (`hasCandidateRejectedSameJob`, `hasManagerSkippedSameCandidate`) | Decision fields used as lifecycle proxy |
| Admin stats uses `candidate_decision === "apply"` | `src/admin/admin-webapp.service.ts` | Runtime writes `applied`; metric drift |

#### A.3 Contact/shared flags drift

There are two different “contact shared” concepts:

1. User-level contact availability/consent:
- `users.contact_shared` and session contact fields.
- Writers: `StateService.setContactInfo/clearContactInfo`, `UsersRepository.saveContact/setContactShared`, `StatePersistenceService.persistSession`.

2. Match-level bilateral exchange completion:
- `matches.status = contact_shared`.
- Writer: `DecisionService.markContactShared` -> `MatchStorageService.markContactShared`.

These can diverge because they are separate write paths and separate semantics.

### B. Interview lifecycle drift

#### B.1 Interview start/completion write points

| Write point | File | Legacy fields/signals written |
|---|---|---|
| Interview start marker | `src/state/state.service.ts` (`markInterviewStarted`) called from multiple router bootstrap branches in `src/router/state.router.ts` | `session.interviewStartedAt`, `session.documentType` |
| Interview completion marker | `src/state/state.service.ts` (`markInterviewCompleted`) called by `src/interviews/interview.engine.ts` | `session.interviewCompletedAt`, `finalArtifact` |
| Completed interview file snapshot | `src/storage/interview-storage.service.ts` | JSON files in `data/interviews/*.json` |
| Completed interview DB snapshot | `src/db/repositories/interviews.repo.ts` | inserts rows into `interview_runs` |

#### B.2 Interview active/completed inference points

| Inference point | File | Drift risk |
|---|---|---|
| Active interview state | `session.state` (`interviewing_candidate|interviewing_manager`) across router and state service | Runtime state used as lifecycle source of truth for active phase |
| Completion status in admin | `src/admin/admin-webapp.service.ts` (`resolveInterviewStatus`) | Derived from `user_states.state` + existence of `interview_runs` row |
| Canonical normalization | `src/core/matching/lifecycle-normalizers.ts` | Uses mixed signals (`sessionState`, `answerCount`, run row/timestamps) |

#### B.3 `interview_runs` vs `interviews` schema drift

- Runtime writes only `interview_runs` (`InterviewsRepository`, migration `003_interview_runs.sql`).
- Migration `019_interviews_table.sql` defines `interviews` with `status in (active, completed, abandoned)` but current runtime does not write it.
- Admin progress currently reads `interview_runs` + `user_states`, not `interviews`.

### C. Manager exposure drift

#### C.1 Places where candidate becomes visible to manager

| Path | File | Current behavior |
|---|---|---|
| Push notification after candidate apply | `src/notifications/notification.engine.ts` (`notifyManagerCandidateApplied`) | Sends manager notification and now calls `ManagerExposureService` sidecar |
| Pull/read manager card composition | `src/matching/match-card-composer.service.ts` (`composeForManager`) | Builds manager card and now calls `ManagerExposureService` sidecar |
| Legacy pull path (show matches command) | `src/router/state.router.ts` (`showTopMatchesWithActions`) | Renders manager card directly without `ManagerExposureService` |

#### C.2 Ownership boundary today

- Owned by `ManagerExposureService`:
  - push path (`source=notification_push`)
  - pull card-composer path (`source=match_card_pull`)
- Not owned yet:
  - `StateRouter.showTopMatchesWithActions` manager branch.

The service itself explicitly logs partial coverage with `missingSource: state_router.showTopMatchesWithActions`.

## 2. Current canonical sidecar coverage

| Canonical transition/logical step | Sidecar owner | Runtime seam | Persisted? |
|---|---|---|---|
| Candidate accepts match | `DecisionService` + `MatchLifecycleService.candidateAcceptsMatch` | candidate apply path | No (log-only) |
| Candidate declines match | `DecisionService` + `MatchLifecycleService.candidateDeclinesMatch` | candidate reject path | No (log-only) |
| Manager approves/rejects | `DecisionService` + `MatchLifecycleService.managerApprovesCandidate/managerRejectsCandidate` | manager decision path | No (log-only) |
| Send to manager (exposure moment) | `ManagerExposureService` + `MatchLifecycleService.sendToManager` | push + one pull path | No (log-only) |
| Interview start | `StateService` + `InterviewLifecycleService.startInterview` | `markInterviewStarted` | No (log-only) |
| Interview completion | `InterviewEngine` + `InterviewLifecycleService.completeInterview` | `completeInterview` | No (log-only) |
| Canonical read normalization | `lifecycle-normalizers`, `candidate-package.builder`, `manager-review-read-model` | manager notifier/card composition read paths | No (read-only) |

## 3. Drift / duplication hotspots

1. Legacy status vocabulary remains source of writes, canonical status is sidecar-only.
- All DB/file writes still use legacy status/decision fields.
- Canonical lifecycle is computed in parallel but not stored.

2. `candidate_applied` is overloaded.
- It means candidate accepted and also acts as manager visibility trigger in practice.
- Canonical `SEND_TO_MANAGER` is inferred from this, not from an explicit exposure event.

3. Manager exposure has split ownership.
- Push and card-composer pull paths are covered.
- Legacy `showTopMatchesWithActions` bypasses service and normalization stack.

4. Interview lifecycle is spread across multiple signal families.
- Session state (`interviewing_*`), session timestamps, `answers`, `interview_runs` rows, and unused `interviews` schema all coexist.

5. Contact sharing semantics are split across user and match entities.
- `users.contact_shared` indicates personal contact availability.
- `matches.status=contact_shared` indicates bilateral exchange completion.
- No single reconciler enforces consistency.

6. Admin/reporting drift exists in production-facing diagnostics.
- `candidatesApplied` uses `"apply"` while runtime writes `"applied"`.

## 4. Safe cleanup candidates

1. Route legacy manager pull rendering through existing normalized read path.
- Candidate: replace/bridge manager branch in `StateRouter.showTopMatchesWithActions` to reuse `MatchCardComposerService` (or helper) so `ManagerExposureService` always runs.
- Why safe: read-side only; keep same buttons/actions.

2. Introduce one read-only “legacy lifecycle resolver” used by admin/dashboard.
- Candidate: centralize status/decision normalization for admin metrics and tables (including tolerant `apply/applied` handling).
- Why safe: reporting-only change, no business decision mutation.

3. Mark dead/legacy-only statuses and methods as deprecated in code comments/docs.
- Candidate: `contact_pending`, `closed`, `setContactPending` (currently unused in runtime path).
- Why safe: documentation/deprecation only before actual deletion.

## 5. Unsafe cleanup areas (not ready yet)

1. Replacing legacy persisted lifecycle fields with canonical statuses.
- Not safe yet because callbacks, decision guards, and admin tools still depend on legacy values directly.

2. Collapsing interview persistence schemas immediately.
- Not safe yet because current runtime relies on `interview_runs` while migration `interviews` may still be expected by external SQL/ops workflows.

3. Changing decision/state gating semantics (`proposed`, `candidate_applied`, `manager_accepted`) in one step.
- Not safe yet because callback flows, consent flow, and state transitions are tightly coupled to these exact checks.

## 6. Recommended cleanup order

1. Complete read-path ownership first.
- Cover `StateRouter.showTopMatchesWithActions` manager branch with `ManagerExposureService` + normalized read model.
- Keep legacy text/buttons unchanged.

2. Stabilize reporting and diagnostics.
- Fix admin metric vocabulary drift (`apply` vs `applied`) via tolerant normalization.
- Reuse one shared legacy->canonical resolver for admin views.

3. Introduce explicit “exposure event” sidecar payload contract.
- Keep log-only, but ensure both push and all pull paths emit consistent metadata (`matchId`, source, canonicalFrom/canonicalTo).

4. Consolidate interview lifecycle derivation.
- Keep writes unchanged; centralize read derivation from session + `interview_runs` in one adapter used by admin and read models.

5. Prepare persistence migration guardrails (no field replacement yet).
- Add migration notes for eventual canonical status persistence columns/events.
- Keep dual-write plan explicit before any DB changes.

6. Only then begin write-path migration.
- Move one transition at a time (candidate decision -> manager decision -> exposure -> contact exchange).
- Keep legacy writes as fallback until parity tests pass.

7. Final cleanup phase.
- Remove dead status paths and unused methods after runtime and analytics no longer reference them.
- Retire temporary drift comments/TODOs once full coverage is achieved.

## 7. Explicit Deprecation Markers (Current Step)

This section tracks legacy vocabulary that is now explicitly marked as deprecated in code comments/annotations.

### 7.1 Deprecated legacy statuses

| Legacy value | Why deprecated | Keep until | Canonical replacement direction |
|---|---|---|---|
| `contact_pending` | Placeholder status; no active runtime transition owner; can create false lifecycle assumptions | legacy reads/writes are fully migrated | explicit manager-exposure + consent ownership (`ManagerExposureService` + canonical match lifecycle) |
| `closed` | Placeholder status with no active writer in current runtime | legacy schema compatibility is removed | canonical terminal statuses (`REJECTED`, `REJECTED_BY_SYSTEM`) in `MatchLifecycleService` |

### 7.2 Overloaded (not deprecated yet) legacy status

| Legacy value | Current overload | Risk | Canonical direction |
|---|---|---|---|
| `candidate_applied` | Represents both candidate acceptance and manager-exposure moment | ambiguous lifecycle ownership | split into explicit canonical transitions (`candidateAcceptsMatch` and `sendToManager`) |

### 7.3 Deprecated helper methods

| Helper | Why deprecated | Canonical replacement direction |
|---|---|---|
| `MatchStorageService.setContactPending(...)` | writes deprecated placeholder status; no stable runtime owner | explicit exposure/consent seam + canonical lifecycle transition ownership |

### 7.4 Marker locations in code

- `src/decisions/match.types.ts`
  - legacy lifecycle caveats documented on `MatchStatus`
  - deprecated placeholder statuses marked (`contact_pending`, `closed`)
  - overloaded status note for `candidate_applied`
- `src/storage/match-storage.service.ts`
  - `setContactPending` marked with `@deprecated` doc comment
- `src/core/matching/legacy-matching-compat.ts`
  - explicit deprecated/overloaded legacy status lists
- `src/core/matching/legacy-lifecycle-drift-notes.ts`
  - read-only drift/deprecation inventory for cleanup planning
