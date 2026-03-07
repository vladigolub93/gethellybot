# Helly v1 DB Schema Audit and Migration Checklist

## Purpose

This document audits the current database schema against the Helly v1 SRS and the execution plan in [helly-v1-implementation-plan.md](/Users/vladigolub/Desktop/telegrambot/docs/helly-v1-implementation-plan.md).

It answers four questions:

1. What tables and columns exist today?
2. Which repositories currently own which tables?
3. What is missing for Helly v1?
4. In what order should schema migration work happen?

## Scope

Sources audited:

- SQL migrations under [src/db/migrations](/Users/vladigolub/Desktop/telegrambot/src/db/migrations)
- repositories under [src/db/repositories](/Users/vladigolub/Desktop/telegrambot/src/db/repositories)
- storage fallbacks under:
  - [src/state/state-persistence.service.ts](/Users/vladigolub/Desktop/telegrambot/src/state/state-persistence.service.ts)
  - [src/storage/match-storage.service.ts](/Users/vladigolub/Desktop/telegrambot/src/storage/match-storage.service.ts)
  - [src/storage/interview-storage.service.ts](/Users/vladigolub/Desktop/telegrambot/src/storage/interview-storage.service.ts)
- schema diagnostics under [src/admin/db-status.service.ts](/Users/vladigolub/Desktop/telegrambot/src/admin/db-status.service.ts)
- SRS in [helly-v1-srs.md](/Users/vladigolub/Desktop/telegrambot/docs/helly-v1-srs.md)

## Executive Summary

The current schema is a workable MVP schema, but it is not yet a Helly v1 schema.

Main blockers:

1. `jobs` is still effectively one-vacancy-per-manager.
2. No first-class `vacancies` entity exists.
3. No first-class `candidate_verifications` entity exists.
4. No first-class `files` entity exists.
5. No first-class `raw_messages` entity exists.
6. No first-class `evaluation_results` entity exists.
7. Interview lifecycle is split across `interviews`, `interview_runs`, and `user_states`.
8. Persistence is not DB-first because local JSON storage still acts as a runtime owner.
9. Some important IDs are structurally inconsistent.

Most dangerous structural mismatch:

- [src/db/migrations/003_matches_v2.sql](/Users/vladigolub/Desktop/telegrambot/src/db/migrations/003_matches_v2.sql) defines `matches.job_id uuid`
- [src/db/migrations/005_profiles_jobs_matches.sql](/Users/vladigolub/Desktop/telegrambot/src/db/migrations/005_profiles_jobs_matches.sql) defines `jobs.id bigserial`

That means `matches.job_id` cannot safely represent `jobs.id` as currently modeled.

## 1. Current Table Inventory

### 1.1 Existing tables found in migrations

Current known tables:

- `users`
- `user_states`
- `profiles`
- `jobs`
- `matches`
- `interview_runs`
- `candidate_profiles`
- `job_profiles`
- `notification_limits`
- `quality_flags`
- `data_deletion_requests`
- `telegram_updates`
- `interviews`

### 1.2 Current table purpose summary

#### `users`

Current purpose:

- Telegram user identity
- role
- contact data
- candidate mandatory fields
- matching preferences

This table is overloaded. It contains:

- identity/contact data
- candidate profile completeness flags
- matching preferences

This is acceptable for MVP, but Helly v1 will likely need cleaner separation between `users` and candidate-specific profile state.

#### `user_states`

Current purpose:

- durable conversational state snapshot
- state payload
- last bot message
- canonical interview sidecar

This is the current owner of session state persistence, but it also acts as an interview-lifecycle sidecar container.

#### `profiles`

Current purpose:

- mixed candidate/job profile storage
- searchable text
- embeddings
- resume/JD intake artifacts
- legacy confirmation strings

This is an overloaded mixed table. It stores two different profile kinds:

- candidate
- job

It is useful as a legacy source, but not a clean Helly v1 target model.

#### `jobs`

Current purpose:

- manager job / vacancy storage
- JD source data
- job analysis
- mandatory manager fields
- job summary and structured profile

Critical issue:

- [src/db/repositories/jobs.repo.ts](/Users/vladigolub/Desktop/telegrambot/src/db/repositories/jobs.repo.ts) upserts using `onConflict: "manager_telegram_user_id"`
- `manager_telegram_user_id` is `unique`

So the schema still enforces one job row per manager.

This is incompatible with the SRS.

#### `matches`

Current purpose:

- candidate-manager matching records
- legacy status and decisions
- matching artifacts
- canonical match lifecycle sidecar

This table is central and useful, but still reflects the old flow vocabulary:

- `candidate_decision`
- `manager_decision`
- overloaded `status`

It also contains type-risk on `job_id`.

#### `interview_runs`

