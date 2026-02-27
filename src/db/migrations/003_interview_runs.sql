-- Stores completed interview payloads for MVP persistence in Supabase.
create table if not exists public.interview_runs (
  id bigserial primary key,
  role text not null,
  telegram_user_id bigint not null,
  started_at timestamptz not null,
  completed_at timestamptz not null,
  document_type text not null,
  extracted_text text not null,
  plan_questions jsonb not null,
  answers jsonb not null,
  final_artifact jsonb,
  created_at timestamptz not null default now()
);

create index if not exists interview_runs_telegram_user_id_idx
  on public.interview_runs (telegram_user_id);
