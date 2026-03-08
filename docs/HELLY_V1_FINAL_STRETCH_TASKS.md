# HELLY v1 Final Stretch Tasks

Version: 1.0  
Date: 2026-03-08

## Purpose

This document defines the remaining ordered tasks to take Helly from the current near-complete state to a fully validated, polished v1 release candidate.

The focus is no longer core architecture. The focus is:

- live validation
- conversation polish from real transcripts
- media quality hardening
- final production-readiness close-out

## Ordered Task List

1. Run a live Telegram smoke for entry onboarding with a user who has a Telegram `username`.
2. Run a live Telegram smoke for entry onboarding with a user who does not have a `username` and must share contact.
3. Run a live Telegram smoke for candidate `SUMMARY_REVIEW` help questions and confirm the stage agent does not misclassify them as correction requests.
4. Run a live Telegram smoke for candidate `QUESTIONS_PENDING` clarification questions and confirm the stage agent does not misclassify them as final structured answers.
5. Run a live Telegram smoke for manager `VACANCY_SUMMARY_REVIEW` help, correction, and approve paths.
6. Validate every live scenario against Supabase snapshots and Railway `graph_stage_executed` logs, then record the results.
7. Export real candidate onboarding conversation snippets from `raw_messages`. Completed.
8. Export real manager onboarding conversation snippets from `raw_messages`. Completed.
9. Review those transcripts and identify the top 10 robotic or awkward Helly turns. Completed.
10. Map each robotic turn to either a prompt fix, stage-agent decision fix, or runtime microcopy fix. Completed.
11. Apply one more targeted conversation-polish pass based on those real transcript findings. Completed.
12. Re-run the live Telegram smoke scenarios after that polish pass.
13. Add stronger transcript quality controls for noisy or low-confidence voice/video cases.
14. Add stronger OCR / scanned-document quality handling and then perform the final documentation and production-readiness close-out.

## Exit Condition

This final stretch is complete when:

- all key live Telegram scenarios pass
- graph-stage execution is verified in Railway logs
- transcript-derived robotic turns are reviewed and addressed
- conversation polish is validated against real user flows
- media-quality hardening is no longer a major product gap
- implementation status can honestly describe Helly v1 as a validated release candidate
