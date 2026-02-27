alter table public.jobs
  add column if not exists job_analysis_json jsonb;

alter table public.jobs
  add column if not exists manager_interview_plan_json jsonb;
