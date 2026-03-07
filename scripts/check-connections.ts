/**
 * Проверка подключения к Supabase и Qdrant по .env.
 * Запуск: npx ts-node scripts/check-connections.ts
 */

import dotenv from "dotenv";
import fetch from "node-fetch";

dotenv.config();

const SUPABASE_URL = process.env.SUPABASE_URL?.trim();
const SUPABASE_KEY =
  process.env.SUPABASE_SERVICE_ROLE_KEY?.trim() ||
  process.env.SUPABASE_PUBLISHABLE_KEY?.trim();
const QDRANT_URL = process.env.QDRANT_URL?.trim();
const QDRANT_API_KEY = process.env.QDRANT_API_KEY?.trim();
const QDRANT_COLLECTION =
  process.env.QDRANT_CANDIDATE_COLLECTION?.trim() || "helly_candidates_v1";

async function checkSupabase(): Promise<{ ok: boolean; message: string }> {
  if (!SUPABASE_URL || !SUPABASE_KEY) {
    return {
      ok: false,
      message: "SUPABASE_URL или SUPABASE_SERVICE_ROLE_KEY не заданы в .env",
    };
  }
  try {
    const url = `${SUPABASE_URL.replace(/\/+$/, "")}/rest/v1/users?select=telegram_user_id&limit=1`;
    const res = await fetch(url, {
      method: "GET",
      headers: {
        apikey: SUPABASE_KEY,
        authorization: `Bearer ${SUPABASE_KEY}`,
        accept: "application/json",
      },
    });
    if (res.ok) {
      return { ok: true, message: `OK (HTTP ${res.status})` };
    }
    const text = await res.text();
    return { ok: false, message: `HTTP ${res.status}: ${text.slice(0, 200)}` };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, message: `Ошибка: ${msg}` };
  }
}

async function checkQdrant(): Promise<{ ok: boolean; message: string }> {
  if (!QDRANT_URL) {
    return { ok: false, message: "QDRANT_URL не задан в .env" };
  }
  const base = QDRANT_URL.replace(/\/+$/, "");
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (QDRANT_API_KEY) {
    headers["api-key"] = QDRANT_API_KEY;
  }
  try {
    const url = `${base}/collections/${encodeURIComponent(QDRANT_COLLECTION)}`;
    const res = await fetch(url, { method: "GET", headers });
    if (res.ok) {
      const data = (await res.json()) as { result?: { points_count?: number } };
      const count = data?.result?.points_count ?? "?";
      return { ok: true, message: `OK, коллекция "${QDRANT_COLLECTION}", points: ${count}` };
    }
    if (res.status === 404) {
      return {
        ok: true,
        message: `Коллекция "${QDRANT_COLLECTION}" ещё не создана (404) — будет создана при первом бэкфилле`,
      };
    }
    const text = await res.text();
    return { ok: false, message: `HTTP ${res.status}: ${text.slice(0, 200)}` };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, message: `Ошибка: ${msg}` };
  }
}

async function main(): Promise<void> {
  console.log("Проверка подключений (из .env)...\n");

  const supabase = await checkSupabase();
  console.log("Supabase:", supabase.ok ? "✓" : "✗", supabase.message);

  const qdrant = await checkQdrant();
  console.log("Qdrant:  ", qdrant.ok ? "✓" : "✗", qdrant.message);

  console.log("");
  if (supabase.ok && qdrant.ok) {
    console.log("Оба подключения в порядке.");
  } else {
    process.exitCode = 1;
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
