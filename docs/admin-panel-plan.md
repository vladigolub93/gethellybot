# Admin Panel Implementation Plan

## 1. Goal

Implement a real admin panel for Helly that uses only existing project data and real backend APIs.

The admin panel must provide:

- PIN login handled by backend only
- user list with filters by role and status
- block / unblock / hard-delete users
- match list with statuses and reasons already present in project data
- basic system analytics
- send bot messages to one or many selected users, with preview
- Telegram-group notifications about match lifecycle, each with a link to the corresponding admin match page

This plan intentionally does **not** rely on inactive product features as a primary requirement.
Legacy interview / evaluation code may still exist in the repository, but admin functionality must be built around the active candidate-vacancy-match flow.

## 2. Product Decisions Confirmed

- Admin panel opens as a normal browser page, not as a Telegram Mini App.
- Any person who knows the PIN `6088` can log into the admin panel.
- `block user` means fully preventing any incoming and outgoing bot interactions.
- `delete user` means hard delete of the user and all related history.
- Admin messaging must support:
  - one user
  - multiple selected users
  - preview before send
- Basic analytics v1 should include:
  - users by role/status
  - candidates by state
  - vacancies by state
  - matches by stage/status
  - skips / approvals / contact shares
  - simple funnel/conversion views

## 3. Real Existing System Baseline

### 3.1 Runtime

- API: [apps/api/main.py](/Users/vladigolub/Desktop/gethellybot/apps/api/main.py)
- Worker: [apps/worker/main.py](/Users/vladigolub/Desktop/gethellybot/apps/worker/main.py)
- Scheduler: [apps/scheduler/main.py](/Users/vladigolub/Desktop/gethellybot/apps/scheduler/main.py)

### 3.2 Current frontend

- Existing user-facing webapp is Telegram-only and lives in:
  - [src/webapp/router.py](/Users/vladigolub/Desktop/gethellybot/src/webapp/router.py)
  - [src/webapp/service.py](/Users/vladigolub/Desktop/gethellybot/src/webapp/service.py)
  - [src/webapp/static/app.js](/Users/vladigolub/Desktop/gethellybot/src/webapp/static/app.js)

This current webapp uses Telegram `initData` auth and is not suitable as-is for browser-based admin access.

### 3.3 Real entities already present

Core:

- `users`
- `files`
- `raw_messages`
- `user_consents`
- `state_transition_logs`
- `job_execution_logs`
- `notifications`
- `outbox_events`

Candidate:

- `candidate_profiles`
- `candidate_profile_versions`
- `candidate_verifications`
- `candidate_cv_challenge_attempts`

Vacancy:

- `vacancies`
- `vacancy_versions`

Matching:

- `matching_runs`
- `matches`
- `invite_waves`
- `introduction_events`

Dormant / secondary:

- interview tables
- evaluation tables

These dormant tables may still need cleanup on hard delete if rows exist, but admin UX must not depend on them.

### 3.4 Current Telegram error-group integration

Existing error-group alerts already use:

- setting: `TELEGRAM_ERROR_CHAT_ID`
- service: [src/monitoring/telegram_alerts.py](/Users/vladigolub/Desktop/gethellybot/src/monitoring/telegram_alerts.py)

This same group will be reused for match lifecycle notifications.

## 4. Main Architecture Decision

Create a **separate browser admin surface** instead of extending Telegram WebApp auth.

### 4.1 Admin URL

Introduce a new admin browser route:

- `GET /admin`

This page will be usable from:

- direct browser visit
- link from Telegram error group

### 4.2 Admin auth model

Use backend-validated PIN login:

- `POST /admin/api/auth/pin`
- request body contains the PIN
- backend verifies the PIN
- backend issues an admin session

Use a backend-issued signed admin session cookie, not Telegram auth.

Recommended:

- new admin session helper modeled after current signed webapp session
- separate cookie for admin
- separate secret in config for admin session signing

Result:

- links from Telegram group can open `/admin#/matches/<id>`
- if not logged in, admin page first shows PIN login
- after successful login, frontend returns to the requested route

