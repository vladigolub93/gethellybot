import { Request, Response, Router } from "express";
import { Logger } from "../config/logger";
import { LlmGateDispatcher } from "../router/dispatch/llm-gate.dispatcher";

interface WebhookControllerDeps {
  dispatcher: LlmGateDispatcher;
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

    try {
      await deps.dispatcher.handleIncomingUpdate(request.body);
      response.status(200).json({ ok: true });
    } catch (error) {
      deps.logger.error("Failed to process Telegram update", {
        updateId:
          typeof request.body?.update_id === "number" ? request.body.update_id : undefined,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      response.status(200).json({ ok: true });
    }
  });

  return router;
}
