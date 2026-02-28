# Deployment Checklist

## 1. Required environment variables
- `NODE_ENV=production`
- `DEBUG_MODE=false`
- `PORT`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_PATH`
- `TELEGRAM_WEBHOOK_URL`
- `TELEGRAM_SECRET_TOKEN`
- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL=gpt-5.2`
- `OPENAI_EMBEDDINGS_MODEL=text-embedding-3-large`
- `OPENAI_TRANSCRIPTION_MODEL=whisper-1`
- `VOICE_MAX_DURATION_SEC=180`
- `TELEGRAM_REACTIONS_ENABLED=true`
- `TELEGRAM_REACTIONS_PROBABILITY=0.12`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

## 2. Build and start
1. `npm ci`
2. `npm run build`
3. `npm start`

## 3. Database migrations
Run SQL migrations in Supabase SQL editor in order by filename.
Verify these core tables exist:
- `users`
- `user_states`
- `profiles`
- `jobs`
- `matches`
- `telegram_updates`
- `quality_flags`
- `notification_limits`

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

## 6. Health check
Verify:
- `GET /health` returns `{ "ok": true }`.
- Webhook endpoint returns 200 for valid Telegram updates.

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
