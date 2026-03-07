-- Additive canonical lifecycle sidecar for matches.
-- Keeps legacy lifecycle fields intact; canonical status is optional.
alter table public.matches
  add column if not exists canonical_match_status text;

