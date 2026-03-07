-- Core user and state storage for durable bot sessions.
create table if not exists public.users (
  id bigserial primary key,
  telegram_user_id bigint not null unique,
  telegram_username text,
  role text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.user_states (
  telegram_user_id bigint primary key,
  chat_id bigint not null,
  telegram_username text,
  role text,
  state text not null,
  state_payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists user_states_role_idx on public.user_states (role);
