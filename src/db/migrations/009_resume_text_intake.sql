alter table public.profiles
  add column if not exists source_type text;

alter table public.profiles
  add column if not exists source_text_original text;

alter table public.profiles
  add column if not exists source_text_english text;

alter table public.profiles
  add column if not exists telegram_file_id text;

alter table public.profiles
  add column if not exists created_at timestamptz not null default now();
