create table if not exists public.candidate_profiles (
  id bigserial primary key,
  telegram_user_id bigint not null unique,
  profile_json jsonb not null default '{}'::jsonb,
  profile_text text not null default '',
  embedding vector,
  embedding_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists candidate_profiles_updated_at_idx
  on public.candidate_profiles (updated_at desc);

create table if not exists public.job_profiles (
  id bigserial primary key,
  telegram_user_id bigint not null unique,
  profile_json jsonb not null default '{}'::jsonb,
  profile_text text not null default '',
  embedding vector,
  embedding_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists job_profiles_updated_at_idx
  on public.job_profiles (updated_at desc);
