interface UserRateState {
  timestamps: number[];
}

const WINDOW_MS = 30_000;
const MAX_MESSAGES_PER_WINDOW = 10;
const userRateMap = new Map<number, UserRateState>();

export interface RateLimitDecision {
  allowed: boolean;
  retryAfterSeconds: number;
}

export function checkAndConsumeUserRateLimit(telegramUserId: number): RateLimitDecision {
  const now = Date.now();
  const current = userRateMap.get(telegramUserId) ?? { timestamps: [] };
  const filtered = current.timestamps.filter((timestamp) => now - timestamp < WINDOW_MS);

  if (filtered.length >= MAX_MESSAGES_PER_WINDOW) {
    const oldestInWindow = filtered[0] ?? now;
    const retryMs = Math.max(1_000, WINDOW_MS - (now - oldestInWindow));
    userRateMap.set(telegramUserId, { timestamps: filtered });
    return {
      allowed: false,
      retryAfterSeconds: Math.ceil(retryMs / 1_000),
    };
  }

  filtered.push(now);
  userRateMap.set(telegramUserId, { timestamps: filtered });
  return {
    allowed: true,
    retryAfterSeconds: 0,
  };
}
