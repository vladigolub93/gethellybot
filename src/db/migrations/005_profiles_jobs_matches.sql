create table if not exists public.profiles (
  id bigserial primary key,
  telegram_user_id bigint not null,
  kind text not null check (kind in ('candidate', 'job')),
  profile_json jsonb not null,
  searchable_text text not null,
  embedding vector(1536),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (telegram_user_id, kind)
);

create index if not exists profiles_kind_idx
  on public.profiles (kind);

create table if not exists public.jobs (
  id bigserial primary key,
  manager_telegram_user_id bigint not null unique,
  status text not null default 'draft',
  job_summary text not null default '',
  job_profile jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists jobs_status_idx
  on public.jobs (status);

create table if not exists public.matches (
  id text primary key,
  manager_telegram_user_id bigint not null,
  candidate_telegram_user_id bigint not null,
  job_summary text not null,
  candidate_summary text not null,
  score double precision not null,
  explanation text not null,
  candidate_decision text not null,
  manager_decision text not null,
  status text not null,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create index if not exists matches_manager_telegram_user_id_idx
  on public.matches (manager_telegram_user_id);

create index if not exists matches_candidate_telegram_user_id_idx
  on public.matches (candidate_telegram_user_id);
