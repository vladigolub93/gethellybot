import { Request, Response, Router } from "express";
import { Logger } from "../config/logger";
import { StateRouter } from "../router/state.router";
import { TelegramUpdate } from "../shared/types/telegram.types";
import { shouldProcessUpdate } from "../shared/utils/telegram-idempotency";
import { normalizeUpdate } from "./update-normalizer";

interface WebhookControllerDeps {
  stateRouter: StateRouter;
  logger: Logger;
  secretToken?: string;
}

function isSecretTokenValid(request: Request, expectedSecretToken?: string): boolean {
  if (!expectedSecretToken) {
    return true;
  }

  const header = request.header("x-telegram-bot-api-secret-token");
  return header === expectedSecretToken;
}

export function buildWebhookController(deps: WebhookControllerDeps): Router {
  const router = Router();

  router.post("/", async (request: Request, response: Response) => {
    if (!isSecretTokenValid(request, deps.secretToken)) {
      response.status(401).json({ ok: false, error: "Invalid Telegram secret token" });
      return;
    }

    if (!request.body || typeof request.body !== "object") {
      response.status(400).json({ ok: false, error: "Invalid body" });
      return;
    }

    const update = request.body as TelegramUpdate;
    const normalized = normalizeUpdate(update);

    if (!normalized) {
      deps.logger.debug("Unsupported Telegram update", { updateId: update.update_id });
      response.status(200).json({ ok: true });
      return;
    }

    try {
      const shouldProcess = await shouldProcessUpdate(normalized.updateId, normalized.userId);
      if (!shouldProcess) {
        deps.logger.debug("Duplicate update ignored by webhook idempotency", {
          updateId: normalized.updateId,
          telegramUserId: normalized.userId,
        });
        response.status(200).json({ ok: true });
        return;
      }
      await deps.stateRouter.route(normalized);
      response.status(200).json({ ok: true });
    } catch (error) {
      deps.logger.error("Failed to process Telegram update", {
        updateId: normalized.updateId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      response.status(200).json({ ok: true });
    }
  });

  return router;
}
