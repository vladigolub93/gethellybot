create table if not exists public.interviews (
  id bigserial primary key,
  telegram_user_id bigint not null,
  role_context text not null check (role_context in ('candidate', 'manager')),
  status text not null default 'active' check (status in ('active', 'completed', 'abandoned')),
  current_question_index integer not null default 0,
  plan_json jsonb not null default '{}'::jsonb,
  answers_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists interviews_telegram_user_id_idx
  on public.interviews (telegram_user_id);

