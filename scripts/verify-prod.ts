/**
 * Проверка продакшена: health, опционально db-status.
 * Запуск: PROD_URL=https://your-app.railway.app [ADMIN_SECRET=xxx] npx ts-node scripts/verify-prod.ts
 */

import fetch from "node-fetch";

const PROD_URL = process.env.PROD_URL?.replace(/\/+$/, "");
const ADMIN_SECRET = process.env.ADMIN_SECRET;

async function main(): Promise<void> {
  if (!PROD_URL) {
    console.error("Set PROD_URL (e.g. https://your-app.railway.app)");
    process.exit(1);
  }

  const results: { name: string; ok: boolean; detail: string }[] = [];

  // 1. Health
  try {
    const res = await fetch(`${PROD_URL}/health`, { method: "GET" });
    const body = (await res.json()) as { ok?: boolean };
    const ok = res.ok && body?.ok === true;
    results.push({
      name: "GET /health",
      ok,
      detail: ok ? "ok: true" : `status=${res.status} body=${JSON.stringify(body)}`,
    });
  } catch (e) {
    results.push({
      name: "GET /health",
      ok: false,
      detail: e instanceof Error ? e.message : String(e),
    });
  }

  // 2. DB status (optional, if ADMIN_SECRET set)
  if (ADMIN_SECRET) {
    try {
      const url = `${PROD_URL}/admin/db-status?secret=${encodeURIComponent(ADMIN_SECRET)}`;
      const res = await fetch(url, { method: "GET" });
      const body = (await res.json()) as {
        ok?: boolean;
        applied_migrations_count?: number;
        missing_tables?: string[];
        missing_columns?: unknown[];
      };
      const ok = res.ok && body?.ok === true;
      const count = body?.applied_migrations_count ?? 0;
      const missing = (body?.missing_tables?.length ?? 0) + (body?.missing_columns?.length ?? 0);
      results.push({
        name: "GET /admin/db-status",
        ok,
        detail: ok
          ? `migrations=${count}`
          : `status=${res.status} migrations=${count} missing_tables=${body?.missing_tables?.length ?? 0} missing_columns=${body?.missing_columns?.length ?? 0}`,
      });
    } catch (e) {
      results.push({
        name: "GET /admin/db-status",
        ok: false,
        detail: e instanceof Error ? e.message : String(e),
      });
    }
  } else {
    results.push({
      name: "GET /admin/db-status",
      ok: true,
      detail: "skipped (no ADMIN_SECRET)",
    });
  }

  // Output
  console.log("\nProduction verification:", PROD_URL);
  for (const r of results) {
    console.log(r.ok ? "  ✓" : "  ✗", r.name, "—", r.detail);
  }
  const allOk = results.every((r) => r.ok);
  console.log(allOk ? "\nAll checks passed.\n" : "\nSome checks failed.\n");
  process.exit(allOk ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
