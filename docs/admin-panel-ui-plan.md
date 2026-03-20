# Admin Panel UI/UX Improvement Plan

## Context

Current admin panel is functionally complete, but UX is still at an internal-tool v0 level:

- destructive and bulk actions rely on browser `alert` / `confirm` / `prompt`
- filters are not deep-linkable
- match and user details are too shallow for real operations work
- feedback states are weak: no toasts, no inline loading/error/success
- selected recipients and bulk actions are easy to lose while navigating
- large tables are readable, but not optimized for scanning or triage

The goal of this pass is not a full redesign. It is to make the admin panel noticeably more usable for daily operations while staying on the current stack:

- browser page
- vanilla JS
- real backend APIs
- no mocked data

## Goals

1. Replace blocking browser dialogs with in-app UX.
2. Make admin state shareable and recoverable via URL.
3. Make `matches` the primary operational triage surface.
4. Make `users` detail useful enough for support and moderation.
5. Improve messaging flow confidence before sending.
6. Keep the interface fast, compact, and production-pragmatic.

## Phase 1 Scope

### 1. Action UX

- Add a reusable modal system for:
  - hard delete confirmation
  - block with optional reason
  - send message confirmation
- Add toast notifications for:
  - success
  - error
  - warning
  - informational refresh state

### 2. URL-Synced State

- Persist current screen in hash as today.
- Persist filters in query params:
  - users: `role`, `status`, `candidate_state`, `vacancy_state`, `search`
  - matches: `status`, `fit_band`, `search`
- Persist selected match detail route.
- Preserve message draft and selected recipient flow in-app without surprise resets.

### 3. Richer Match Detail

- Add timeline/events block sourced from real data:
  - state transitions
  - intro/contact-share info
  - related notifications summary
- Improve vacancy and candidate sections:
  - compact metadata pills
  - summary text
  - rationale / gaps / matched signals
  - scores grouped together
- Keep direct admin URL visible.

### 4. Richer User Detail

- Add recent matches for the user.
- Add recent notifications summary.
- Add recent raw-message summary.
- Make user detail clearly show:
  - role and state
  - blocked/deleted state
  - candidate summary or open vacancies
  - operational stats

### 5. Messaging UX

- Show recipient summary more clearly:
  - selected
  - deliverable
  - skipped
- Show skipped reasons in a more readable way.
- Confirm exact send impact before queueing.
- Keep draft intact across screen refreshes.

### 6. Visual/Interaction Polish

- Add sticky action bars where helpful.
- Add visible focus states.
- Improve table scanability.
- Add empty/loading/error states inside screens instead of implicit re-render jumps.
- Make side panel sticky on desktop layouts.

## Backend Support Needed

### AdminService

- Extend `get_user_detail()` with:
  - recent matches
  - recent notifications
  - recent raw messages
- Extend `get_match_detail()` with:
  - state transition timeline
  - related notification summary

No fake or derived entities should be introduced. Only existing project data should be used:

- `users`
- `candidate_profiles`
- `candidate_profile_versions`
- `vacancies`
- `vacancy_versions`
- `matches`
- `matching_runs`
- `notifications`
- `raw_messages`
- `state_transition_logs`
- `introduction_events`

## Frontend Structure Changes

Files:

- `src/admin/static/index.html`
- `src/admin/static/admin.css`
- `src/admin/static/admin.js`

Planned additions:

- app-level modal root
- app-level toast stack
- query/hash state helpers
- richer detail renderers
- improved action handlers with explicit pending states

## Non-Goals For This Pass

- no framework migration
- no React rewrite
- no virtualization yet unless performance becomes a real bottleneck
- no redesign of backend auth
- no new admin permissions model

## Risks

- URL state can get messy if not normalized consistently.
- Large detail payloads can bloat screen rendering if too much history is returned.
- Hard-delete UX must stay conservative and explicit.

## Acceptance Criteria

1. Admin can filter users and matches, refresh, reload page, and keep the same slice.
2. Admin actions no longer depend on browser `alert/confirm/prompt`.
3. Match detail includes timeline/context useful for manual triage.
4. User detail includes recent operational history from real data.
5. Messaging flow shows preview, deliverable/skipped counts, and explicit send confirmation.
6. UI remains browser-page only and uses real backend APIs.

## Implementation Order

1. Add backend detail payloads for user and match history.
2. Add URL state helpers in frontend.
3. Add modal/toast infrastructure.
4. Replace existing destructive/message browser dialogs.
5. Upgrade users detail and matches detail UI.
6. Polish layout, sticky sections, and scanability.
7. Run targeted tests and manual smoke.