## 5. Scope of Admin Panel

### 5.1 Users

Admin must be able to:

- list all users
- filter by role
- filter by active / blocked / deleted-like state
- open a user detail drawer/page
- block
- unblock
- hard delete

The list must be powered by real backend queries over the actual `users` table plus related profile/vacancy state.

### 5.2 Matches

Admin must be able to:

- list all matches
- filter by status
- search by role title / candidate / manager / ids
- open match detail
- view real rationale and reasons if present

Real match reason sources already available:

- `matches.filter_reason_codes_json`
- `matches.rationale_json`
- `matching_runs.payload_json`

### 5.3 Analytics

Admin dashboard v1 should include at least:

- total users
- users by role
- blocked users
- candidates by state
- vacancies by state
- matches by status
- recent matching runs
- approval / skip / contact-share counts
- simple funnel:
  - shortlisted
  - candidate_decision_pending
  - candidate_applied
  - manager_decision_pending
  - manager approved awaiting candidate
  - approved / contact share
  - skipped / expired

### 5.4 Send message from bot

Admin must be able to:

- select one or many users
- compose plain text
- preview the exact message
- send through the real notification pipeline

No mocks, no direct front-only fake send.

## 6. Backend Changes

## 6.1 New admin auth/session module

Add a dedicated browser-admin auth flow instead of reusing Telegram auth.

Planned pieces:

- `src/admin/auth.py`
- `src/admin/session.py`
- `src/admin/router.py`
- `src/admin/service.py`

### Endpoints

- `GET /admin`
- `POST /admin/api/auth/pin`
- `POST /admin/api/auth/logout`
- `GET /admin/api/session`

### Config

Add settings such as:

- `ADMIN_PANEL_PIN`
- `ADMIN_SESSION_SECRET`
- `ADMIN_SESSION_TTL_SECONDS`

The actual PIN value in production will be `6088`.

## 6.2 User admin APIs

Add real admin APIs:

- `GET /admin/api/users`
- `GET /admin/api/users/{user_id}`
- `POST /admin/api/users/block`
- `POST /admin/api/users/unblock`
- `DELETE /admin/api/users/{user_id}`

### List payload

Return:

- identity
- Telegram ids
- role flags
- candidate state if profile exists
- vacancy count / open vacancy count if manager
- blocked flag
- deleted-related visibility
- timestamps

### Filters

Support at least:

- `role=candidate|hiring_manager|dual|unknown`
- `status=active|blocked|deleted_like`
- free-text search over:
  - display name
  - username
  - telegram user id

## 6.3 User block semantics

There is no current `blocked` field, so add one explicitly.

Recommended schema change on `users`:

- `is_blocked boolean not null default false`
- `blocked_at timestamptz null`
- optional `blocked_reason text null`

### Enforcement points

Block must stop both incoming and outgoing bot interactions.

This requires enforcement in at least:

1. Inbound Telegram handling
- ignore / short-circuit new user messages and callbacks if `users.is_blocked = true`

2. Outbound notification delivery
- do not send queued notifications to blocked users
- mark them cancelled or skipped with explicit reason

3. Matching/review dispatch
- blocked candidates must not receive vacancy cards
- blocked managers must not receive candidate cards

4. Browser web surfaces
- blocked candidate/manager access should be denied for normal user-facing surfaces

Admin auth itself remains independent from `users`.

## 6.4 Hard delete service

Current product has soft-delete helpers for candidate/vacancy and a test reset script:

- [src/cleanup/service.py](/Users/vladigolub/Desktop/gethellybot/src/cleanup/service.py)
- [scripts/reset_telegram_user.py](/Users/vladigolub/Desktop/gethellybot/scripts/reset_telegram_user.py)

Admin delete must be a real backend hard-delete workflow.

### Approach

Create a dedicated admin deletion service that:

- builds a deletion plan for the target user
- deletes all linked entities in a safe order
- executes inside a DB transaction
- returns a machine-readable deletion summary

### Entities to delete

At minimum:

- `introduction_events`
- `evaluation_results` if present
- interview-related rows if present
- `invite_waves`
- `matches`
- `matching_runs`
- `candidate_verifications`
- `candidate_cv_challenge_attempts`
- `candidate_profile_versions`
- `vacancy_versions`
- `notifications`
- `outbox_events`
- `state_transition_logs`
- `job_execution_logs`
- `user_consents`
- `raw_messages`
- `files`
- `candidate_profiles`
- `vacancies`
- `users`

Because the user asked for hard delete of all related history, this service should be based on the proven deletion order in `scripts/reset_telegram_user.py`, then moved into supported backend code.

## 6.5 Match admin APIs

Add:

- `GET /admin/api/matches`
- `GET /admin/api/matches/{match_id}`

### Match list fields

- match id
- vacancy id
- candidate profile id
- role title
- candidate name
- manager identity
- status
- fit band
- hard-filter outcome
- reason codes
- main rationale text
- timestamps

### Filters

- by status
- by fit band
- by vacancy id
- by user id
- free-text search

The match detail endpoint should expose only real saved data:

- match metadata
- fit/rationale
- candidate/vacancy summaries
- current statuses
- related notification / contact-share facts if available

## 6.6 Analytics APIs

Add:

- `GET /admin/api/analytics/overview`
- optional small supporting endpoints if needed for chart sections

The overview response should be computed from real tables only.

Suggested sections:

- userCounts
- candidateStateCounts
- vacancyStateCounts
- matchStatusCounts
- recentMatchingRuns
- conversionMetrics
- recentOpsStats

## 6.7 Admin bot messaging APIs

Add:

- `POST /admin/api/messages/preview`
- `POST /admin/api/messages/send`

### Preview

Input:

- selected user ids
- plain text message

Return:

- resolved recipients
- skipped recipients
- rendered preview text
- recipient count

### Send

Use the existing notification delivery pipeline:

- create `notifications` rows
- scheduler picks them up
- bot sends via existing `NotificationDeliveryService`

This keeps delivery consistent with production behavior and avoids parallel ad-hoc bot sending code.

## 6.8 Match lifecycle alerts to Telegram group

Add a dedicated ops alert service for match events instead of overloading error-alert wording.

Suggested new module:

- `src/monitoring/match_alerts.py`

This service should send to the existing Telegram error chat using the same bot token / chat id.

### Events to notify

1. match created
2. match successful
3. match unsuccessful
4. candidate approved
5. manager approved
6. candidate skipped
7. manager skipped
8. contacts shared

### Event semantics

- `match created`: when a new `matches` row is created
- `candidate approved`: when match moves to `candidate_applied`
- `manager approved`: when match moves to `manager_interview_requested` or direct approve branch
- `contacts shared`: when `IntroductionEvent` is created and contact notifications are emitted
- `match successful`: when match reaches final approved direct-contact handoff
- `match unsuccessful`: when match reaches terminal negative result such as manager skip, candidate skip, or expiry

### Message content

Each alert must include:

- event type
- match id
- vacancy title
- candidate label
- manager label
- current match status
- admin URL to that match

### Admin match link format

Use a browser-safe admin URL, for example:

- `/admin#/matches/<match_id>`

Because admin is a browser page with PIN auth, this link can be used directly from the Telegram group.

### Hook points

Alert hooks should be added where the lifecycle actually changes:

- new matches in [src/matching/service.py](/Users/vladigolub/Desktop/gethellybot/src/matching/service.py)
- candidate/manager review actions and contact share in [src/matching/review.py](/Users/vladigolub/Desktop/gethellybot/src/matching/review.py)

Avoid generic global hooks that would make alerts ambiguous.

## 7. Frontend Changes

## 7.1 New browser admin app

Create a dedicated admin frontend instead of reusing Telegram-only boot.

Suggested structure:

- `src/admin/static/index.html`
- `src/admin/static/admin.js`
- `src/admin/static/admin.css`

This admin UI can still visually align with the current terminal-like Helly design system, but it should not depend on Telegram WebApp runtime APIs.

## 7.2 Screens

### Login

- PIN input
- backend submit
- error state

