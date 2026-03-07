# Migrations

Alembic migrations for Helly v1.

## Commands

Apply all migrations:

```bash
alembic upgrade head
```

Show current revision:

```bash
alembic current
```

## Notes

- The database target is Supabase Postgres.
- `pgvector` extension is created in the initial migration.
- New migrations should keep schema aligned with `docs/HELLY_V1_DATA_MODEL_AND_ERD.md`.

