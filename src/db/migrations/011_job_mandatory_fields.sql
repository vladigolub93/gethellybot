alter table if exists jobs
  add column if not exists job_work_format text not null default '',
  add column if not exists job_remote_countries text[] null,
  add column if not exists job_remote_worldwide boolean not null default false,
  add column if not exists job_budget_min numeric null,
  add column if not exists job_budget_max numeric null,
  add column if not exists job_budget_currency text null,
  add column if not exists job_budget_period text null,
  add column if not exists job_profile_complete boolean not null default false;

update jobs
set job_profile_complete = (
  length(trim(coalesce(job_work_format, ''))) > 0 and
  (
    job_work_format <> 'remote' or
    job_remote_worldwide = true or
    coalesce(array_length(job_remote_countries, 1), 0) > 0
  ) and
  job_budget_min is not null and
  job_budget_max is not null and
  length(trim(coalesce(job_budget_currency, ''))) > 0 and
  length(trim(coalesce(job_budget_period, ''))) > 0
)
where job_profile_complete is distinct from (
  length(trim(coalesce(job_work_format, ''))) > 0 and
  (
    job_work_format <> 'remote' or
    job_remote_worldwide = true or
    coalesce(array_length(job_remote_countries, 1), 0) > 0
  ) and
  job_budget_min is not null and
  job_budget_max is not null and
  length(trim(coalesce(job_budget_currency, ''))) > 0 and
  length(trim(coalesce(job_budget_period, ''))) > 0
);
