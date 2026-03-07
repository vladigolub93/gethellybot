# Remaining Lifecycle Drift After Canonical Read Adoption

This document captures lifecycle drift that still exists **after**:
- canonical lifecycle sidecar persistence (`canonical_match_status`, `canonical_interview_status`),
- unified lifecycle snapshot resolver,
- canonical-first admin read snapshot,
- canonical-aware manager review read model.

Scope:
- Analysis/documentation only.
- No runtime behavior changes.

### 1. Canonical lifecycle already in use

### Match lifecycle (canonical usage)

- `src/decisions/decision.service.ts`
  - Computes canonical sidecar transitions for:
    - candidate accept/reject,
    - manager approve/reject.
  - Persists canonical sidecar via `MatchStorageService.apply*Decision(..., { canonicalMatchStatus })`.
- `src/storage/match-storage.service.ts`
  - Carries optional `canonicalMatchStatus` in updates.
- `src/db/repositories/matches.repo.ts`
  - Persists `canonical_match_status` when available; falls back to legacy payload if canonical persistence fails.

### Interview lifecycle (canonical usage)

- `src/state/state.service.ts`
  - Computes canonical interview start transition (`INVITED -> STARTED`) sidecar at `markInterviewStarted(...)`.
  - Stores sidecar in session (`session.canonicalInterviewStatus`).
- `src/interviews/interview.engine.ts`
  - Computes canonical interview completion sidecar (`STARTED|IN_PROGRESS -> COMPLETED`).
  - Passes sidecar into persistence record.
- `src/db/repositories/states.repo.ts`
  - Persists `canonical_interview_status` in `user_states` when available.
- `src/db/repositories/interviews.repo.ts`
  - Persists `canonical_interview_status` in `interview_runs` when available.

### Read-side canonical normalization

- `src/core/matching/lifecycle-snapshot.resolver.ts`
  - Prefers canonical persisted statuses when provided; falls back to normalized legacy inputs.
- `src/admin/admin-webapp.service.ts`
  - Passes canonical persisted values to `resolveLifecycleSnapshot(...)`.
- `src/core/matching/candidate-package.builder.ts`
  - Canonical-first precedence in manager package assembly.
- `src/core/matching/manager-review-read-model.ts`
  - Reuses canonical-first candidate package builder.
- `src/notifications/manager-notifier.ts`
  - Uses canonical-aware manager read model.
- `src/matching/match-card-composer.service.ts`
  - Uses canonical-aware manager read model.

### Manager exposure seam

- `src/core/matching/manager-exposure.service.ts`
  - Owns sidecar computation for send-to-manager lifecycle event.
- Integrated call sites:
  - `src/notifications/notification.engine.ts` (`notification_push`),
  - `src/matching/match-card-composer.service.ts` (`match_card_pull`),
  - `src/router/state.router.ts` (`showTopMatchesWithActions` pull path).

### 2. Remaining legacy-driven lifecycle areas

### A. Match lifecycle still primarily controlled by legacy fields

1. Write vocabulary is still legacy-first
- `src/storage/match-storage.service.ts`
  - Writes `status` + `candidateDecision` + `managerDecision` as primary lifecycle fields.
  - Canonical status is additive only.

2. Decision gating still depends on legacy statuses
- `src/decisions/decision.service.ts`
  - Candidate can act only when `match.status === "proposed"`.
  - Manager can act only when `match.status === "candidate_applied"`.
  - Contact share step checks `match.status === "manager_accepted"` / `contact_shared`.

3. Consent/callback flow gates by legacy status
- `src/router/callback.router.ts`
  - Candidate/manager contact-share callbacks still enforce `"manager_accepted"` checks.

### B. Interview lifecycle still split across multiple legacy/implicit signals

1. Session state is a major lifecycle source
- `interviewing_candidate` / `interviewing_manager` still used as active-lifecycle indicator across router/services.

2. Completion inferred via row existence + timestamps
- Admin/read paths still use `hasInterviewRunRow`, `completed_at`, and session state heuristics in parallel.

3. Canonical interview status is duplicated in two stores
- `user_states.canonical_interview_status` and `interview_runs.canonical_interview_status` can drift.

### C. Manager exposure lifecycle meaning is still partially implicit

1. Exposure meaning still relies on legacy status semantics
- `candidate_applied` still acts as visibility proxy in several paths.

2. Exposure service is still telemetry sidecar
- `ManagerExposureService` does not own writes or central orchestration outcome.
- Legacy flow behavior still operates independently.

### D. Admin/reporting still keeps ad hoc legacy interpretation

1. Additional fallback derivation still exists
- `src/admin/admin-webapp.service.ts`
  - `resolveNormalizedLifecycleForAdmin(...)` + `derive*FromLegacyForAdmin(...)` still performs custom interpretation when snapshot fields are null.

