alter table public.users
  add column if not exists matching_paused boolean not null default false;

alter table public.users
  add column if not exists matching_paused_at timestamptz null;

