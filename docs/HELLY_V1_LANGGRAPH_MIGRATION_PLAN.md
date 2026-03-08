# HELLY v1 LangGraph Migration Plan

Execution Plan for Migrating Helly to LangGraph Stage Agents

Version: 1.0  
Date: 2026-03-07

Canonical note:

- this document reflects the original migration sequencing toward LangGraph
- the current canonical rebuild sequence is now defined in `HELLY_V1_AGENT_OWNED_STAGE_REBUILD_PLAN.md`
- future execution should follow the rebuild plan when the two documents differ

## 1. Purpose

This document turns the LangGraph stage-agent architecture decision into an execution sequence.

It does not replace the full implementation roadmap.

It focuses only on:

- introducing LangGraph
- migrating stage orchestration
- preserving backend state authority

## 2. Migration Goal

Helly should move from:

- Telegram routing
- shared controller
- shared state-assistance layer

to:

- LangGraph stage router
- one bounded stage agent per major workflow stage
- backend validation bridge

Updated target:

- every major user-facing stage should become a full stage-owning agent
- not merely a graph-driven help layer over existing handlers

## 3. Constraints

During migration:

- Postgres state machines remain authoritative
- repositories and domain services remain reusable
- no agent may mutate state directly
- all side effects still go through backend services
- migration should happen stage-family by stage-family

## 4. Execution Order

### Step 1. LangGraph Foundation

Deliver:

- `langgraph` dependency
- `src/graph/` module boundary
- shared Helly graph state contract
- graph bootstrap and runner

Status:

- in progress
- implemented:
  - dependency baseline
  - `src/graph/` foundation package
  - canonical `HellyGraphState`
  - stage registry
  - foundation stage graph bootstrap
  - router skeleton
  - runtime compiler with sequential fallback when `langgraph` is not importable in the local environment

### Step 2. Backend Validation Bridge

Deliver:

- adapter from graph action proposal to backend validator
- standard validated action result contract
- common no-op and rejection handling

Status:

- in progress
- implemented:
  - graph-to-backend action validation adapter
  - normalized validation result contract
  - graph node integration for action validation

### Step 3. Entry Stage Agents

Migrate:

- `CONTACT_REQUIRED`
- `CONSENT_REQUIRED`
- `ROLE_SELECTION`

Exit:

- `/start` and early onboarding no longer depend on old branchy Telegram handlers for decisioning

Status:

- in progress
- implemented:
  - entry-stage graph service
  - graph-owned execution for `CONTACT_REQUIRED`
  - graph-owned execution for `CONSENT_REQUIRED`
  - graph-owned execution for `ROLE_SELECTION`
  - structured consent transition through graph validation
  - structured role-selection transition through graph validation
  - Telegram entry flow now uses graph execution first for text-based onboarding interactions

### Step 4. Candidate Onboarding Agents

Migrate:

- `CV_PENDING`
- `SUMMARY_REVIEW`
- `QUESTIONS_PENDING`
- `VERIFICATION_PENDING`
- `READY`

Exit:

- candidate journey is stage-agent owned from CV request through ready state

Status:

- in progress
- implemented:
  - graph-owned text-stage execution for `CV_PENDING`
  - graph-driven help handling for `CV_PENDING`
  - graph-driven structured action proposal for candidate text CV input
  - graph-driven `send_cv_text` validation and backend handoff
  - graph-owned execution for `SUMMARY_REVIEW`
  - graph-driven structured action proposal for summary approval
  - graph-driven structured action proposal for summary correction
  - graph-driven backend handoff for summary approval and one-round correction
  - graph-owned execution for `QUESTIONS_PENDING`
  - graph-driven structured parsing for salary, location, and work-format answers
  - graph-driven backend handoff for parsed question payloads
  - graph-owned execution for `VERIFICATION_PENDING`
  - graph-driven validation and backend handoff for verification video submission
  - graph-owned execution for `READY` status guidance and delete-profile initiation
  - graph-driven `delete_profile` validation and backend handoff into deletion confirmation flow
  - voice/document candidate experience input still falls through to the existing backend intake path
  - voice/video mandatory-question answers still fall through to the existing backend question parser path
  - only non-video verification interactions remain as in-stage guidance; actual verification completion happens through graph-validated video handoff into the existing backend video-verification service

### Step 5. Hiring Manager Onboarding Agents

Migrate:

- `INTAKE_PENDING`
- `CLARIFICATION_QA`
- `OPEN`

Exit:

- manager vacancy onboarding is stage-agent owned

Status:

- in progress
- implemented:
  - graph-owned text-stage execution for `INTAKE_PENDING`
  - graph-driven help handling for `INTAKE_PENDING`
  - graph-driven structured action proposal for manager text JD input
  - graph-driven `send_job_description_text` validation and backend handoff
  - graph-owned execution for `CLARIFICATION_QA`
  - graph-driven structured parsing for text clarification answers
  - graph-driven `send_vacancy_clarifications` validation and backend handoff
  - graph-owned execution for `OPEN` status guidance and delete-vacancy initiation
  - graph-driven `delete_vacancy` validation and backend handoff into deletion confirmation flow
  - non-text vacancy JD input still falls through to the existing backend intake path
  - voice/video clarification answers still fall through to the existing backend clarification parser path

### Step 6. Interview and Review Agents

Migrate:

- `INTERVIEW_INVITED`
- `INTERVIEW_IN_PROGRESS`
- `MANAGER_REVIEW`
- `DELETE_CONFIRMATION`

Exit:

- invitation, interview, review, and deletion confirmation are stage-agent owned

Status:

- in progress
- implemented:
  - graph-owned execution for `INTERVIEW_INVITED`
  - graph-driven validation and backend handoff for `accept_interview`
  - graph-driven validation and backend handoff for `skip_opportunity`
  - graph-owned execution for `INTERVIEW_IN_PROGRESS`
  - graph-driven validation and backend handoff for `answer_current_question`
  - graph-owned execution for `MANAGER_REVIEW`
  - graph-driven validation and backend handoff for `approve_candidate`
  - graph-driven validation and backend handoff for `reject_candidate`
  - graph-owned execution for `DELETE_CONFIRMATION`
  - graph-driven validation and backend handoff for `confirm_delete`
  - graph-driven validation and backend handoff for `cancel_delete`
  - Telegram routing now uses graph-first help/reply resolution for migrated stages before compatibility fallback to the old controller path

### Step 7. Routing Simplification

Deliver:

- remove old duplicated help interception branches
- keep Telegram layer as transport and normalization glue
- centralize stage execution entrypoint through LangGraph

Status:

- in progress
- implemented:
  - migrated stages now use graph-first execution before legacy compatibility fallback
  - Telegram transport reuses a single graph result per migrated update path
  - repeated graph-to-backend handoff branches for candidate delete, manager delete, manager review, candidate interaction, candidate summary review, candidate verification, manager clarification, manager intake, and candidate intake are extracted into reusable helpers instead of duplicated inline routing code
  - repeated graph-help reply dispatch for migrated stages is also centralized into a shared helper instead of repeated inline `graph reply -> notification` branches
  - repeated compatibility fallback service-to-notification dispatch for summary review, verification, questions, clarification, intake, manager review, and candidate interview paths is also centralized into reusable Telegram helpers
  - `TelegramUpdateService` no longer calls `BotControllerService` directly for generic unsupported-input recovery; recovery now resolves stage context through graph/messaging-native transport helpers

### Step 8. Production Validation

Deliver:

- reusable validation command for Railway API health and Telegram webhook correctness
- validated live baseline against the deployed production bot

Status:

- in progress
- implemented:
  - `scripts/validate-production.sh`
  - `make validate-production`
  - live validation run against Railway production:
    - API `/health` returned `ok`
    - Telegram webhook URL matched `APP_BASE_URL/telegram/webhook`
    - `pending_update_count` was `0`
  - `scripts/inspect_telegram_user.py`
  - live DB inspection run against Supabase completed successfully for a non-existent Telegram user id and returned a valid empty snapshot

### Step 8. Regression and Production Hardening

Deliver:

- graph-path integration tests
- migration parity tests against old behavior
- production smoke tests for candidate and manager flows

Status:

- in progress
- implemented:
  - graph-stage resolution coverage for candidate priority ordering:
    - `READY`
    - `INTERVIEW_INVITED`
    - `INTERVIEW_IN_PROGRESS`
    - `DELETE_CONFIRMATION`
  - graph-stage resolution coverage for manager priority ordering:
    - `OPEN`
    - `MANAGER_REVIEW`
    - `DELETE_CONFIRMATION`
  - Telegram routing now caches and reuses a single graph stage result per migrated candidate/manager message path, reducing duplicated graph execution inside one update cycle
  - migrated stage help resolution no longer depends on `bot_controller` fallback for candidate, manager, interview, review, and delete conversational paths
  - entry-stage consent and role-selection execution no longer depends on legacy raw-text command branches
  - entry-stage help resolution no longer depends on `bot_controller` fallback; if graph provides no stage-owned reply, runtime falls through to generic recovery instead
  - graph-native sequential flow tests now cover candidate stage progression:
    - `CV_PENDING`
    - `SUMMARY_REVIEW`
    - `QUESTIONS_PENDING`
    - `VERIFICATION_PENDING`
    - `READY`
  - graph-native sequential flow tests now cover manager stage progression:
    - `INTAKE_PENDING`
    - `CLARIFICATION_QA`
    - `OPEN`
    - `DELETE_CONFIRMATION`
  - graph-native sequential flow tests now cover interaction stage progression:
    - `INTERVIEW_INVITED`
    - `INTERVIEW_IN_PROGRESS`
    - `MANAGER_REVIEW`
    - `DELETE_CONFIRMATION`
  - graph-native Telegram routing tests now cover:
    - entry -> candidate -> CV/questions handoff
    - entry -> hiring manager -> JD/clarification handoff
    - candidate interview accept/answer and manager approve review handoff
  - graph-native Telegram routing tests now assert the full `graph decision -> backend service handoff -> notification template` path rather than only stage-agent outputs
  - repeated Telegram transport dispatch branches for candidate delete, manager delete, manager review, and candidate interaction actions are now consolidated into reusable graph-handoff helpers
  - full test suite currently passes with graph-owned routing and stage-resolution coverage

## 5. Definition of Done

The migration is complete when:

- all major user-facing stages execute through LangGraph
- old state-aware routing/controller logic is no longer the main orchestration layer
- each major user-facing stage is owned by its stage agent rather than by scattered handler logic
- backend state transitions remain validated and auditable
- Telegram transport is reduced to ingress/egress plumbing