2. Legacy metrics vocabulary drift remains
- `candidatesApplied` currently counts `candidate_decision === "apply"` while main runtime writes `"applied"`.

### E. State/session lifecycle signals still encode business meaning

1. Stage detection relies on conversational heuristics
- `src/router/flow-stage.resolver.ts`
  - Candidate/manager review detection uses summary-question text heuristic (`includes("summary"|"confirm")`).

2. Interview progress/reminders rely on broad state buckets
- `src/notifications/interview-reminder.service.ts`
  - Treats `waiting_resume`, `extracting_resume`, `waiting_job`, `extracting_job` as incomplete interview states.

3. Transition graph mixes onboarding/interview/decision meanings
- `src/state/transition-rules.ts`
  - Lifecycle flow remains state-machine-like but still based on legacy state vocabulary, not canonical match/interview lifecycle objects.

### 3. Hidden drift risks

1. Canonical interview status precedence conflict in admin path
- In admin match mapping, canonical interview status prefers `user_states` value first, then falls back to `interview_runs`.
- If `user_states.canonical_interview_status` is stale (for example still `STARTED`) while `interview_runs` has `COMPLETED`, snapshot can be forced to stale value.
- Location: `src/admin/admin-webapp.service.ts` (candidate state lookup + canonical fallback chain around match mapping).

2. Candidate canonical interview map can be polluted by non-candidate runs
- Current loop condition allows rows where `run.role !== "candidate"` into candidate canonical-status map branch.
- This can introduce incorrect map entries for non-candidate records.
- Location: `src/admin/admin-webapp.service.ts` around candidate canonical interview map construction.

3. Canonical match sidecar semantics can diverge from business moment
- Candidate apply path maps legacy `proposed` to canonical `INVITED`, then applies `candidateAcceptsMatch -> INTERVIEW_STARTED`.
- In legacy business flow, candidate apply mostly means "sent/visible to manager" (`candidate_applied`) rather than interview start for a specific match.
- Result: persisted `canonical_match_status` may be internally consistent by transition rules but semantically misaligned with actual runtime milestone.
- Location: `src/decisions/decision.service.ts` + `src/core/matching/match-lifecycle.service.ts`.

4. Manager exposure partial-coverage telemetry is stale
- `ManagerExposureService` currently hardcodes `partialCoverage = true` and logs missing source `state_router.showTopMatchesWithActions`, but that path is already routed through the service.
- This creates misleading operational visibility.
- Location: `src/core/matching/manager-exposure.service.ts` + `src/router/state.router.ts`.

5. Manager read surfaces use different canonical interview sources
- Notification push path can provide `canonicalInterviewStatus` from candidate session.
- Card composition pull path usually lacks canonical interview status and relies on legacy-derived inference.
- Two manager read paths can normalize the same candidate differently at the same time.
- Location: `src/notifications/notification.engine.ts` vs `src/matching/match-card-composer.service.ts`.

6. Admin lifecycle output can still differ from manager read model output
- Admin path still applies extra ad hoc fallback derivation logic after snapshot resolution.
- Manager read model uses candidate package precedence chain.
- Same legacy record can produce different normalized lifecycle in admin vs manager read surfaces.

7. Session-state-based interview status can over-report progress
- `interviewing_*` or incomplete-state buckets can imply active interview even when the lifecycle event did not truly start or already drifted.
- Affects reminders and admin progress summaries.

### 4. Safe next cleanup candidates

1. Unify admin normalized fallback through shared resolver helper
- Replace/retire `deriveMatchStatusFromLegacyForAdmin`, `deriveInterviewStatusFromLegacyForAdmin`, `deriveEvaluationStatusFromLegacyForAdmin` in favor of shared normalization/snapshot fallback.
- Keep output shape unchanged.
- Why safe: read-only admin/reporting path.

2. Fix canonical interview precedence/order in admin read path
- Prefer freshest canonical interview signal (or deterministic precedence) when both `user_states` and `interview_runs` exist.
- Correct candidate-only mapping loop condition to avoid non-candidate contamination.
- Why safe: read-only admin data quality correction.

3. Align manager pull path read input with canonical interview status where available
- Pass canonical interview status into manager pull card/read-model path from safe source when present.
- Keep legacy fallback unchanged.
- Why safe: read-side consistency, no decision/persistence changes.

### 5. Unsafe areas

1. Replacing legacy decision/status gates with canonical gates in callbacks/state router
- Current behavior is tightly coupled to `status` + `candidateDecision` + `managerDecision`.
- Changing this now risks breaking consent and action permissions.

2. Removing legacy match status fields (`status`, `candidateDecision`, `managerDecision`)
- Too risky until all write paths, callbacks, reporting, and analytics fully consume canonical lifecycle ownership.

3. Collapsing interview lifecycle storage into a single source immediately
- `user_states` and `interview_runs` are both active and currently used in different read paths.
- Direct consolidation without staged migration/backfill risks regressions.
