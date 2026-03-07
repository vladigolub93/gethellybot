# Deployment Checklist

## 1. Required environment variables

**Required (app won’t start without these):**
- `NODE_ENV=production`
- `DEBUG_MODE=false`
- `PORT`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_PATH`
- `TELEGRAM_WEBHOOK_URL`
- `TELEGRAM_SECRET_TOKEN`
- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL` (e.g. `gpt-4o`)
- `OPENAI_EMBEDDINGS_MODEL` (e.g. `text-embedding-3-large`)
- `OPENAI_TRANSCRIPTION_MODEL=whisper-1`
- `VOICE_MAX_DURATION_SEC=180`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

**Optional but recommended:**
- `TELEGRAM_REACTIONS_ENABLED=true`
- `TELEGRAM_REACTIONS_PROBABILITY=0.12`
- `SUPABASE_PUBLISHABLE_KEY` (if different from service role)
- `ADMIN_SECRET` — для админ-веб и `GET /admin/db-status` (проверка прода)
- `ADMIN_USER_IDS` — comma-separated Telegram user IDs админов
- `ADMIN_TELEGRAM_CHAT_ID` — чат для алертов (Stage 11)
- `ADMIN_LOG_LEVEL=warn` — минимальный уровень для отправки в админ-чат

**Dialogue V2 (ответы через LLM):**
- `DIALOGUE_V2_ENABLED=true`
- `CONVERSATION_STATE_V2_ENABLED=true`

**Vector search (матчинг):**
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `QDRANT_CANDIDATE_COLLECTION=helly_candidates_v1`
- `QDRANT_BACKFILL_ON_START=true`

## 2. Build and start
1. `npm ci`
2. `npm run build`
3. `npm start`

## 3. Database migrations
Run SQL migrations in Supabase SQL editor **in order by filename** (001, 002, … 022).
Папка: `src/db/migrations/`. Описание схемы: `src/db/migrations/README_SCHEMA.md`.

Обязательно должны быть применены (в т.ч. после недавнего деплоя):
- `021_profile_v2_store.sql` — таблицы candidate_profiles, job_profiles
- `022_ensure_matches_and_users_columns.sql` — недостающие колонки у matches, users, user_states

Проверка: таблицы `users`, `user_states`, `profiles`, `jobs`, `matches`, `candidate_profiles`, `job_profiles`, `telegram_updates`, `notification_limits`, `quality_flags`, `data_deletion_requests` существуют; в Supabase Dashboard → SQL можно вызвать `get_applied_migrations_count()` (миграция 017).

## 4. Telegram webhook with secret token
Use:
`POST https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook`
Body:
```json
{
  "url": "https://<your-domain><TELEGRAM_WEBHOOK_PATH>",
  "secret_token": "<TELEGRAM_SECRET_TOKEN>"
}
```

## 5. Host recommendations
- Railway or Render is recommended for webhook bots, stable always-on Node process.
- Vercel is optional only when long running work is offloaded, due function timeouts and cold starts.

## 6. Health check and production verification
- `GET /health` returns `{ "ok": true }`.
- Webhook endpoint returns 200 for valid Telegram updates.
- Logs include `Qdrant vector search` with `enabled: true` when Qdrant env is configured.

**Скрипт проверки прода (после деплоя):**
```bash
PROD_URL=https://your-app.railway.app ADMIN_SECRET=your_admin_secret npx ts-node scripts/verify-prod.ts
```
Подставь свой URL Railway (или другой хост) и `ADMIN_SECRET` из переменных окружения прода. Скрипт проверит `/health` и при наличии секрета — `/admin/db-status` (таблицы и миграции).

## 7. Post deploy smoke checks
1. `/start` flow, role selection, contact capture.
2. Resume and JD intake by file and pasted text.
3. Interview progression with meta question handling.
4. Matching command handling and pause or resume.
5. Mutual contact exchange guard.
6. Data deletion command.

## 8. Rollback plan
1. Disable webhook:
`POST https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook`
2. Re-deploy previous known stable release.
3. Re-enable webhook for previous release URL.
