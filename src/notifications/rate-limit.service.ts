import { Logger } from "../config/logger";
import {
  NotificationLimitRecord,
  NotificationLimitsRepository,
} from "../db/repositories/notification-limits.repo";

const DEFAULT_DAILY_LIMIT_CANDIDATE = 5;
const DEFAULT_DAILY_LIMIT_MANAGER = 20;

interface LocalLimitRecord extends NotificationLimitRecord {}

export interface RateLimitResult {
  allowed: boolean;
  reason?: string;
}

export class RateLimitService {
  private readonly localStore = new Map<string, LocalLimitRecord>();

  constructor(
    private readonly repository: NotificationLimitsRepository,
    private readonly logger: Logger,
  ) {}

  async checkAndConsumeCandidateNotification(
    telegramUserId: number,
    cooldownHours: number,
    dailyLimit = DEFAULT_DAILY_LIMIT_CANDIDATE,
  ): Promise<RateLimitResult> {
    return this.checkAndConsume({
      telegramUserId,
      role: "candidate",
      cooldownHours,
      dailyLimit,
    });
  }

  async checkAndConsumeManagerNotification(
    telegramUserId: number,
    cooldownHours: number,
    dailyLimit = DEFAULT_DAILY_LIMIT_MANAGER,
  ): Promise<RateLimitResult> {
    return this.checkAndConsume({
      telegramUserId,
      role: "manager",
      cooldownHours,
      dailyLimit,
    });
  }

  async isInCooldown(
    telegramUserId: number,
    role: "candidate" | "manager",
    cooldownHours: number,
  ): Promise<boolean> {
    const record = await this.loadRecord(telegramUserId, role);
    const lastNotifyAt = role === "candidate" ? record.lastCandidateNotifyAt : record.lastManagerNotifyAt;
    if (!lastNotifyAt) {
      return false;
    }
    const hoursSince = hoursBetween(lastNotifyAt, new Date().toISOString());
    return hoursSince < Math.max(0, cooldownHours);
  }

  async hoursSinceLastNotification(
    telegramUserId: number,
    role: "candidate" | "manager",
  ): Promise<number | null> {
    const record = await this.loadRecord(telegramUserId, role);
    const lastNotifyAt = role === "candidate" ? record.lastCandidateNotifyAt : record.lastManagerNotifyAt;
    if (!lastNotifyAt) {
      return null;
    }
    return hoursBetween(lastNotifyAt, new Date().toISOString());
  }

  private async checkAndConsume(input: {
    telegramUserId: number;
    role: "candidate" | "manager";
    cooldownHours: number;
    dailyLimit: number;
  }): Promise<RateLimitResult> {
    const record = await this.loadRecord(input.telegramUserId, input.role);
    const nowIso = new Date().toISOString();

    const normalized = this.normalizeRecord(record, nowIso);
    const lastNotifyAt =
      input.role === "candidate" ? normalized.lastCandidateNotifyAt : normalized.lastManagerNotifyAt;

    if (lastNotifyAt) {
      const elapsedHours = hoursBetween(lastNotifyAt, nowIso);
      if (elapsedHours < Math.max(0, input.cooldownHours)) {
        return {
          allowed: false,
          reason: `cooldown_active_${input.role}`,
        };
      }
    }

    if (normalized.dailyCount >= Math.max(1, input.dailyLimit)) {
      return {
        allowed: false,
        reason: `daily_limit_reached_${input.role}`,
      };
    }

    const updated: NotificationLimitRecord = {
      ...normalized,
      dailyCount: normalized.dailyCount + 1,
      lastCandidateNotifyAt:
        input.role === "candidate" ? nowIso : normalized.lastCandidateNotifyAt,
      lastManagerNotifyAt:
        input.role === "manager" ? nowIso : normalized.lastManagerNotifyAt,
      dailyResetAt: normalized.dailyResetAt,
    };

    await this.saveRecord(updated);

    this.logger.debug("Notification rate limit consumed", {
      telegramUserId: input.telegramUserId,
      role: input.role,
      dailyCount: updated.dailyCount,
      cooldownHours: input.cooldownHours,
    });

    return { allowed: true };
  }

  private async loadRecord(
    telegramUserId: number,
    role: "candidate" | "manager",
  ): Promise<NotificationLimitRecord> {
    const key = buildKey(telegramUserId, role);
    const local = this.localStore.get(key);
    if (local) {
      return local;
    }

    const remote = await this.repository.getByUserAndRole(telegramUserId, role);
    if (remote) {
      this.localStore.set(key, remote);
      return remote;
    }

    const created: NotificationLimitRecord = {
      telegramUserId,
      role,
      lastCandidateNotifyAt: null,
      lastManagerNotifyAt: null,
      dailyCount: 0,
      dailyResetAt: null,
    };
    this.localStore.set(key, created);
    return created;
  }

  private async saveRecord(record: NotificationLimitRecord): Promise<void> {
    const key = buildKey(record.telegramUserId, record.role);
    this.localStore.set(key, record);
    try {
      await this.repository.upsertRecord(record);
    } catch (error) {
      this.logger.warn("Failed to persist notification limit state", {
        telegramUserId: record.telegramUserId,
        role: record.role,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }

  private normalizeRecord(record: NotificationLimitRecord, nowIso: string): NotificationLimitRecord {
    const current = { ...record };
    const resetAt = current.dailyResetAt;
    if (!resetAt) {
      current.dailyResetAt = startOfNextDayUtc(nowIso);
      current.dailyCount = Math.max(0, current.dailyCount);
      return current;
    }

    if (new Date(nowIso).getTime() >= new Date(resetAt).getTime()) {
      current.dailyCount = 0;
      current.dailyResetAt = startOfNextDayUtc(nowIso);
    }

    return current;
  }
}

function buildKey(telegramUserId: number, role: "candidate" | "manager"): string {
  return `${telegramUserId}:${role}`;
}

function hoursBetween(fromIso: string, toIso: string): number {
  const from = new Date(fromIso).getTime();
  const to = new Date(toIso).getTime();
  if (!Number.isFinite(from) || !Number.isFinite(to)) {
    return 9999;
  }
  return Math.max(0, (to - from) / (1000 * 60 * 60));
}

function startOfNextDayUtc(nowIso: string): string {
  const now = new Date(nowIso);
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 0, 0));
  return next.toISOString();
}
