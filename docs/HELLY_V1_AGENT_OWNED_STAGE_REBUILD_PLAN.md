# HELLY v1 Agent-Owned Stage Rebuild Plan

Full Execution Plan for Rebuilding Helly Around LangGraph Stage Agents

Version: 1.0  
Date: 2026-03-07

## 1. Purpose

This document is the canonical execution plan for rebuilding Helly to the target architecture where:

- every major user-facing workflow step is a persisted state
- every user-facing state is managed by its own AI stage agent
- `LangGraph` orchestrates stage execution and handoff
- prompts and shared knowledge base drive stage behavior

This document supersedes the old migration mindset of:

- shared controller first
- partial in-state AI help
- gradual fallback-based assistance

From this point forward, implementation should assume:

- the end-state is `agent-owned stages`
- not `state-aware helper logic around rigid handlers`

## 2. Rebuild Goal

The rebuild is complete when Helly works like this:

1. A user sends a Telegram message.
2. Backend resolves the active persisted state.
3. LangGraph loads the correct stage agent for that state.
4. The stage agent conducts the full conversation for that stage.
5. The stage agent collects the data required for stage completion.
6. The stage agent emits structured output for transition.
7. Backend persists side effects and moves the entity to the next state.
8. LangGraph hands execution to the next stage agent.

## 3. Non-Negotiable Rules

Rules for the rebuild:

- every major user-facing state must have its own stage agent
- every stage agent must have its own prompt family
- every stage agent must use the shared Helly knowledge base
- every stage agent must know its own completion criteria
- every transition must be backed by structured output, not raw string matching
- Telegram service must become thin transport glue
- domain services must stop owning conversational behavior

## 4. Stage Inventory to Build

## 4.1 Entry

- `CONTACT_REQUIRED`
- `CONSENT_REQUIRED`
- `ROLE_SELECTION`

## 4.2 Candidate

- `CV_PENDING`
- `SUMMARY_REVIEW`
- `QUESTIONS_PENDING`
- `VERIFICATION_PENDING`
- `READY`

## 4.3 Hiring Manager

- `INTAKE_PENDING`
- `CLARIFICATION_QA`
- `OPEN`

## 4.4 Interview and Review

- `INTERVIEW_INVITED`
- `INTERVIEW_IN_PROGRESS`
- `MANAGER_REVIEW`
- `DELETE_CONFIRMATION`

These are the mandatory agent-owned stages for v1.

## 5. Deliverable Required for Every Stage

For each stage, the rebuild is not complete until the following exist:

- stage agent name and graph registration
- stage-specific system prompt
- stage-specific prompt examples
- stage-specific output schema
- knowledge-base grounding rules
- allowed actions
- completion criteria
- required structured payload
- transition mapping to the next state
- tests for:
  - happy path
  - help path
  - blocker path
  - alternative input path
  - invalid input path

## 6. Phased Execution Plan

## Phase 1. Freeze the New Canonical Architecture

Tasks:

1. Rewrite architecture docs so `agent-owned stage execution` is the canonical target.
2. Rewrite planning docs so future work no longer treats the old shared controller as the final design.
3. Treat all remaining work as rebuild work, not minor hardening of the old routing model.

Exit:

- documentation source of truth is aligned

## Phase 2. Define the Canonical Stage-Agent Contract

Tasks:

1. Finalize the shared `HellyGraphState` contract.
2. Finalize the standard stage agent output schema.
3. Finalize canonical fields:
   - `reply_text`
   - `intent`
   - `stage_status`
   - `proposed_action`
   - `structured_payload`
   - `follow_up_needed`
   - `follow_up_question`
   - `confidence`
4. Finalize validation bridge from stage output to backend transition execution.
5. Finalize stage completion semantics.

Exit:

- every future stage agent can be built against one stable contract

## Phase 3. Build the Shared Graph Runtime

Tasks:

1. Finalize graph registry for all stage agents.
2. Finalize graph runtime/compiler for production `Python 3.12`.
3. Finalize reusable graph nodes:
   - context loading
   - KB grounding
   - intent interpretation
   - reply generation
   - payload extraction
   - completion check
   - validation bridge
   - transition handoff
4. Finalize graph-level tracing and logging.
5. Ensure graph execution is the first-class runtime path in API flow.

Exit:

- reusable graph runtime is stable and can host every stage agent

