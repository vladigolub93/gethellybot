-- Ensure all columns required by repositories exist (idempotent).
-- Run after all previous migrations; safe to run multiple times.

-- matches: columns from 003_matches_v2 (in case migration order differs)
alter table public.matches
  add column if not exists job_id uuid;

alter table public.matches
  add column if not exists candidate_id uuid;

alter table public.matches
  add column if not exists total_score integer;

alter table public.matches
  add column if not exists breakdown_json jsonb;

alter table public.matches
  add column if not exists reasons_json jsonb;

alter table public.matches
  add column if not exists explanation_json jsonb;

alter table public.matches
  add column if not exists matching_decision_json jsonb;

alter table public.matches
  add column if not exists job_technical_summary_json jsonb;

alter table public.matches
  add column if not exists candidate_technical_summary_json jsonb;

-- users: ensure columns from 006, 007, 012, 014, 015, 010 exist
alter table public.users
  add column if not exists onboarding_completed boolean not null default false;

alter table public.users
  add column if not exists first_match_explained boolean not null default false;

alter table public.users
  add column if not exists phone_number text;

alter table public.users
  add column if not exists first_name text;

alter table public.users
  add column if not exists last_name text;

alter table public.users
  add column if not exists contact_shared boolean not null default false;

alter table public.users
  add column if not exists contact_shared_at timestamptz;

alter table public.users
  add column if not exists preferred_language text;

alter table public.users
  add column if not exists auto_matching_enabled boolean not null default true;

alter table public.users
  add column if not exists auto_notify_enabled boolean not null default true;

alter table public.users
  add column if not exists matching_paused boolean not null default false;

alter table public.users
  add column if not exists matching_paused_at timestamptz;

alter table public.users
  add column if not exists candidate_country text not null default '';

alter table public.users
  add column if not exists candidate_city text not null default '';

alter table public.users
  add column if not exists candidate_work_mode text not null default '';

alter table public.users
  add column if not exists candidate_salary_amount numeric;

alter table public.users
  add column if not exists candidate_salary_currency text;

alter table public.users
  add column if not exists candidate_salary_period text;

alter table public.users
  add column if not exists candidate_profile_complete boolean not null default false;

-- user_states: last_bot_message from 016
alter table public.user_states
  add column if not exists last_bot_message text;
