# HELLY v1 Conversation Polish Task List

Version: 1.0  
Date: 2026-03-08

## 1. Purpose

This task list turns the conversation-quality and voice-and-tone documents into execution work.

The target is a more natural, more human, more Telegram-native Helly that feels closer to a high-quality conversational recruiter product.

## 2. Phase A. Shared Prompt Layer

1. Finalize the shared Telegram style rules.
2. Add explicit response choreography rules to the shared layer.
3. Add explicit emoji and reaction policy to the shared layer.
4. Add anti-robotic phrasing rules to the shared layer.
5. Add anti-overexplaining rules to the shared layer.

## 3. Phase B. Highest-Impact Prompt Rewrites

6. Rewrite `CONTACT_REQUIRED` for warmer onboarding.
7. Rewrite `ROLE_SELECTION` for more natural guidance.
8. Rewrite `CV_PENDING` so the bot sounds more helpful and less procedural.
9. Rewrite `SUMMARY_REVIEW` so the bot sounds like a human reviewer, not a form step.
10. Rewrite `QUESTIONS_PENDING` so follow-up questions sound lighter and more natural.
11. Rewrite `VACANCY_SUMMARY_REVIEW` so the manager experience feels polished and recruiter-like.
12. Rewrite `INTERVIEW_INVITED` for a more compelling invitation tone.
13. Rewrite `INTERVIEW_IN_PROGRESS` for more natural pacing and less robotic transitions.
14. Rewrite `MANAGER_REVIEW` to sound more like an experienced recruiting operator.
15. Rewrite `DELETE_CONFIRMATION` so it is clear without sounding cold.

## 4. Phase C. Message Choreography

16. Define what replies should be single-message by default.
17. Define what replies should be split into explanation plus CTA.
18. Add support in the messaging layer for stage agents to emit multiple short user-facing messages.
19. Update the highest-impact stages to use multi-message output where helpful.
20. Add regression coverage for split-message rendering.

## 5. Phase D. Local Context Memory

21. Define the minimal local conversation memory payload per stage. Completed.
22. Feed recent user/bot turns into user-facing stage agents. Completed.
23. Add rules to avoid repeating the same explanation twice in a row. Completed.
24. Add rules to reference the user's most recent concern directly. Completed.
25. Add tests for repeated-question handling. Completed.

## 6. Phase E. Microcopy Cleanup

26. Audit entry-stage user-facing copy for robotic wording. Completed.
27. Audit candidate-stage copy for stiffness and repetition. Completed.
28. Audit manager-stage copy for ATS-like wording. Completed.
29. Audit interview-stage copy for awkward transitions. Completed.
30. Replace generic acknowledgements with more varied natural phrasing. Completed.

## 7. Phase F. Live Transcript Review

31. Collect real conversation snippets from candidate onboarding. Completed.
32. Collect real conversation snippets from manager onboarding. Completed.
33. Identify top 10 robotic turns. Completed.
34. Map each robotic turn to a prompt or messaging fix. Completed.
35. Re-run live smoke after prompt updates.

## 8. Phase G. Final Quality Close-Out

36. Update implementation status with conversation-quality progress. Completed.
37. Update prompt catalog with any new prompt families or multi-message rules.
38. Update live smoke runbook with conversation-quality checkpoints. Completed.
39. Run prompt coverage tests. Completed.
40. Run full regression suite. Completed.
