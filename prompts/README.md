# Helly Prompt Assets

This directory is the source of truth for production prompt assets.

Rules:

- one capability per folder
- every business-writing capability has a schema
- examples and test cases are versioned with the prompt
- code should eventually load prompts from here instead of embedding long strings
- user-facing prompt families should stay grounded in `/Users/vladigolub/Desktop/gethellybot/docs/HELLY_V1_AGENT_KNOWLEDGE_BASE.md`
- every graph-owned stage agent must have a dedicated prompt asset through `orchestrator/state_assistance/<slug>/SYSTEM.md`
- every runtime-loaded `SYSTEM.md` automatically receives the shared Telegram recruiter style rules from `/Users/vladigolub/Desktop/gethellybot/prompts/_shared/TELEGRAM_STYLE.md`

Current active runtime capabilities:

- `candidate/cv_extract`
- `candidate/summary_merge`
- `candidate/mandatory_field_parse`
- `vacancy/jd_extract`
- `vacancy/clarification_parse`
- `interview/question_plan`
- `evaluation/candidate_evaluate`

Prompt families now covered at the asset level:

- `orchestrator/bot_controller`
- `candidate/cv_extract`
- `candidate/summary_merge`
- `candidate/mandatory_field_parse`
- `vacancy/jd_extract`
- `vacancy/clarification_parse`
- `vacancy/inconsistency_detect`
- `interview/question_plan`
- `interview/followup_decision`
- `interview/session_conductor`
- `interview/answer_parse`
- `matching/candidate_rerank`
- `evaluation/candidate_evaluate`
- `messaging/recovery`
- `messaging/small_talk`
- `messaging/role_selection`
- `messaging/deletion_confirmation`
- `messaging/interview_invitation_copy`
- `messaging/response_copywriter`
- graph-owned stage agents:
  - `contact_required`
  - `role_selection`
  - `candidate_cv_pending`
  - `candidate_summary_review`
  - `candidate_questions_pending`
  - `candidate_verification_pending`
  - `candidate_ready`
  - `vacancy_intake_pending`
  - `vacancy_summary_review` (required next manager-stage prompt family)
  - `vacancy_clarification_qa`
  - `vacancy_open`
  - `interview_invited`
  - `interview_in_progress`
  - `manager_review`
  - `delete_confirmation`

Retired from the active stage inventory:

- `consent_required`

Still pending at the runtime wiring level:

- `matching/candidate_rerank`
- `vacancy/inconsistency_detect`
- `interview/followup_decision`
- `interview/session_conductor`
- `interview/answer_parse`
- `orchestrator/bot_controller`
