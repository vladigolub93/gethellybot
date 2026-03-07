# Database schema reference

Все таблицы в схеме `public`. Миграции применяются по порядку номеров.

## Таблицы и ключевые колонки

### users (004, 006, 007, 010, 012, 014, 015)
- id, telegram_user_id (unique), telegram_username, role, created_at, updated_at
- onboarding_completed, first_match_explained (006)
- phone_number, first_name, last_name, contact_shared, contact_shared_at (007)
- preferred_language (014)
- auto_matching_enabled, auto_notify_enabled (015)
- matching_paused, matching_paused_at (012)
- candidate_country, candidate_city, candidate_work_mode, candidate_salary_amount, candidate_salary_currency, candidate_salary_period, candidate_profile_complete (010)

### user_states (004, 016)
- telegram_user_id (PK), chat_id, telegram_username, role, state, state_payload (jsonb), updated_at
- last_bot_message (016)

### profiles (005, 007, 008, 009, 018)
- id, telegram_user_id, kind (candidate|job), profile_json, searchable_text, embedding (vector), created_at, updated_at
- raw_resume_analysis_json, profile_status (007)
- technical_summary_json (008)
- source_type, source_text_original, source_text_english, telegram_file_id (009)
- last_confirmation_one_liner (018)

### jobs (005, 008, 009, 010_jobs_profile_and_summary, 011, 018, 020)
- id, manager_telegram_user_id (unique), status, job_summary, job_profile, updated_at
- source_type, source_text_original, source_text_english, telegram_file_id, created_at (008)
- job_analysis_json, manager_interview_plan_json (009)
- job_profile_json, technical_summary_json (010_jobs_profile_and_summary)
- job_work_format, job_remote_countries, job_remote_worldwide, job_budget_min, job_budget_max, job_budget_currency, job_budget_period, job_profile_complete (011)
- last_confirmation_one_liner (018)
- created_by_user_id (020)

### matches (005, 003_matches_v2)
- id (PK), manager_telegram_user_id, candidate_telegram_user_id, job_summary, candidate_summary, score, explanation, candidate_decision, manager_decision, status, created_at, updated_at
- job_id, candidate_id (uuid), total_score, breakdown_json, reasons_json, explanation_json, matching_decision_json, job_technical_summary_json, candidate_technical_summary_json (003_matches_v2)

### candidate_profiles, job_profiles (021)
- canonical v2 profile storage with profile_text, embedding, embedding_metadata

### notification_limits (011_notification_limits)
- id, telegram_user_id, role, last_candidate_notify_at, last_manager_notify_at, daily_count, daily_reset_at, updated_at, unique(telegram_user_id, role)

### telegram_updates (014)
- update_id (PK), telegram_user_id, received_at

### data_deletion_requests (013)
- telegram_user_id (PK), telegram_username, reason, status, requested_at, updated_at

### interviews (019)
- id, telegram_user_id, role_context, status, current_question_index, plan_json, answers_json, created_at, updated_at

### quality_flags (012_quality_flags)
- id (uuid), entity_type, entity_id, flag, details (jsonb), created_at

## Миграция 022

Добавляет с `ADD COLUMN IF NOT EXISTS` все перечисленные колонки для `matches`, `users`, `user_states`, чтобы при любом порядке применения миграций схема оставалась полной.
