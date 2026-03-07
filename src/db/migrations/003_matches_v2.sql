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