### Dashboard

- KPI cards
- small charts / grouped counts
- recent match activity

### Users

- searchable/filterable table
- bulk selection
- row actions:
  - block
  - unblock
  - delete
  - send message

### Matches

- searchable/filterable table
- status badges
- fit band / reason summary
- open detail view

### Match detail

- vacancy block
- candidate block
- rationale block
- lifecycle block
- notification / contact-share facts

### Messaging

- recipient selector from filtered users
- message composer
- preview pane
- confirm send

## 7.3 Navigation

Use browser routes or hash routes:

- `/admin#/dashboard`
- `/admin#/users`
- `/admin#/matches`
- `/admin#/matches/<id>`
- `/admin#/messages`

If the browser opens directly on a match link before auth:

- page stores target route
- after PIN login, it restores the requested route

## 8. Real-Data Query Strategy

No mocks or hardcoded entities.

The admin panel must read from actual repositories / SQL queries:

- users
- candidate profiles
- vacancies
- matches
- matching runs
- notifications
- raw messages
- state transitions
- contact-share events

For analytics and lists, add explicit admin-oriented query helpers instead of repurposing owner-scoped candidate/manager queries.

## 9. Implementation Order

## Phase 1. Admin auth foundation

- add admin session config
- add admin auth/session helpers
- add `/admin` page and auth endpoints
- add browser session boot flow

## Phase 2. User admin backend

- add user list/detail queries
- add schema migration for block fields
- add block/unblock service logic
- add inbound/outbound blocked-user enforcement

## Phase 3. Hard delete backend

- add deletion planner/service
- wire delete API
- return deletion summary
- add tests for cascade correctness

## Phase 4. Match admin backend

- add match list/detail queries
- expose reasons/rationale/statuses

## Phase 5. Analytics backend

- implement overview aggregations

## Phase 6. Admin messaging backend

- preview endpoint
- send endpoint using real notifications

## Phase 7. Match lifecycle Telegram alerts

- add match alert service
- emit alerts at creation / decision / skip / contact-share transitions
- include admin match links

## Phase 8. Admin frontend

- login screen
- dashboard
- users screen
- matches screen
- messaging screen

## Phase 9. Integration and polish

- blocked users stopped on inbound and outbound flows
- direct match links open correctly after auth
- large tables stay usable
- empty/loading/error states

## 10. Testing Plan

Add or extend tests for:

### Auth

- valid PIN login
- invalid PIN rejected
- expired admin session rejected
- logout clears session

### Users

- list filters
- block/unblock
- blocked users cannot interact with bot
- blocked users do not receive notifications

### Deletion

- hard delete candidate user
- hard delete manager user
- dual-role edge cases if present
- related rows removed in expected order

### Matches

- list filters
- detail response includes real rationale/reasons

### Analytics

- overview aggregates from real fixture rows

### Messaging

- preview resolves real recipients
- send creates real notifications
- bulk selection works

### Match alerts

- created
- candidate approved
- manager approved
- skipped
- approved/contact shared
- unsuccessful outcome
- admin URL included

### Frontend

- login flow
- route restore after auth
- list rendering
- bulk actions

## 11. Risks and Mitigations

### Risk: hard delete is destructive

Mitigation:

- service-level deletion planner
- transactional delete
- explicit confirmation in admin UI
- visible deletion summary

### Risk: blocked users still get messages from old queued notifications

Mitigation:

- notification delivery must check blocked state immediately before send
- optionally cancel pending notifications for blocked user on block action

### Risk: admin links from Telegram group fail before login

Mitigation:

- browser admin page stores target route and restores it after PIN auth

### Risk: current read-only webapp assumptions conflict with admin writes

Mitigation:

- build admin as a separate surface under `/admin`
- do not entangle it with Telegram WebApp auth rules

## 12. Deliverables

At the end of implementation, the repo should contain:

- backend admin auth and admin APIs
- browser admin frontend
- block/unblock/delete support
- analytics endpoints and UI
- admin messaging preview/send
- Telegram match lifecycle alerts with admin links
- tests for the new admin behavior

