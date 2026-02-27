create extension if not exists pgcrypto;

create table if not exists public.quality_flags (
  id uuid primary key default gen_random_uuid(),
  entity_type text not null,
  entity_id text not null,
  flag text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists quality_flags_entity_idx
  on public.quality_flags (entity_type, entity_id);
