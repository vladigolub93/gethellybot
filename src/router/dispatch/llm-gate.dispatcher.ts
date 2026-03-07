import { logContext, Logger } from "../../config/logger";
import { StateRouter } from "../state.router";
import { shouldProcessUpdate } from "../../shared/utils/telegram-idempotency";
import { NormalizedUpdate, TelegramUpdate } from "../../shared/types/telegram.types";
import { normalizeUpdate } from "../../telegram/update-normalizer";
import { beginUpdateContext } from "../../telegram/reply-guard";

export interface LlmGateDispatcher {
  handleIncomingUpdate(update: TelegramUpdate | NormalizedUpdate): Promise<void>;
}

interface LlmGateDispatcherDeps {
  stateRouter: StateRouter;
  logger: Logger;
}

export function buildLlmGateDispatcher(deps: LlmGateDispatcherDeps): LlmGateDispatcher {
  return new DefaultLlmGateDispatcher(deps.stateRouter, deps.logger);
}

class DefaultLlmGateDispatcher implements LlmGateDispatcher {
  constructor(
    private readonly stateRouter: StateRouter,
    private readonly logger: Logger,
  ) {}

  async handleIncomingUpdate(update: TelegramUpdate | NormalizedUpdate): Promise<void> {
    const normalized = this.normalize(update);
    if (!normalized) {
      this.logger.debug("Unsupported Telegram update");
      return;
    }

    const shouldProcess = await shouldProcessUpdate(normalized.updateId, normalized.userId);
    if (!shouldProcess) {
      this.logger.debug("Duplicate update ignored by webhook idempotency", {
        updateId: normalized.updateId,
        telegramUserId: normalized.userId,
      });
      return;
    }

    logContext(
      this.logger,
      "info",
      "llm_gate.dispatch.start",
      {
        update_id: normalized.updateId,
        telegram_user_id: normalized.userId,
      },
      {
        kind: normalized.kind,
      },
    );

    beginUpdateContext(normalized.updateId, normalized.userId);
    await this.stateRouter.route(normalized);

    logContext(
      this.logger,
      "info",
      "llm_gate.dispatch.done",
      {
        update_id: normalized.updateId,
        telegram_user_id: normalized.userId,
        ok: true,
      },
      {
        kind: normalized.kind,
      },
    );
  }

  private normalize(update: TelegramUpdate | NormalizedUpdate): NormalizedUpdate | null {
    if (isNormalizedUpdate(update)) {
      return update;
    }
    return normalizeUpdate(update);
  }
}

function isNormalizedUpdate(update: TelegramUpdate | NormalizedUpdate): update is NormalizedUpdate {
  return typeof (update as NormalizedUpdate).kind === "string";
}
