alter table if exists public.jobs
  add column if not exists created_by_user_id bigint not null default 0;

