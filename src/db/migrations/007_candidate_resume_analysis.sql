alter table public.profiles
  add column if not exists raw_resume_analysis_json jsonb;

alter table public.profiles
  add column if not exists profile_status text;

create index if not exists profiles_profile_status_idx
  on public.profiles (profile_status);
