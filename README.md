# telegrambot

MVP scaffold for a Telegram-based AI-powered recruitment matching system.

## DB readiness check

After migrations are applied and service is running, verify DB schema readiness:

1. Set `ADMIN_SECRET` in environment.
2. Call endpoint:
   - `GET /admin/db-status`
   - Header: `x-admin-secret: <ADMIN_SECRET>`

Response shape:

```json
{
  "ok": true,
  "missing_tables": [],
  "missing_columns": [],
  "applied_migrations_count": 0
}
```

If `ok` is `false`, apply missing migrations and recheck.

## LLM gate simulation

Run a local dispatcher simulation without Telegram network calls:

```bash
npm run simulate:flow
```

This script checks:
- every mocked update goes through router classification,
- no generic fallback phrase is used,
- meta steps do not force interview advancement.
