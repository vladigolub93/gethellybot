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
| `bot_controller` | Asset Ready | Runtime Wired | main workflow-safe orchestration prompt |
| `candidate_cv_extract` | Asset Ready | Runtime Wired | OpenAI structured extraction active |
| `candidate_summary_merge` | Asset Ready | Runtime Wired | OpenAI structured merge active |
| `candidate_mandatory_field_parse` | Asset Ready | Runtime Wired | OpenAI structured parse active |
| `vacancy_jd_extract` | Asset Ready | Runtime Wired | OpenAI structured extraction active |
| `vacancy_clarification_parse` | Asset Ready | Runtime Wired | OpenAI structured parse active |
| `vacancy_inconsistency_detect` | Asset Ready | Runtime Wired | precision-focused ambiguity detection active in vacancy extraction |
| `interview_question_plan` | Asset Ready | Runtime Wired | typed question-plan shape active |
| `interview_session_conductor` | Asset Ready | Runtime Wired | turn-by-turn interview copy generation active |
| `interview_followup_decision` | Asset Ready | Runtime Wired | one-follow-up-per-topic enforcement active |
| `interview_answer_parse` | Asset Ready | Runtime Wired | answer parsing supports follow-up decisions |
| `candidate_rerank` | Asset Ready | Runtime Wired | LLM rerank active after deterministic pool |
| `candidate_evaluate` | Asset Ready | Runtime Wired | OpenAI-backed evaluation active |
| `messaging/recovery` | Asset Ready | Runtime Wired | active via `MessagingService` and `BotControllerService` |
| `messaging/small_talk` | Asset Ready | Runtime Wired | active via `BotControllerService` |
| `messaging/role_selection` | Asset Ready | Runtime Wired | active in onboarding entry flow |
| `messaging/deletion_confirmation` | Asset Ready | Runtime Wired | active in candidate and vacancy deletion flows |
| `messaging/interview_invitation_copy` | Asset Ready | Runtime Wired | active in invitation dispatch |
| `messaging/response_copywriter` | Asset Ready | Runtime Wired | used as centralized messaging refinement layer |

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

The remaining gap is no longer prompt design coverage. The remaining gap is surrounding infra and quality control:

1. add vector retrieval and embedding refresh
2. add cleanup jobs and retention-aware deletion follow-up work
3. continue migrating remaining hard-coded low-priority text into the centralized messaging layer
4. add transcription/OCR confidence policies and fallback handling

## Conclusion

From the specification and runtime perspective, Helly now has complete prompt-family coverage for v1.

The work that remains is platform hardening and retrieval quality, not prompt discovery.