## Phase 4. Rebuild Entry Flow as Full Stage Agents

Tasks:

1. Implement `contact_required_agent` as full stage owner.
2. Implement `consent_required_agent` as full stage owner.
3. Implement `role_selection_agent` as full stage owner.
4. Replace legacy entry routing decisions with graph-first execution.
5. Add tests for:
   - why contact is needed
   - can I skip
   - why consent is needed
   - candidate vs hiring manager explanation

Exit:

- onboarding entry is fully stage-agent driven

## Phase 5. Rebuild Candidate Flow as Full Stage Agents

Tasks:

1. Implement `candidate_cv_agent`.
2. Implement `candidate_summary_review_agent`.
3. Implement `candidate_questions_agent`.
4. Implement `candidate_verification_agent`.
5. Implement `candidate_ready_agent`.

For `candidate_cv_agent` specifically:

6. Collect enough user input to produce canonical `cv_text`.
7. Persist `cv_text` as first-class profile data.
8. Trigger summary analysis from persisted `cv_text`.
9. Persist candidate-facing summary as first-class summary data.
10. Ask exactly one review question:
   - `Does this summary look correct, or would you like to change anything?`
11. Allow exactly one summary correction round.
12. Produce final summary for approval.

Exit:

- candidate journey from CV stage to `READY` is stage-agent owned

## Phase 6. Rebuild Hiring Manager Flow as Full Stage Agents

Tasks:

1. Implement `vacancy_intake_agent`.
2. Implement `vacancy_clarification_agent`.
3. Implement `vacancy_open_agent`.
4. Ensure manager can provide job details through multiple allowed formats.
5. Ensure the clarification agent can collect missing fields through natural conversation.

Exit:

- manager vacancy onboarding is stage-agent owned

## Phase 7. Rebuild Interview and Review Flow as Full Stage Agents

Tasks:

1. Implement `interview_invite_agent`.
2. Implement `interview_session_agent`.
3. Implement `manager_review_agent`.
4. Implement `delete_confirmation_agent`.
5. Move invitation explanation, interview guidance, review explanation, and delete explanation into stage agents.

Exit:

- interview/review/delete stages are stage-agent owned

## Phase 8. Move Stage Completion Logic Into Agents

Tasks:

1. Remove remaining command-heavy routing assumptions from Telegram layer.
2. Remove stage-completion heuristics that live outside stage agents.
3. Ensure each stage agent is responsible for deciding:
   - still collecting
   - needs follow-up
   - ready for transition
4. Keep backend transition execution reusable but move conversation ownership into stage agents.

Exit:

- conversation and completion logic belong to stage agents, not scattered handlers

## Phase 9. Replace Legacy Controller Paths

Tasks:

1. Retire old shared bot controller as primary stage logic.
2. Retire legacy state-assistance routing branches where graph execution exists.
3. Keep only thin transport glue in Telegram service.
4. Keep compatibility adapters only where still needed during migration.

Exit:

- legacy controller is no longer the main orchestration runtime

## Phase 10. Graph-Native Testing and Hardening

Tasks:

1. Add graph-unit tests for every stage agent.
2. Add graph-integration tests for every stage family.
3. Add end-to-end candidate flow tests.
4. Add end-to-end manager flow tests.
5. Add end-to-end interview/review tests.
6. Add failure-mode tests for:
   - ambiguous user input
   - help questions
   - refusal/blocker messages
   - alternative allowed inputs
   - repeated invalid attempts

Exit:

- graph execution is covered beyond route-level tests

## Phase 11. Production Validation

Tasks:

1. Run Docker-native full test suite under `Python 3.12`.
2. Validate Railway deploy with `langgraph` installed in runtime image.
3. Run live Telegram smoke tests for:
   - candidate onboarding
   - manager onboarding
   - interview invite
   - deletion confirmation
4. Verify logs and traces for graph execution.

Exit:

- graph-based production path is validated

## 7. Priority Order

Strict order:

1. architecture freeze
2. shared graph contract
3. graph runtime
4. entry agents
5. full candidate agents
6. full manager agents
7. interview/review/delete agents
8. remove legacy controller ownership
9. graph-native tests
10. production validation

## 8. Immediate Next Tasks

The next concrete implementation tasks should be:

