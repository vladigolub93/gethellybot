import { allowedActions } from "../allowedActions";
import { GatekeeperConfig, DEFAULT_GATEKEEPER_CONFIG } from "./gatekeeper.config";
import { GatekeeperInput, GatekeeperResult } from "./gatekeeper.types";

const FALLBACK_MESSAGE = "Please continue with the current step.";

export class GatekeeperService {
  constructor(private readonly config: GatekeeperConfig = DEFAULT_GATEKEEPER_CONFIG) {}

  evaluate(input: GatekeeperInput): GatekeeperResult {
    const message = normalizeMessage(input.message);

    if (input.action === null) {
      return {
        accepted: false,
        reason: "NO_ACTION",
        action: null,
        message,
      };
    }

    if (!isConfidenceAcceptable(input.confidence, this.config.minConfidence)) {
      return {
        accepted: false,
        reason: "LOW_CONFIDENCE",
        action: input.action,
        message,
      };
    }

    const stateActions = allowedActions[input.currentState] ?? [];
    if (!stateActions.includes(input.action)) {
      return {
        accepted: false,
        reason: "ACTION_NOT_ALLOWED",
        action: input.action,
        message,
      };
    }

    return {
      accepted: true,
      reason: "ACCEPTED",
      action: input.action,
      message,
    };
  }
}

function isConfidenceAcceptable(confidence: number, minConfidence: number): boolean {
  return Number.isFinite(confidence) && confidence >= minConfidence;
}

function normalizeMessage(message: string): string {
  const trimmed = message.trim();
  return trimmed || FALLBACK_MESSAGE;
}
