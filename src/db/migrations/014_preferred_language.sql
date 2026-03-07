alter table public.users
  add column if not exists preferred_language text;

alter table public.users
  alter column preferred_language set default 'unknown';
