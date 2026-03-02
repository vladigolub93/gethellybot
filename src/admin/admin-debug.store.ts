/**
 * Stage 11: In-memory store for last route and last N failures per user (admin debug).
 */

export interface LastRouteEntry {
  handler: string;
  source: string;
  at: string;
}

export interface FailureEntry {
  kind: "llm_fail" | "parse_fail" | "guard_block" | "repeat_loop" | "duplicate_reply";
  promptName?: string;
  source?: string;
  at: string;
  detail?: string;
}

const MAX_FAILURES_PER_USER = 5;
const MAX_ROUTES_PER_USER = 1;

const lastRouteByUser = new Map<number, LastRouteEntry>();
const failuresByUser = new Map<number, FailureEntry[]>();

export function recordLastRoute(userId: number, handler: string, source: string): void {
  lastRouteByUser.set(userId, {
    handler,
    source,
    at: new Date().toISOString(),
  });
}

export function getLastRoute(userId: number): LastRouteEntry | null {
  return lastRouteByUser.get(userId) ?? null;
}

export function recordFailure(
  userId: number,
  kind: FailureEntry["kind"],
  opts?: { promptName?: string; source?: string; detail?: string },
): void {
  let list = failuresByUser.get(userId);
  if (!list) {
    list = [];
    failuresByUser.set(userId, list);
  }
  list.unshift({
    kind,
    promptName: opts?.promptName,
    source: opts?.source,
    at: new Date().toISOString(),
    detail: opts?.detail,
  });
  if (list.length > MAX_FAILURES_PER_USER) list.length = MAX_FAILURES_PER_USER;
}

export function getLastFailures(userId: number, limit = 5): FailureEntry[] {
  const list = failuresByUser.get(userId) ?? [];
  return list.slice(0, limit);
}
