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
