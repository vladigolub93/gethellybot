# HELLY v1 Agent Ownership Completion Plan

Detailed Execution Plan for Removing Backend Intent Ownership From User-Facing Stages

Version: 1.0  
Date: 2026-03-08

## 1. Purpose

This document defines the remaining work required to make Helly behave according to the intended architecture:

- every user-facing stage is owned by its own AI stage agent
- `LangGraph` orchestrates stage execution
- backend does not interpret user intent inside migrated stages
- backend only validates structured stage output, persists side effects, and executes transitions

This plan exists because the current runtime is only partially in that state.

Some stages already run through `LangGraph`, but parts of their decision logic still rely on backend-side heuristics such as:

- help-pattern matching
- command aliases
- fallback text classification
- non-empty-text means completion input

That is not the target architecture.

## 2. Target Runtime Rule

For every migrated user-facing stage:

1. Telegram transport passes the message into the active stage agent.
2. The stage agent decides:
   - help
   - question
   - blocker
   - clarification
   - stage-completion input
   - follow-up needed
   - transition readiness
3. The stage agent returns structured output.
4. Backend only:
   - validates the proposed action
   - persists data
   - executes side effects
   - records the state transition

Backend must not:

- reinterpret the user message after the stage agent
- override stage meaning with local intent heuristics
- decide whether a message is help vs correction vs approval inside migrated stages

## 3. Current Gap

The remaining architectural gap is:

- stage orchestration exists
- graph ownership exists
- but true stage intent ownership is still incomplete

The biggest remaining problem class is:

- stage runtime still uses deterministic detectors in:
  - graph stage nodes
  - Telegram compatibility routing
  - domain service command parsing

This leads to bugs where:

- a help question is treated as a correction
- a timing question is treated as stage completion
- a free-form clarification is treated as an action command

## 4. Scope

This plan applies to all major user-facing stages:

### 4.1 Entry

- `CONTACT_REQUIRED`
- `ROLE_SELECTION`

### 4.2 Candidate

- `CV_PENDING`
- `SUMMARY_REVIEW`
- `QUESTIONS_PENDING`
- `VERIFICATION_PENDING`
- `READY`

### 4.3 Hiring Manager

- `INTAKE_PENDING`
- `VACANCY_SUMMARY_REVIEW`
- `CLARIFICATION_QA`
- `OPEN`

### 4.4 Interview and Review

- `INTERVIEW_INVITED`
- `INTERVIEW_IN_PROGRESS`
- `MANAGER_REVIEW`
- `DELETE_CONFIRMATION`

## 5. Canonical Division of Responsibility

### Stage Agent Owns

- intent understanding
- in-stage conversation
- help handling
- blocker handling
- alternative-path explanation
- follow-up inside the stage
- decision whether stage is complete
- decision what structured action should be proposed

### Backend Owns

- persistence
- queueing
- external tool execution
- validation of proposed action against allowed actions
- state transition execution
- audit logging

### Telegram Transport Owns

- update normalization
- graph invocation
- rendering of returned notifications/messages
- no stage-specific interpretation logic

## 6. Ordered Task List

### Phase A. Freeze the Rule in Documentation

1. Mark backend intent classification in migrated stages as architecture debt.
2. Update architecture docs so the stage agent is explicitly the only owner of user-message interpretation inside migrated stages.
3. Update implementation status to show that graph execution is not enough unless intent ownership also lives in the agent.
4. Add this plan to the documentation index.

Exit:

- canonical docs clearly state the rule

### Phase B. Inventory All Remaining Backend Intent Logic

5. Audit all `src/graph/stages/*.py` files for deterministic intent detectors.
6. Audit `src/telegram/service.py` for stage-specific interpretation logic that still influences meaning.
7. Audit candidate, vacancy, interview, and evaluation services for raw command interpretation that should move into stage agents.
8. Produce a matrix:
   - stage
   - current intent owner
   - target intent owner
   - backend logic to remove

Exit:

- every remaining non-agent intent decision is mapped

Current artifact for this phase:

- [HELLY_V1_AGENT_INTENT_OWNERSHIP_MATRIX.md](./HELLY_V1_AGENT_INTENT_OWNERSHIP_MATRIX.md)

### Phase C. Define the Canonical Agent Decision Contract

9. Expand the stage agent output contract so it fully covers:
   - `message_kind`
   - `intent`
   - `proposed_action`
   - `structured_payload`
   - `needs_follow_up`
   - `follow_up_text`
   - `reasoning_confidence`
10. Define what backend may do when:
   - action accepted
   - action rejected
   - no action proposed
   - help reply only
11. Define the rule that stage agents may propose `no_transition` intentionally.

Exit:

- one stable contract for full agent ownership

### Phase D. Add Explicit Prompt Coverage for Intent Ownership

12. Update every stage prompt family so it explicitly says:
    - you decide whether the user is asking for help, asking a question, correcting data, approving, rejecting, or providing completion input
13. Add prompt instructions that the agent must not treat every free-form message as completion input.
14. Add prompt instructions that timing/why/what-next questions are still in-stage help, not transitions.
15. Add prompt instructions that edits/corrections must be based on explicit correction intent.

