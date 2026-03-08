# HELLY v1 Entry and Vacancy Redesign Task List

Detailed Execution Plan for:

- removing consent from entry onboarding
- allowing onboarding with Telegram `username` or shared `contact`
- adding manager-side vacancy summary review symmetry
- clarifying the `LangGraph supervisor/router` role over stage agents

Version: 1.0  
Date: 2026-03-08

## 1. Purpose

This document defines the next concrete redesign slice for Helly.

It supersedes the older assumptions that:

- entry onboarding must always collect consent
- entry onboarding must always collect a shared Telegram contact first
- manager vacancy intake can go directly from raw JD input into clarification without a manager-facing summary approval step

## 2. Target Product Behavior

### 2.1 Entry Flow

The desired entry flow becomes:

1. User sends `/start`.
2. Bot reads Telegram identity data from the update.
3. If the user already has a Telegram `username`, onboarding may continue without asking for shared contact.
4. If the user has no usable `username` and no stored shared `contact`, bot enters `CONTACT_REQUIRED`.
5. After identity is sufficient, bot goes directly to `ROLE_SELECTION`.

There is no consent stage in this redesign.

### 2.2 Candidate Flow

Candidate flow stays conceptually the same:

- collect CV / experience input
- persist canonical `cv_text`
- generate candidate-facing summary
- allow one correction round
- collect required candidate fields
- collect verification
- move to `READY`

### 2.3 Hiring Manager Flow

Hiring manager flow changes to:

1. collect raw vacancy input
2. persist canonical `vacancy_text`
3. generate manager-facing vacancy summary in 3-4 sentences
4. ask manager to approve or correct that summary
5. allow one correction round
6. only then move to vacancy clarification
7. after clarification move vacancy to `OPEN`

### 2.4 Orchestration Rule

The system should not introduce a free-form global conversational super-agent.

Instead it should use:

- one `LangGraph supervisor/router`
- one bounded stage agent per user-facing stage
- backend validation and transition execution

The supervisor/router should:

- resolve the active persisted stage
- select the correct stage agent
- pass graph state and context
- receive structured stage output
- route the result into backend validation and side effects

The supervisor/router should not behave like a global chat agent.

## 3. Canonical Stage Inventory After This Redesign

### 3.1 Entry

- `CONTACT_REQUIRED`
- `ROLE_SELECTION`

### 3.2 Candidate

- `CV_PENDING`
- `SUMMARY_REVIEW`
- `QUESTIONS_PENDING`
- `VERIFICATION_PENDING`
- `READY`

### 3.3 Hiring Manager

- `INTAKE_PENDING`
- `VACANCY_SUMMARY_REVIEW`
- `CLARIFICATION_QA`
- `OPEN`

### 3.4 Interview and Review

- `INTERVIEW_INVITED`
- `INTERVIEW_IN_PROGRESS`
- `MANAGER_REVIEW`
- `DELETE_CONFIRMATION`

## 4. Ordered Task List

### Phase A. Freeze Documentation

1. Remove `CONSENT_REQUIRED` from canonical stage architecture docs.
2. Update entry flow docs so `username` or shared `contact` is sufficient identity for onboarding.
3. Add `VACANCY_SUMMARY_REVIEW` to canonical stage inventory.
4. Update prompt catalog and knowledge base to reflect the new entry rule and manager summary-review rule.
5. Clarify in architecture docs that the runtime uses a thin `LangGraph supervisor/router`, not a global chat agent.

### Phase B. Entry Flow Redesign

6. Remove `CONSENT_REQUIRED` from graph-owned entry-stage execution.
7. Update entry-stage resolution so `CONTACT_REQUIRED` is used only when the user has neither `username` nor stored shared `contact`.
8. Update Telegram entry transport and recovery paths to use the new identity rule consistently.
9. Remove entry consent messaging, reply markup, and compatibility logic from runtime.
10. Remove or retire consent-specific prompt assets from the active stage inventory.
11. Keep `user_consents` table as legacy-compatible data until cleanup is explicitly scheduled; do not block onboarding on it.

