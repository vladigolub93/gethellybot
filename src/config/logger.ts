import fetch from "node-fetch";

type LogLevel = "debug" | "info" | "warn" | "error";

const LOG_LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

export interface Logger {
  debug(message: string, meta?: Record<string, unknown>): void;
  info(message: string, meta?: Record<string, unknown>): void;
  warn(message: string, meta?: Record<string, unknown>): void;
  error(message: string, meta?: Record<string, unknown>): void;
}

interface CreateLoggerOptions {
  telegram?: {
    enabled: boolean;
    token: string;
    chatId?: string;
    minLevel: LogLevel;
    ratePerMinute: number;
    batchMs: number;
  };
}

export interface LoggerContext {
  update_id?: number;
  telegram_user_id?: number;
  role?: string;
  current_state?: string;
  route?: string;
  action?: string;
  prompt_name?: string;
  model_name?: string;
  latency_ms?: number;
  did_call_llm_router?: boolean;
  did_call_task_prompt?: boolean;
  handler_selected?: string;
  reply_sent?: boolean;
  ok?: boolean;
  error_code?: string;
}

interface SinkEntry {
  level: LogLevel;
  message: string;
  meta?: Record<string, unknown>;
  timestamp: string;
}

function log(
  level: LogLevel,
  message: string,
  meta?: Record<string, unknown>,
  sink?: TelegramLogSink,
): void {
  const payload: Record<string, unknown> = {
    timestamp: new Date().toISOString(),
    level,
    message,
  };
  if (meta) {
    payload.meta = meta;
  }
  process.stdout.write(`${JSON.stringify(payload)}\n`);
  sink?.enqueue({
    level,
    message,
    meta,
    timestamp: payload.timestamp as string,
  });
}

export function createLogger(options?: CreateLoggerOptions): Logger {
  const sink = buildTelegramLogSink(options?.telegram);
  return {
    debug(message, meta) {
      log("debug", message, meta, sink);
    },
    info(message, meta) {
      log("info", message, meta, sink);
    },
    warn(message, meta) {
      log("warn", message, meta, sink);
    },
    error(message, meta) {
      log("error", message, meta, sink);
    },
  };
}

export function logContext(
  logger: Logger,
  level: LogLevel,
  message: string,
  context: LoggerContext,
  fields?: Record<string, unknown>,
): void {
  const meta: Record<string, unknown> = {
    ...context,
    ...(fields ?? {}),
  };

  if (level === "debug") {
    logger.debug(message, meta);
    return;
  }
  if (level === "warn") {
    logger.warn(message, meta);
    return;
  }
  if (level === "error") {
    logger.error(message, meta);
    return;
  }
  logger.info(message, meta);
}

class TelegramLogSink {
  private readonly queue: SinkEntry[] = [];
  private flushTimer: NodeJS.Timeout | null = null;
  private windowStartMs = Date.now();
  private sentInWindow = 0;

  constructor(
    private readonly token: string,
    private readonly chatId: string,
    private readonly minLevel: LogLevel,
    private readonly ratePerMinute: number,
    private readonly batchMs: number,
  ) {}

  enqueue(entry: SinkEntry): void {
    if (!shouldSendToSink(entry.level, this.minLevel)) {
      return;
    }
    this.queue.push(entry);
    this.scheduleFlush();
  }

  private scheduleFlush(): void {
    if (this.flushTimer) {
      return;
    }
    this.flushTimer = setTimeout(() => {
      void this.flush();
    }, this.batchMs);
  }

  private async flush(): Promise<void> {
    this.flushTimer = null;
    if (!this.queue.length) {
      return;
    }
    if (!this.tryConsumeRateWindow()) {
      this.scheduleFlush();
      return;
    }

    const batch = this.queue.splice(0, 5);
    const text = formatTelegramLogBatch(batch);
    try {
      await sendToTelegram(this.token, this.chatId, text);
    } catch {
      // Logging must never break application flow.
    } finally {
      if (this.queue.length) {
        this.scheduleFlush();
      }
    }
  }

  private tryConsumeRateWindow(): boolean {
    const now = Date.now();
    if (now - this.windowStartMs >= 60_000) {
      this.windowStartMs = now;
      this.sentInWindow = 0;
    }
    if (this.sentInWindow >= this.ratePerMinute) {
      return false;
    }
    this.sentInWindow += 1;
    return true;
  }
}

function buildTelegramLogSink(
  config: CreateLoggerOptions["telegram"] | undefined,
): TelegramLogSink | undefined {
  if (!config?.enabled) {
    return undefined;
  }
  const token = config.token.trim();
  const chatId = config.chatId?.trim();
  if (!token || !chatId) {
    return undefined;
  }
  return new TelegramLogSink(
    token,
    chatId,
    config.minLevel,
    Math.max(1, Math.floor(config.ratePerMinute)),
    Math.max(300, Math.floor(config.batchMs)),
  );
}

function shouldSendToSink(level: LogLevel, minLevel: LogLevel): boolean {
  return LOG_LEVEL_ORDER[level] >= LOG_LEVEL_ORDER[minLevel];
}

function formatTelegramLogBatch(entries: SinkEntry[]): string {
  const blocks = entries.map((entry) => {
    const redactedMeta = entry.meta ? redactMeta(entry.meta) : undefined;
    const metaText = redactedMeta ? `\nmeta: ${safeJson(redactedMeta)}` : "";
    return `[${entry.level.toUpperCase()}] ${entry.timestamp}\n${entry.message}${metaText}`;
  });
  return truncateMessage(blocks.join("\n\n---\n\n"), 3800);
}

function redactMeta(meta: Record<string, unknown>): Record<string, unknown> {
  const output: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(meta)) {
    const lowerKey = key.toLowerCase();
    if (
      lowerKey.includes("token") ||
      lowerKey.includes("secret") ||
      lowerKey.includes("apikey") ||
      lowerKey.includes("api_key") ||
      lowerKey.includes("authorization")
    ) {
      output[key] = "[REDACTED]";
      continue;
    }
    if (typeof value === "string" && value.length > 500) {
      output[key] = `${value.slice(0, 500)}...`;
      continue;
    }
    output[key] = value;
  }
  return output;
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value);
  } catch {
    return "\"[unserializable]\"";
  }
}

function truncateMessage(text: string, maxChars: number): string {
  if (text.length <= maxChars) {
    return text;
  }
  return `${text.slice(0, maxChars - 3)}...`;
}

async function sendToTelegram(token: string, chatId: string, text: string): Promise<void> {
  const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      disable_web_page_preview: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`telegram_log_send_failed_http_${response.status}`);
  }
}