Current purpose:

- completed interview persistence
- artifact snapshot of answers/results
- canonical interview lifecycle completion sidecar

Useful table, but not enough alone for full interview lifecycle ownership.

#### `interviews`

Current purpose:

- active interview state for old MVP flow
- current question index
- plan JSON
- answers JSON

This overlaps conceptually with:

- `user_states`
- `interview_runs`

This is a schema drift hotspot.

#### `candidate_profiles` and `job_profiles`

Current purpose:

- canonical-ish v2 profile storage with embeddings and metadata

Useful direction, but still not aligned with multi-vacancy ownership because `job_profiles` is unique by `telegram_user_id`, not by vacancy.

#### `telegram_updates`

Current purpose:

- idempotency marker only

This is not enough for the SRS raw-message requirement.

## 2. Current Repository to Table Mapping

### 2.1 Active repositories

#### [users.repo.ts](/Users/vladigolub/Desktop/telegrambot/src/db/repositories/users.repo.ts)

Owns:

- `users`

Current writes include:

- role
- preferred language
- contact data
- candidate mandatory fields
- matching preferences

#### [states.repo.ts](/Users/vladigolub/Desktop/telegrambot/src/db/repositories/states.repo.ts)

Owns:

- `user_states`

Current writes include:

- state
- payload
- last bot message
- `canonical_interview_status`

#### [profiles.repo.ts](/Users/vladigolub/Desktop/telegrambot/src/db/repositories/profiles.repo.ts)

Owns:

- `profiles`
- `candidate_profiles`
- `job_profiles`

Current writes include:

- mixed candidate/job profile artifacts
- embeddings
- resume analysis
- technical summaries
- v2 canonical profile snapshots

#### [jobs.repo.ts](/Users/vladigolub/Desktop/telegrambot/src/db/repositories/jobs.repo.ts)

Owns:

- `jobs`

Current writes include:

- manager job summary
- analysis
- technical summary
- mandatory fields
- intake source

Critical problem:

- ownership key is `manager_telegram_user_id`, not `vacancy_id`

#### [matches.repo.ts](/Users/vladigolub/Desktop/telegrambot/src/db/repositories/matches.repo.ts)

Owns:

- `matches`

Current writes include:

- legacy decisions
- legacy status
- match artifacts
- `canonical_match_status`

#### [interviews.repo.ts](/Users/vladigolub/Desktop/telegrambot/src/db/repositories/interviews.repo.ts)

Owns:

- `interview_runs`

Current writes include:

- completed interview records
- `canonical_interview_status`

#### [telegram-updates.repo.ts](/Users/vladigolub/Desktop/telegrambot/src/db/repositories/telegram-updates.repo.ts)

Owns:

- `telegram_updates`

Current writes include:

- `update_id`
- `telegram_user_id`
- `received_at`

This is only idempotency persistence, not raw message persistence.

#### [data-deletion.repo.ts](/Users/vladigolub/Desktop/telegrambot/src/db/repositories/data-deletion.repo.ts)

Owns:

- `data_deletion_requests`

Also performs broad deletions across:

- `user_states`
- `profiles`
- `interview_runs`
- `jobs`
- `matches`
- `notification_limits`
- `telegram_updates`
- `users`

This confirms deletion is currently broad purge logic, not scoped domain deletion.

## 3. Current Schema vs SRS Entity Model

Target SRS entities:

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

### 3.1 Mapping status

| Target entity | Current representation | Status |
|---|---|---|
| User | `users` | Partial |
| CandidateProfile | `profiles(kind=candidate)` + `candidate_profiles` | Partial |
| CandidateVerification | none | Missing |
| Vacancy | `jobs` | Partial, structurally wrong |
| VacancyProfile | `profiles(kind=job)` + `job_profiles` + `jobs.job_profile_json` | Partial |
| Match | `matches` | Partial |
| InterviewSession | `interviews` + `user_states` + `interview_runs` | Partial, drifted |
| InterviewAnswer | embedded JSON in `interviews` / `interview_runs` | Missing as first-class entity |
| EvaluationResult | embedded artifact/JSON only | Missing |
| File | scattered `telegram_file_id` / local files only | Missing |
| RawMessage | `telegram_updates` idempotency only | Missing |
| StateTransitionLog | none | Missing |

## 4. Structural Mismatches and Risks

### 4.1 One manager still equals one job row

Evidence:

- [src/db/migrations/005_profiles_jobs_matches.sql](/Users/vladigolub/Desktop/telegrambot/src/db/migrations/005_profiles_jobs_matches.sql)
- [src/db/repositories/jobs.repo.ts](/Users/vladigolub/Desktop/telegrambot/src/db/repositories/jobs.repo.ts)

Problem:

- Helly v1 requires one manager to own many vacancies.
- Current schema prevents that.

