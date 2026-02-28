create table if not exists telegram_updates (
  update_id bigint primary key,
  telegram_user_id bigint not null,
  received_at timestamptz not null default now()
);
