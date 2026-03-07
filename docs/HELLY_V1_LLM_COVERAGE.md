# HELLY v1 LLM Coverage

Version: 1.0  
Date: 2026-03-07

## Purpose

This document tracks whether Helly has full LLM prompt coverage at the specification and asset level.

It distinguishes between:

- `Asset Ready`: prompt assets exist in `prompts/`
- `Runtime Wired`: the current code actively uses the capability
- `Planned`: capability is defined but not yet wired into runtime

## Coverage Matrix

| Capability | Asset Status | Runtime Status | Notes |
| --- | --- | --- | --- |
| `bot_controller` | Asset Ready | Planned | main workflow-safe orchestration prompt |
| `candidate_cv_extract` | Asset Ready | Runtime Wired | OpenAI structured extraction active |
| `candidate_summary_merge` | Asset Ready | Runtime Wired | OpenAI structured merge active |
| `candidate_mandatory_field_parse` | Asset Ready | Runtime Wired | OpenAI structured parse active |
| `vacancy_jd_extract` | Asset Ready | Runtime Wired | OpenAI structured extraction active |
| `vacancy_clarification_parse` | Asset Ready | Runtime Wired | OpenAI structured parse active |
| `vacancy_inconsistency_detect` | Asset Ready | Planned | separate precision-focused detection |
| `interview_question_plan` | Asset Ready | Runtime Wired (older shape) | asset is ahead of runtime schema |
| `interview_session_conductor` | Asset Ready | Planned | future turn-by-turn interview agent |
| `interview_followup_decision` | Asset Ready | Planned | needed for one-follow-up-per-topic enforcement |
| `interview_answer_parse` | Asset Ready | Planned | needed for transcript-aware parsing |
| `candidate_rerank` | Asset Ready | Planned | required for full matching pipeline |
| `candidate_evaluate` | Asset Ready | Runtime Wired | OpenAI-backed evaluation active |
| `messaging/recovery` | Asset Ready | Planned | currently mostly template-driven |
| `messaging/small_talk` | Asset Ready | Planned | needed for workflow-safe small talk |
| `messaging/role_selection` | Asset Ready | Planned | optional helper |
| `messaging/deletion_confirmation` | Asset Ready | Planned | blocked by deletion flow implementation |
| `messaging/interview_invitation_copy` | Asset Ready | Planned | current copy is template-based |
| `messaging/response_copywriter` | Asset Ready | Planned | optional refinement layer |

## What Is Covered Now

At the prompt-asset level, Helly now covers the necessary LLM surface for:

- onboarding extraction
- vacancy extraction
- interview planning
- interview conducting logic
- follow-up policy
- answer parsing
- evaluation
- reranking
- recovery and small talk
- top-level bot control

## Remaining Engineering Work

The remaining gap is no longer prompt design coverage. The remaining gap is runtime wiring and surrounding infra:

1. load prompt assets from disk instead of relying on inline prompt strings
2. wire `bot_controller` into Telegram orchestration
3. wire `interview_session_conductor`, `interview_followup_decision`, and `interview_answer_parse` into the interview runtime
4. wire `vacancy_inconsistency_detect` into vacancy extraction
5. wire `candidate_rerank` into the matching pipeline
6. add transcript and document ingestion for non-text flows
7. add deletion flows so deletion messaging prompts can become active

## Conclusion

From the specification and asset perspective, Helly now has complete prompt-family coverage for v1.

The work that remains is implementation wiring, not prompt discovery.
