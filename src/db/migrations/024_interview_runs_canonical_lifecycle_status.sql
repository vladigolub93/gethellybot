-- Additive canonical lifecycle sidecar for interview completion records.
-- Keeps legacy interview_runs fields and semantics unchanged.
alter table public.interview_runs
  add column if not exists canonical_interview_status text;

