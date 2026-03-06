-- Additive canonical lifecycle sidecar for interview start state snapshots.
-- Keeps legacy user_states fields and state payload semantics unchanged.
alter table public.user_states
  add column if not exists canonical_interview_status text;