1. expand `LangGraph` graph runtime from partial slices to full stage ownership
2. convert candidate-side migrated stages from help-oriented graph slices into full stage owners
3. finish manager-side stage coverage:
   - `CLARIFICATION_QA`
   - `OPEN`
4. migrate interaction stages:
   - `INTERVIEW_INVITED`
   - `INTERVIEW_IN_PROGRESS`
   - `DELETE_CONFIRMATION`
5. refactor Telegram routing so graph becomes the default path for all supported stages

Current execution note:

- Phase 1 is complete
- Phase 8 is materially complete for all major user-facing stages
- Phase 9 is in progress, with graph-first execution now primary in migrated Telegram paths
- entry consent and role-selection execution no longer depends on legacy raw-text routing branches
- entry-stage help resolution no longer uses `bot_controller` fallback; entry assistance is now graph-owned or falls through to generic recovery outside stage guidance
- entry flow in Phase 4 is now implemented as graph-owned execution for text-based onboarding interactions
- `CV_PENDING` is now implemented as a graph-owned text stage
- `SUMMARY_REVIEW` is now implemented as a graph-owned approval/correction stage
- `QUESTIONS_PENDING` is now implemented as a graph-owned structured-answer stage
- `VERIFICATION_PENDING` is now implemented as a graph-owned verification stage with graph-validated video handoff
- `READY` is now implemented as a graph-owned candidate status/delete-initiation stage
- `INTAKE_PENDING` is now implemented as a graph-owned manager text-intake stage
- `CLARIFICATION_QA` is now implemented as a graph-owned manager clarification stage
- `OPEN` is now implemented as a graph-owned manager status/delete-initiation stage
- `INTERVIEW_INVITED` is now implemented as a graph-owned invitation-decision stage
- `INTERVIEW_IN_PROGRESS` is now implemented as a graph-owned active-answer stage
- `MANAGER_REVIEW` is now implemented as a graph-owned review-decision stage
- `DELETE_CONFIRMATION` is now implemented as a graph-owned deletion-decision stage
- Telegram routing now prefers graph-owned stage replies and graph-owned action handoff before falling back to legacy controller assistance in migrated paths
- Telegram routing now reuses one graph stage result per migrated candidate/manager message path instead of repeatedly re-invoking graph execution inside the same update
- migrated candidate, manager, interview, review, and delete stage help paths no longer rely on `bot_controller` fallback; in-stage help now comes from graph-owned stage execution only
- entry-stage help no longer relies on `bot_controller` fallback either; only generic recovery remains outside graph-owned guidance
- graph-native stage-resolution coverage now verifies priority ordering across candidate and manager stage families, including `READY`, `INTERVIEW_INVITED`, `INTERVIEW_IN_PROGRESS`, `MANAGER_REVIEW`, and `DELETE_CONFIRMATION`
- graph-native flow coverage now includes sequential candidate and manager journey tests across multiple stage transitions, not only single-stage unit checks
- graph-native flow coverage now also includes interaction-path sequences across invitation, active interview, manager review, and delete confirmation
- graph-native Telegram routing coverage now includes end-to-end text journeys where `TelegramUpdateService` executes `graph -> backend handoff -> notification` across entry, candidate, manager, and interaction paths
- graph-native Telegram routing coverage now includes full text journeys for:
  - entry -> candidate onboarding -> CV/questions handoff
  - entry -> manager onboarding -> JD/clarification handoff
  - interview accept/answer and manager review approval handoff
- candidate delete dispatch, manager delete dispatch, manager review dispatch, and candidate interaction dispatch are now extracted into reusable Telegram transport helpers instead of duplicated inline routing branches
- the next rebuild target is Phase 9 and Phase 10 cleanup work: removing remaining legacy controller ownership, simplifying Telegram routing around graph-first execution, and expanding graph-native end-to-end coverage

## 9. Definition of Done

This rebuild is complete when:

- all major user-facing states are agent-owned stages
- all such stages run through LangGraph
- all stage agents have prompt assets and KB grounding
- all stage agents can gather the data required to complete their step
- all transitions happen from structured stage outputs
- Telegram routing is thin glue only
- the old shared controller is no longer the primary execution path

## 10. Canonical Companion Documents

Read this together with:

- `HELLY_V1_AGENT_OWNED_STAGE_ARCHITECTURE.md`
- `HELLY_V1_AGENT_KNOWLEDGE_BASE.md`
- `HELLY_V1_PROMPT_CATALOG.md`