### Phase C. Entry Prompt and KB Redesign

12. Rewrite `CONTACT_REQUIRED` prompt so it explains:
    - username is enough if available
    - shared contact is only needed when username is unavailable
    - contact supports identity and later approved introduction
13. Rewrite `ROLE_SELECTION` prompt so it becomes the first post-identity stage.
14. Update shared KB answers:
    - why contact is requested
    - when it is not requested
    - what data is and is not shared
15. Remove obsolete consent explanations from user-facing KB and prompts.

### Phase D. Entry Test Redesign

16. Add graph-stage tests for:
    - `username -> ROLE_SELECTION`
    - `no username -> CONTACT_REQUIRED`
    - contact-help questions
17. Add Telegram routing tests for:
    - `/start` with username
    - `/start` without username
    - contact share path
    - role selection after username-only identity
18. Remove or rewrite tests that expect consent gating.

### Phase E. Vacancy Summary Review Stage Design

19. Add `VACANCY_SUMMARY_REVIEW` to manager-side state-machine docs.
20. Define completion criteria for the new stage:
    - manager approves the generated vacancy summary
    - or manager provides exactly one correction round
21. Define canonical persisted fields:
    - raw `vacancy_text`
    - manager-facing `approval_summary_text`
    - structured vacancy summary JSON
22. Define prompt contract for manager-facing vacancy summary:
    - 3-4 concise sentences
    - manager-facing wording
    - no raw internal extraction dump

### Phase F. Vacancy Summary Review Runtime

23. Persist canonical `vacancy_text` before downstream LLM analysis.
24. Generate vacancy summary from persisted `vacancy_text`.
25. Persist manager-facing vacancy summary separately from raw structured summary JSON.
26. Show the manager only the manager-facing summary.
27. Ask one review question, symmetric with candidate summary review.
28. Allow exactly one correction round.
29. After approval, transition to `CLARIFICATION_QA`.
30. Ensure raw parsed vacancy text is not rendered back to the manager.

### Phase G. Vacancy Summary Review Stage Agent

31. Add `vacancy_summary_review_agent` to graph stage registration.
32. Add dedicated prompt family for `VACANCY_SUMMARY_REVIEW`.
33. Add structured action support for:
    - `approve_vacancy_summary`
    - `request_vacancy_summary_change`
34. Add backend handoff from graph result into vacancy summary review service logic.

### Phase H. Vacancy Summary Review Tests

35. Add stage-agent tests for:
    - help question
    - approve
    - real correction request
    - empty correction request
36. Add Telegram flow tests for:
    - JD input -> summary review
    - approve -> clarification
    - correction -> final summary -> approve
37. Add rendering tests to ensure only manager-facing summary is shown.

### Phase I. Prompt Coverage and Cleanup

38. Ensure prompt coverage tests now include `VACANCY_SUMMARY_REVIEW`.
39. Remove `CONSENT_REQUIRED` from canonical required stage-prompt coverage once runtime no longer uses it.
40. Re-run full prompt coverage suite.

### Phase J. Live Validation

41. Run live Telegram smoke for username-only onboarding.
42. Run live Telegram smoke for no-username contact onboarding.
43. Run live Telegram smoke for manager vacancy summary review.
44. Verify Railway logs show graph-owned execution for the updated entry and manager stages.
45. Verify Supabase state snapshots after each smoke milestone.

## 5. Recommended Execution Order

Strict order for implementation:

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

## 6. Definition of Done

This redesign slice is complete when:

- entry flow no longer contains a consent stage
- username-only users can onboard without contact share
- no-username users are cleanly routed into `CONTACT_REQUIRED`
- manager vacancy intake includes a summary-review step
- manager sees a human summary, not raw parsed vacancy text
- vacancy summary review supports one correction round
- `VACANCY_SUMMARY_REVIEW` is graph-owned
- prompt coverage and runtime tests are green
- live Telegram smoke passes for the updated flows
