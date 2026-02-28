create or replace function public.get_db_schema_snapshot()
returns table (
  table_name text,
  columns text[]
)
language sql
security definer
as $$
  select
    c.table_name::text,
    array_agg(c.column_name::text order by c.ordinal_position)::text[] as columns
  from information_schema.columns c
  where c.table_schema = 'public'
  group by c.table_name
  order by c.table_name;
$$;

create or replace function public.get_applied_migrations_count()
returns table (
  applied_migrations_count integer
)
language plpgsql
security definer
as $$
declare
  count_value integer;
begin
  begin
    select count(*)::integer into count_value
    from supabase_migrations.schema_migrations;
  exception
    when others then
      count_value := 0;
  end;

  return query select count_value;
end;
$$;
