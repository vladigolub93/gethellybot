create index if not exists profiles_embedding_cos_idx
  on public.profiles
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create or replace function public.search_candidate_profiles(
  query_embedding vector(1536),
  match_count integer
)
returns table (
  telegram_user_id bigint,
  similarity double precision,
  profile_json jsonb,
  searchable_text text
)
language sql
stable
as $$
  select
    p.telegram_user_id,
    1 - (p.embedding <=> query_embedding) as similarity,
    p.profile_json,
    p.searchable_text
  from public.profiles p
  where p.kind = 'candidate'
    and p.embedding is not null
  order by p.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;
