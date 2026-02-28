type LogLevel = "debug" | "info" | "warn" | "error";

export interface Logger {
  debug(message: string, meta?: Record<string, unknown>): void;
  info(message: string, meta?: Record<string, unknown>): void;
  warn(message: string, meta?: Record<string, unknown>): void;
  error(message: string, meta?: Record<string, unknown>): void;
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

function log(level: LogLevel, message: string, meta?: Record<string, unknown>): void {
  const payload: Record<string, unknown> = {
    timestamp: new Date().toISOString(),
    level,
    message,
  };

  if (meta) {
    payload.meta = meta;
  }

  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

export function createLogger(): Logger {
  return {
    debug(message, meta) {
      log("debug", message, meta);
    },
    info(message, meta) {
      log("info", message, meta);
    },
    warn(message, meta) {
      log("warn", message, meta);
    },
    error(message, meta) {
      log("error", message, meta);
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
