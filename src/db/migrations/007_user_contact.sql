alter table public.users
  add column if not exists phone_number text;

alter table public.users
  add column if not exists first_name text;

alter table public.users
  add column if not exists last_name text;

alter table public.users
  add column if not exists contact_shared boolean not null default false;

alter table public.users
  add column if not exists contact_shared_at timestamptz;