Risk:

- This blocks correct matching ownership.
- This blocks interview waves per vacancy.
- This blocks vacancy deletion as a vacancy-scoped flow.

### 4.2 `matches.job_id` type mismatch

Evidence:

- `matches.job_id uuid`
- `jobs.id bigserial`

Problem:

- current schema cannot safely treat `matches.job_id` as a real foreign key to `jobs.id`

Risk:

- broken joins
- ambiguous ownership
- migration pain when moving to vacancy-first matching

### 4.3 `job_profiles` is unique by manager Telegram user, not by vacancy

Problem:

- even the more canonical profile store is still manager-singleton, not vacancy-scoped

Risk:

- impossible to represent many vacancies properly

### 4.4 Interview data is spread across three owners

Current owners:

- `interviews`
- `interview_runs`
- `user_states.canonical_interview_status`

Problem:

- active session, lifecycle sidecar, and completed artifact are not represented as a clean single interview session model

Risk:

- drift between active and completed states
- ambiguity around interview start, completion, and abandonment

### 4.5 Raw message and file ownership do not exist

Current state:

- `telegram_updates` only stores idempotency markers
- `profiles` and `jobs` store some `telegram_file_id`
- local filesystem stores JSON snapshots for state/matches/interviews

Problem:

- no first-class persistent file entity
- no first-class raw message entity

Risk:

- media/audit gaps
- hard to support video verification cleanly
- hard to trace source-of-truth artifacts

### 4.6 Evaluation is not first-class

Current state:

- evaluation-like fields are embedded in interview artifacts and technical summaries

Problem:

- no clean `evaluation_results` ownership

Risk:

- difficult thresholding
- difficult manager package ownership
- hard to compare evaluation versions over time

### 4.7 DB-first persistence is not true yet

Evidence:

- [state-persistence.service.ts](/Users/vladigolub/Desktop/telegrambot/src/state/state-persistence.service.ts)
- [match-storage.service.ts](/Users/vladigolub/Desktop/telegrambot/src/storage/match-storage.service.ts)
- [interview-storage.service.ts](/Users/vladigolub/Desktop/telegrambot/src/storage/interview-storage.service.ts)

Problem:

- local JSON files are still runtime owners with Supabase mirror behavior

Risk:

- drift between local and DB state
- difficult production recovery
- hard to reason about canonical ownership

## 5. Missing Tables Required for Helly v1

These tables do not exist yet and should be added.

### 5.1 `candidate_verifications`

Required because SRS requires video verification before READY.

Minimum expected columns:

- `id`
- `candidate_user_id`
- `status`
- `verification_phrase`
- `video_file_id`
- `video_storage_key`
- `raw_message_id`
- `verification_result_json`
- `verified_at`
- `created_at`
- `updated_at`

### 5.2 `vacancies`

This should become the first-class replacement for manager-singleton `jobs`.

Minimum expected columns:

- `id`
- `manager_user_id`
- `status`
- `title`
- `jd_source_type`
- `jd_source_file_id`
- `jd_text_original`
- `jd_text_normalized`
- `summary`
- `created_at`
- `updated_at`
- `deleted_at` or equivalent lifecycle field if soft deletion is used

### 5.3 `vacancy_profiles`

If `vacancies` is the first-class entity, vacancy structured profile should be vacancy-scoped.

Minimum expected columns:

- `id`
- `vacancy_id`
- `profile_json`
- `profile_text`
- `embedding`
- `embedding_metadata`
- `analysis_json`
- `technical_summary_json`
- `created_at`
- `updated_at`

### 5.4 `files`

Required to unify documents, voice, video, and verification assets.

Minimum expected columns:

- `id`
- `owner_user_id`
- `telegram_file_id`
- `telegram_unique_file_id` if available
- `message_id`
- `chat_id`
- `kind`
- `mime_type`
- `storage_key`
- `size_bytes`
- `duration_seconds`
- `metadata_json`
- `created_at`

### 5.5 `raw_messages`

Required by the SRS.

Minimum expected columns:

- `id`
- `update_id`
- `message_id`
- `chat_id`
- `telegram_user_id`
- `direction`
- `message_type`
- `payload_json`
- `text_preview`
- `file_id`
- `created_at`

### 5.6 `evaluation_results`

Required for explicit ownership of final evaluation.

Minimum expected columns:

- `id`
- `match_id`
- `interview_session_id`
- `status`
- `score`
- `strengths_json`
- `risks_json`
- `recommendation`
- `model_version`
- `prompt_version`
- `created_at`
- `updated_at`

### 5.7 `state_transition_logs`

Required for auditability and debugging.

Minimum expected columns:

