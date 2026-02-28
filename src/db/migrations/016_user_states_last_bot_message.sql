alter table if exists public.user_states
  add column if not exists last_bot_message text;
