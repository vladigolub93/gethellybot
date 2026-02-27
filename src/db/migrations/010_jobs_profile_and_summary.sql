alter table public.jobs
  add column if not exists job_profile_json jsonb;

alter table public.jobs
  add column if not exists technical_summary_json jsonb;
