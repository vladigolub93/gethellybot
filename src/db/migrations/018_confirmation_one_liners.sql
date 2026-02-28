alter table if exists public.profiles
  add column if not exists last_confirmation_one_liner text;

alter table if exists public.jobs
  add column if not exists last_confirmation_one_liner text;
