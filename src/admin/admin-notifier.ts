/**
 * Stage 11: Push critical errors and key warnings to admin Telegram group/DM.
 * safeNotifyAdmin never throws; use for fire-and-forget alerts.
 */

import fetch from "node-fetch";
import { Logger } from "../config/logger";

export type AdminNotifyLevel = "info" | "warn" | "error";

const LEVEL_ORDER: Record<AdminNotifyLevel, number> = {
  info: 10,
  warn: 20,
  error: 30,
};

export interface AdminNotifyMeta {
  userId?: number;
  chatId?: number;
  phase?: string;
  state?: string;
  promptName?: string;
  updateId?: number;
  source?: string;
  errorStack?: string;
  /** Last 1–2 outbound message hashes when repeat loop triggered */
  lastOutboundHashes?: string[];
  [key: string]: unknown;
}

export interface AdminNotifierConfig {
  botToken: string;
  adminChatId: string;
  minLevel: AdminNotifyLevel;
  logger?: Logger;
}

const MAX_MESSAGE_LENGTH = 3900;

export class AdminNotifier {
  constructor(private readonly config: AdminNotifierConfig) {}

  shouldSend(level: AdminNotifyLevel): boolean {
    if (!this.config.botToken || !this.config.adminChatId) return false;
    return LEVEL_ORDER[level] >= LEVEL_ORDER[this.config.minLevel];
  }

  async notifyAdmin(
    level: AdminNotifyLevel,
    title: string,
    details?: string,
    meta?: AdminNotifyMeta,
  ): Promise<void> {
    if (!this.shouldSend(level)) return;
    const text = formatAdminMessage(level, title, details, meta);
    try {
      const res = await fetch(`https://api.telegram.org/bot${this.config.botToken}/sendMessage`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          chat_id: this.config.adminChatId,
          text: text.slice(0, MAX_MESSAGE_LENGTH),
          disable_web_page_preview: true,
        }),
      });
      if (!res.ok) {
        this.config.logger?.warn("admin_notifier.send_failed", {
          status: res.status,
          level,
          title: title.slice(0, 80),
        });
      }
    } catch (err) {
      this.config.logger?.warn("admin_notifier.send_error", {
        error: err instanceof Error ? err.message : String(err),
        level,
        title: title.slice(0, 80),
      });
      throw err;
    }
  }

  /** Never throws; use for fire-and-forget. */
  safeNotifyAdmin(
    level: AdminNotifyLevel,
    title: string,
    details?: string,
    meta?: AdminNotifyMeta,
  ): void {
    this.notifyAdmin(level, title, details, meta).catch(() => {});
  }
}

function formatAdminMessage(
  level: AdminNotifyLevel,
  title: string,
  details?: string,
  meta?: AdminNotifyMeta,
): string {
  const lines: string[] = [`[${level.toUpperCase()}] ${title}`];
  if (details) lines.push(details);
  if (meta) {
    const keys = ["userId", "chatId", "phase", "state", "promptName", "updateId", "source"];
    const parts: string[] = [];
    for (const k of keys) {
      const v = meta[k];
      if (v !== undefined && v !== null && v !== "") parts.push(`${k}=${v}`);
    }
    if (meta.errorStack) {
      const stack = String(meta.errorStack).split("\n").slice(0, 8).join("\n");
      parts.push(`stack: ${stack}`);
    }
    if (meta.lastOutboundHashes?.length) {
      parts.push(`lastHashes: ${meta.lastOutboundHashes.join(", ")}`);
    }
    if (parts.length) lines.push(parts.join(" | "));
  }
  return lines.join("\n");
}

let defaultNotifier: AdminNotifier | null = null;

export function setDefaultAdminNotifier(notifier: AdminNotifier): void {
  defaultNotifier = notifier;
}

export function getDefaultAdminNotifier(): AdminNotifier | null {
  return defaultNotifier;
}

/** Safe fire-and-forget using default notifier (if set). */
export function safeNotifyAdmin(
  level: AdminNotifyLevel,
  title: string,
  details?: string,
  meta?: AdminNotifyMeta,
): void {
  defaultNotifier?.safeNotifyAdmin(level, title, details, meta);
}
