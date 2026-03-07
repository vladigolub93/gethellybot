create table if not exists public.data_deletion_requests (
  telegram_user_id bigint primary key,
  telegram_username text,
  reason text,
  status text not null default 'requested',
  requested_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