Exit:

- prompts encode intent ownership, not just copy style

### Phase E. Rebuild Entry Stages to LLM-First Intent

16. Remove deterministic entry help classification from `CONTACT_REQUIRED`.
17. Remove deterministic entry help classification from `ROLE_SELECTION`.
18. Let the entry stage agent decide:
    - user is asking why contact is needed
    - user is asking whether they can skip
    - user is asking what candidate vs manager means
    - user is actually selecting a role
19. Keep backend only for action validation and role/contact persistence.

Exit:

- entry stages are agent-owned in intent, not only in routing

### Phase F. Rebuild Candidate Stages to LLM-First Intent

20. Remove deterministic intent classification from `CV_PENDING`. `Completed`
21. Remove deterministic intent classification from `SUMMARY_REVIEW`. `Completed`
22. Remove deterministic intent classification from `QUESTIONS_PENDING`. `Completed`
23. Remove deterministic intent classification from `VERIFICATION_PENDING`.
24. Remove deterministic intent classification from `READY`. `Completed`

For `SUMMARY_REVIEW` specifically:

25. Ensure timing questions are treated as help. `Completed`
26. Ensure “why do I need to approve this?” is treated as help. `In progress`
27. Ensure only explicit correction intent becomes `request_summary_change`. `Completed`
28. Ensure only explicit approval intent becomes `approve_summary`. `Completed`

For `QUESTIONS_PENDING` specifically:

29. Ensure free-form compensation/location answers are parsed by the stage agent first.
30. Ensure help questions like `gross or net?` are not misclassified as final answers.

Exit:

- candidate stages are agent-owned in intent

### Phase G. Rebuild Manager Stages to LLM-First Intent

31. Remove deterministic intent classification from `INTAKE_PENDING`. `Completed`
32. Remove deterministic intent classification from `VACANCY_SUMMARY_REVIEW`. `Completed`
33. Remove deterministic intent classification from `CLARIFICATION_QA`. `Completed`
34. Remove deterministic intent classification from `OPEN`.

For `VACANCY_SUMMARY_REVIEW` specifically:

35. Ensure timing/help questions are treated as help. `Completed`
36. Ensure only explicit correction intent becomes `request_summary_change`. `Completed`
37. Ensure only explicit approval intent becomes `approve_summary`. `Completed`

Exit:

- manager stages are agent-owned in intent

### Phase H. Rebuild Interview and Review Stages to LLM-First Intent

38. Remove deterministic intent classification from `INTERVIEW_INVITED`. `Completed`
39. Remove deterministic intent classification from `INTERVIEW_IN_PROGRESS`. `Completed`
40. Remove deterministic intent classification from `MANAGER_REVIEW`.
41. Remove deterministic intent classification from `DELETE_CONFIRMATION`. `Completed`

Exit:

- interview/review/delete stages are agent-owned in intent

### Phase I. Remove Remaining Stage Interpretation From Telegram Transport

42. Remove stage-specific meaning decisions from `TelegramUpdateService`.
43. Leave only:
    - normalize update
    - resolve active stage
    - call graph
    - render result
    - handoff to backend execution
44. Verify transport contains no stage-specific `help vs action` meaning logic.

Exit:

- Telegram transport becomes thin glue

### Phase J. Remove Remaining Stage Interpretation From Domain Services

45. Refactor candidate service methods so they execute actions, not interpret raw user intent.
46. Refactor vacancy service methods so they execute actions, not interpret raw user intent.
47. Refactor interview service methods so they execute actions, not interpret raw user intent.
48. Keep only action-oriented execution methods in domain services.

Exit:

- domain services are executors, not stage interpreters

### Phase K. Add Regression Suite for Intent Ownership

49. Add one regression suite per stage for:
    - help question
    - timing question
    - blocker statement
    - explicit completion input
    - explicit correction
    - explicit approval/rejection where applicable
50. Add matrix tests that verify free-form questions do not accidentally trigger transitions.
51. Add matrix tests that verify only explicit correction intent creates correction actions.

Exit:

- intent-ownership regressions are pinned down

### Phase L. Live Validation

52. Run live candidate smoke for `SUMMARY_REVIEW` timing/help questions.
53. Run live candidate smoke for `QUESTIONS_PENDING` clarification questions.
54. Run live manager smoke for `VACANCY_SUMMARY_REVIEW` help/correction/approve.
55. Verify Railway logs show graph stage execution without incorrect downstream action execution.
56. Verify Supabase snapshots after each smoke stage.

Exit:

- the architecture is verified against real Telegram behavior

## 7. Recommended Execution Order

Strict order:

1. Phase A
2. Phase B
3. Phase C
4. Phase D
5. Phase E
6. Phase F
7. Phase G
8. Phase H
9. Phase I
10. Phase J
11. Phase K
12. Phase L

## 8. Definition of Done

This plan is complete when:

- every migrated stage is truly agent-owned in intent
- backend does not reinterpret user messages inside migrated stages
- Telegram transport does not contain stage-specific meaning logic
- domain services execute validated actions rather than classify raw text
- free-form help questions no longer accidentally trigger transitions
- live Telegram smoke confirms the new behavior on real user flows
