# Helly Prompt Assets

This directory is the source of truth for production prompt assets.

Rules:

- one capability per folder
- every business-writing capability has a schema
- examples and test cases are versioned with the prompt
- code should eventually load prompts from here instead of embedding long strings

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

Still pending at the runtime wiring level:

- `matching/candidate_rerank`
- `vacancy/inconsistency_detect`
- `interview/followup_decision`
- `interview/session_conductor`
- `interview/answer_parse`
- `orchestrator/bot_controller`
