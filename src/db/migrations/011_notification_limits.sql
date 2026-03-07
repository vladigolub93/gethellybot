create table if not exists public.notification_limits (
  id bigserial primary key,
  telegram_user_id bigint not null,
  role text not null check (role in ('candidate', 'manager')),
  last_candidate_notify_at timestamptz,
  last_manager_notify_at timestamptz,
  daily_count integer not null default 0,
  daily_reset_at timestamptz,
  updated_at timestamptz not null default now(),
  unique (telegram_user_id, role)
);

create index if not exists notification_limits_telegram_user_id_idx
  on public.notification_limits (telegram_user_id);
