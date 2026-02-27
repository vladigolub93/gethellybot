alter table public.profiles
  add column if not exists technical_summary_json jsonb;
