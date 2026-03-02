alter table public.users
  add column if not exists candidate_country text not null default '';

alter table public.users
  add column if not exists candidate_city text not null default '';

alter table public.users
  add column if not exists candidate_work_mode text not null default '';

alter table public.users
  add column if not exists candidate_salary_amount numeric null;

alter table public.users
  add column if not exists candidate_salary_currency text null;

alter table public.users
  add column if not exists candidate_salary_period text null;

alter table public.users
  add column if not exists candidate_profile_complete boolean not null default false;

update public.users
set candidate_profile_complete = (
  length(trim(coalesce(candidate_country, ''))) > 0 and
  length(trim(coalesce(candidate_city, ''))) > 0 and
  length(trim(coalesce(candidate_work_mode, ''))) > 0 and
  candidate_salary_amount is not null and
  length(trim(coalesce(candidate_salary_currency, ''))) > 0 and
  length(trim(coalesce(candidate_salary_period, ''))) > 0
)
where candidate_profile_complete is distinct from (
  length(trim(coalesce(candidate_country, ''))) > 0
  and length(trim(coalesce(candidate_city, ''))) > 0
  and length(trim(coalesce(candidate_work_mode, ''))) > 0
  and candidate_salary_amount is not null
  and length(trim(coalesce(candidate_salary_currency, ''))) > 0
  and length(trim(coalesce(candidate_salary_period, ''))) > 0
);
