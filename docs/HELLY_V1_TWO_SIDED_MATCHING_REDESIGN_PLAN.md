# HELLY v1 Two-Sided Matching and Interview Redesign Plan

Superseded note:

- This document is no longer the active product flow.
- The active runtime is documented in [HELLY_V1_DIRECT_CONTACT_MATCHING_FLOW.md](/Users/vladigolub/Desktop/gethellybot/docs/HELLY_V1_DIRECT_CONTACT_MATCHING_FLOW.md).
- The interview-heavy design below is kept only as historical design context for a future premium interview mode.

Detailed Execution Plan for:

- moving from auto-invite-after-match to manager/candidate pre-interview decisions
- showing managers candidate profiles before interview
- showing candidates matched vacancies before interview
- enforcing `3 at a time` presentation and `10 active` pipeline caps
- enforcing `1 active interview at a time` per candidate with queued interviews
- treating interview interruption as candidate decline

Version: 1.0  
Date: 2026-03-10

## 1. Purpose

This document defines the next major redesign slice for Helly.

It replaces the current assumption that:

- a shortlisted candidate is automatically invited to interview
- the hiring manager sees the candidate only after interview evaluation
- a candidate sees a role only when the system has already decided to invite them

The new target is a two-sided decision funnel before interview starts.

## 2. Target Product Behavior

## 2.1 Manager-Side Flow

When a vacancy is matched:

1. Helly finds matching candidates.
2. Helly sends the hiring manager up to `3` candidate profiles at a time for that vacancy.
3. Under each profile the manager can choose:
   - `Interview`
   - `Skip`
4. If the manager chooses `Interview`, the candidate receives an interview invitation.
5. If the candidate accepts, the manager receives an acknowledgement that the candidate accepted and interview is now pending or started.
6. If the candidate rejects, the manager receives a message that the candidate declined the opportunity.
7. Helly must not keep more than `10` simultaneously active interview-pipeline candidates per vacancy.
8. If the vacancy already has `10` active interview-pipeline candidates, Helly must stop offering more and tell the manager to wait until active candidates finish or drop out.

## 2.2 Candidate-Side Flow

When a candidate is matched:

1. Helly sends the candidate up to `3` matched vacancies at a time.
2. Under each vacancy the candidate can choose:
   - `Apply`
   - `Skip`
3. If the candidate chooses `Apply`, the manager receives the candidate profile plus:
   - `Interview`
   - `Skip`
4. If the manager chooses `Interview`, the candidate receives an interview invitation and the interview begins immediately if no other interview is active.
5. If the manager chooses `Skip`, the candidate receives a rejection/skip notification.
6. A candidate may have up to `10` active applications at once.
7. Once the candidate has `10` active applications, Helly stops surfacing more roles and asks the candidate to wait for manager decisions.

## 2.3 Interview Queue

Interview concurrency rules:

- A candidate may have only `1` active interview in progress at a time.
- If a candidate accepts another interview while one is already active, the accepted interview goes into a queue.
- Queued interviews begin only after the active interview is finished or cancelled.
- If the candidate aborts an interview before completion, the system treats it as a decline for that vacancy.

## 2.4 Manager Visibility

Manager visibility becomes two-step:

1. pre-interview candidate profile review
2. post-interview result package review

Managers should no longer have to wait for interview completion before seeing a candidate profile.

## 3. Target Lifecycle Model

The current single `Match.status` string is too overloaded for this redesign.

The target lifecycle should distinguish:

- matching visibility state
- manager pre-interview decision state
- candidate pre-interview decision state
- interview queue state
- post-interview review state
- terminal outcome

Recommended target states:

### 3.1 Pre-Interview Discovery

- `shortlisted`
- `manager_decision_pending`
- `candidate_decision_pending`

### 3.2 Explicit Decisions

- `manager_interview_requested`
- `manager_skipped`
- `candidate_applied`
- `candidate_skipped`
- `candidate_declined_interview`

### 3.3 Interview Pipeline

- `interview_queued`
- `invited`
- `accepted`
- `interview_completed`
- `manager_review`

### 3.4 Terminal Outcomes

- `approved`
- `rejected`
- `auto_rejected`
- `expired`

Important rule:

- manager-driven and candidate-driven entry into the interview pipeline must converge to the same interview/session runtime

## 4. Hard Product Constraints

Canonical limits:

- manager presentation batch size per vacancy: `3`
- candidate presentation batch size per candidate: `3`
- max active interview-pipeline candidates per vacancy: `10`
- max active applications per candidate: `10`
- max active interview sessions per candidate: `1`

Canonical behavioral constraints:

- no auto-invite immediately after matching
- pre-interview candidate package must be visible to the manager
- candidate can receive matched roles before manager approval
- interview start depends on both sides and queue availability
- abandoning interview counts as decline

## 5. Ordered Task List

## Phase A. Freeze Documentation and Domain Contract

