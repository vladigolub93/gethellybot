alter table public.users
  add column if not exists auto_matching_enabled boolean not null default true;

alter table public.users
  add column if not exists auto_notify_enabled boolean not null default true;
