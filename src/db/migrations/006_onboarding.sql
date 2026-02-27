alter table public.users
  add column if not exists role text;

alter table public.users
  add column if not exists onboarding_completed boolean not null default false;

alter table public.users
  add column if not exists first_match_explained boolean not null default false;

alter table public.users
  add column if not exists created_at timestamptz not null default now();