1. Add this redesign document to `docs/`.
2. Add canonical status constants for the new match lifecycle.
3. Add canonical constants for:
   - batch size `3`
   - max active vacancy interview pipeline `10`
   - max active candidate applications `10`
   - max active interview sessions per candidate `1`
4. Add pure policy helpers for:
   - vacancy slot availability
   - candidate application slot availability
   - interview queue decision
5. Update architecture/state-machine docs after runtime begins to move.

## Phase B. Stop Auto-Invite and Introduce Pre-Interview Manager Review

6. Remove automatic `interview_dispatch_invites_v1` dispatch immediately after `shortlisted_count > 0`.
7. Add a new pre-interview manager-visible match state.
8. After matching, move the top candidates into manager review batches instead of candidate invite waves.
9. Send manager-facing candidate packages in batches of `3`.
10. Add new manager reply actions:
    - `Interview candidate`
    - `Skip candidate`
11. Update manager stage routing and prompts to support this new decision stage.
12. Keep post-interview `manager_review` separate from pre-interview selection.

## Phase C. Candidate-Side Vacancy Feed Before Interview

13. Add candidate-visible matched vacancy cards in batches of `3`.
14. Add candidate actions:
    - `Apply`
    - `Skip`
15. When candidate applies:
    - persist that state on the match
    - notify the vacancy manager with the candidate profile
16. When candidate skips:
    - persist terminal skip state
    - move on to the next candidate-visible role
17. Block new role presentation once the candidate has `10` active applications.

## Phase D. Manager Decisions on Candidate Applications

18. When a candidate applies, send the manager the candidate profile with:
    - `Interview candidate`
    - `Skip candidate`
19. If the manager skips:
    - notify candidate that the vacancy did not move forward
20. If the manager requests interview:
    - move the match into candidate interview-decision state
    - notify candidate
21. Ensure this path converges with manager-first discovery path.

## Phase E. Candidate Interview Invitation and Queueing

22. Support candidate responses to interview request:
    - `Accept interview`
    - `Skip opportunity`
23. On accept:
    - if no interview is active, start immediately
    - otherwise create queued interview state
24. On skip:
    - notify manager that the candidate declined the interview invitation
25. Add queue-start logic when an active interview completes or is cancelled.

## Phase F. Vacancy and Candidate Cap Enforcement

26. Add vacancy-level active pipeline counting.
27. Add candidate-level active application counting.
28. Stop sending more manager-visible candidates once vacancy cap `10` is reached.
29. Stop sending more candidate-visible vacancies once candidate cap `10` is reached.
30. Add clear user-facing wait messages for both caps.

## Phase G. Interview Abort = Candidate Decline

31. Add candidate interview cancellation/abort action.
32. If the candidate aborts mid-interview:
    - mark the match as candidate-declined
    - close or cancel the interview session
    - notify the manager
33. Start the next queued interview, if any.

## Phase H. Notifications and UX Copy

34. Add manager-facing copies for:
    - candidates available now
    - candidate accepted interview
    - candidate rejected interview
    - vacancy cap reached
35. Add candidate-facing copies for:
    - matched roles available now
    - manager invited to interview
    - manager skipped after apply
    - application cap reached
    - interview queued
    - queued interview started
36. Add or update Telegram keyboards for:
    - manager pre-interview decision
    - candidate vacancy apply/skip
    - interview queue messaging

## Phase I. Graph and Stage-Agent Migration

37. Add new graph-owned stage(s) for manager pre-interview selection.
38. Add new graph-owned stage(s) for candidate applied / vacancy selection.
39. Update stage resolution priority so:
    - active interview
    - queued interview
    - pending interview invitation
    - manager pre-interview review
    - candidate vacancy review
    - baseline `READY` / `OPEN`
40. Update prompt catalog and tests for all new stages and actions.

## Phase J. Data, Migration, and Backfill

41. Add migration(s) if new columns or auxiliary queue tables are required.
42. Backfill or safely tolerate legacy `matches` created under auto-invite logic.
43. Add compatibility behavior so old `invited` / `manager_review` rows do not break stage resolution.

## Phase K. Testing and Rollout

44. Add unit tests for policy helpers and queue limits.
45. Add matching/service tests for pre-interview batching.
46. Add Telegram routing tests for manager/candidate decision buttons.
47. Add interview tests for queued start and abort-as-decline.
48. Run live smoke on production with:
    - one vacancy
    - at least two candidates
    - manager-first review path
    - candidate-first apply path
49. Verify no more than `10` active interview-pipeline matches per vacancy.
50. Verify only `1` active interview per candidate.

## 6. Recommended Execution Order

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
11. Phase K

Do not start candidate-facing vacancy apply flow before manager-side pre-interview decision flow is stable.

Do not add queueing before the system has explicit dual-sided decision states.

## 7. Immediate Execution Slice

The first execution slice should be:

1. add the documentation
2. add lifecycle constants and policy helpers
3. remove auto-invite coupling from the matching happy path
4. replace it with manager pre-interview review batching

This is the smallest coherent slice that actually moves the product toward the new behavior.