- `id`
- `telegram_user_id`
- `session_scope`
- `from_state`
- `to_state`
- `action`
- `reason`
- `metadata_json`
- `created_at`

### 5.8 `interview_invitations` or equivalent wave-owned table

Required for interview waves and invitation lifecycle.

Minimum expected columns:

- `id`
- `match_id`
- `vacancy_id`
- `candidate_user_id`
- `wave_number`
- `status`
- `invited_at`
- `responded_at`
- `expires_at`
- `created_at`
- `updated_at`

## 6. Existing Tables That Need Major Changes

### 6.1 `jobs`

Decision:

- do not delete immediately
- do not continue expanding it as the final vacancy model

Needed change:

- replace or supersede with first-class `vacancies`

### 6.2 `job_profiles`

Needed change:

- make profile ownership vacancy-scoped, not manager-scoped

### 6.3 `matches`

Needed changes:

- correct `job_id` / `vacancy_id` ownership
- add explicit `vacancy_id` if needed
- preserve current match artifacts during migration
- later reduce legacy decision/status overloading

### 6.4 `interviews`

Needed change:

- decide whether to migrate into `interview_sessions` or repurpose it cleanly

Current table is too tied to old active interview semantics.

### 6.5 `telegram_updates`

Needed change:

- keep for idempotency if useful
- add `raw_messages` separately

It should not be treated as the message persistence solution.

## 7. Recommended Target Schema Direction

### 7.1 Keep and adapt

These can remain, with changes:

- `users`
- `user_states`
- `matches`
- `notification_limits`
- `quality_flags`
- `data_deletion_requests`
- `telegram_updates`

### 7.2 Replace or supersede

- `jobs` -> supersede with `vacancies`
- `job_profiles` -> supersede with vacancy-scoped profile table
- `profiles(kind=job)` -> reduce over time
- `interviews` -> replace or repurpose as canonical interview session owner

### 7.3 Add new first-class tables

- `candidate_verifications`
- `vacancies`
- `vacancy_profiles`
- `files`
- `raw_messages`
- `evaluation_results`
- `state_transition_logs`
- `interview_invitations`

## 8. Migration Checklist

### Priority 0: Do before major runtime refactor

- [ ] document the final target schema names and ownership rules
- [ ] decide whether `vacancies` is a new table or a staged replacement for `jobs`
- [ ] decide whether `interview_sessions` is a new table or a staged replacement for `interviews`
- [ ] correct the `job_id` ownership mismatch in the target design

### Priority 1: Additive schema required for SRS completeness

- [ ] add `candidate_verifications`
- [ ] add `files`
- [ ] add `raw_messages`
- [ ] add `evaluation_results`
- [ ] add `state_transition_logs`
- [ ] add `interview_invitations`
- [ ] add vacancy-first table(s)

### Priority 2: Canonical flow support

- [ ] add vacancy-scoped profile storage
- [ ] add vacancy-scoped matching ownership
- [ ] add wave-tracking fields
- [ ] add deletion-support fields for vacancy/profile cancellation

### Priority 3: Cleanup prep

- [ ] update DB status diagnostics to include new required tables/columns
- [ ] stop expanding manager-singleton `jobs` assumptions
- [ ] stop relying on JSON local files as primary persistence

## 9. Recommended Migration Order

### Step 1

Add new additive tables that do not break current runtime:

- `files`
- `raw_messages`
- `candidate_verifications`
- `evaluation_results`
- `state_transition_logs`
- `interview_invitations`

### Step 2

Introduce vacancy-first schema:

- add `vacancies`
- add `vacancy_profiles`
- keep `jobs` intact during migration

### Step 3

Introduce canonical interview-session schema:

- either add `interview_sessions`
- or formally repurpose `interviews`

### Step 4

Wire read-side services to new tables first.

### Step 5

Wire write-side runtime ownership to new tables behind feature flags or safe migration seams.

### Step 6

Only after runtime cutover:

- deprecate manager-singleton `jobs`
- deprecate legacy mixed profile ownership
- remove JSON-primary persistence

## 10. Immediate Implementation Recommendation

The next implementation task after this audit should be:

**Design the target vacancy-first and raw-message/file schema in SQL migrations without wiring runtime behavior yet.**

That should include:

1. a new `vacancies` table
2. a new `vacancy_profiles` table or equivalent
3. a new `files` table
4. a new `raw_messages` table
5. a new `candidate_verifications` table

Reason:

- these are the biggest SRS blockers at the schema level
- they can be added safely and additively
- they unblock later runtime cutover work

## 11. Final Assessment

Current schema readiness for Helly v1:

- current MVP persistence coverage: medium
- SRS compatibility: low to medium
- migration readiness: medium

The schema is strong enough to evolve in place, but not strong enough yet to support the final Helly v1 product flow without additive tables and ownership correction.

