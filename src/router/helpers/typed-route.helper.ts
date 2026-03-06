import { Logger } from "../../config/logger";
import { ActionRouterInput, ActionRouterResult } from "../../ai/action-router/action-router.types";
import {
  GatekeeperInput,
  GatekeeperReason,
  GatekeeperResult,
} from "../../core/state/gatekeeper/gatekeeper.types";
import { HellyAction } from "../../core/state/actions";
import { HellyState } from "../../core/state/states";

type TypedClassifier = {
  classify(input: ActionRouterInput): Promise<ActionRouterResult>;
};

type TypedGatekeeper = {
  evaluate(input: GatekeeperInput): GatekeeperResult;
};

export type TypedRouteReason =
  | GatekeeperReason
  | "FEATURE_FLAG_OFF"
  | "UNMAPPED_STATE_OR_MISSING_DEPS"
  | "FAILED_LEGACY_FALLBACK";

export type RunTypedRouteInput = {
  enabled: boolean;
  logPrefix: string;
  userId: number;
  source?: string;
  runtimeState: string;
  userMessage: string;
  expectedCanonicalState: HellyState;
  resolveCanonicalState: (runtimeState: string) => HellyState | null;
  acceptedActions: HellyAction[];
  actionRouterService?: TypedClassifier;
  gatekeeperService?: TypedGatekeeper;
  logger: Pick<Logger, "debug" | "warn">;
};

export type RunTypedRouteResult = {
  usedTypedPath: boolean;
  accepted: boolean;
  action: HellyAction | null;
  reason: TypedRouteReason;
  message: string;
};

const DEFAULT_FALLBACK_MESSAGE = "Please continue with the current step.";

export async function runTypedRoute(input: RunTypedRouteInput): Promise<RunTypedRouteResult> {
  if (!input.enabled) {
    return {
      usedTypedPath: false,
      accepted: false,
      action: null,
      reason: "FEATURE_FLAG_OFF",
      message: DEFAULT_FALLBACK_MESSAGE,
    };
  }

  const canonicalState = input.resolveCanonicalState(input.runtimeState);
  if (
    canonicalState !== input.expectedCanonicalState ||
    !input.actionRouterService ||
    !input.gatekeeperService
  ) {
    input.logger.debug(`${input.logPrefix}.path`, {
      userId: input.userId,
      ...(input.source ? { source: input.source } : {}),
      path: "legacy_fallback",
      reason: "UNMAPPED_STATE_OR_MISSING_DEPS",
      canonicalState,
    });
    return {
      usedTypedPath: false,
      accepted: false,
      action: null,
      reason: "UNMAPPED_STATE_OR_MISSING_DEPS",
      message: DEFAULT_FALLBACK_MESSAGE,
    };
  }

  try {
    const actionRouterResult = await input.actionRouterService.classify({
      userMessage: input.userMessage,
      currentState: canonicalState,
    });
    input.logger.debug(`${input.logPrefix}.action_router_result`, {
      userId: input.userId,
      ...(input.source ? { source: input.source } : {}),
      currentState: input.runtimeState,
      action: actionRouterResult.action,
      confidence: actionRouterResult.confidence,
    });

    const gatekeeperResult = input.gatekeeperService.evaluate({
      currentState: canonicalState,
      action: actionRouterResult.action,
      confidence: actionRouterResult.confidence,
      message: actionRouterResult.message,
    });
    input.logger.debug(`${input.logPrefix}.gatekeeper_result`, {
      userId: input.userId,
      ...(input.source ? { source: input.source } : {}),
      accepted: gatekeeperResult.accepted,
      reason: gatekeeperResult.reason,
      action: gatekeeperResult.action,
    });

    const accepted =
      gatekeeperResult.accepted &&
      gatekeeperResult.action !== null &&
      input.acceptedActions.includes(gatekeeperResult.action);
    if (accepted) {
      input.logger.debug(`${input.logPrefix}.path`, {
        userId: input.userId,
        ...(input.source ? { source: input.source } : {}),
        path: "typed",
        action: gatekeeperResult.action,
      });
      return {
        usedTypedPath: true,
        accepted: true,
        action: gatekeeperResult.action,
        reason: gatekeeperResult.reason,
        message: gatekeeperResult.message,
      };
    }

    input.logger.debug(`${input.logPrefix}.path`, {
      userId: input.userId,
      ...(input.source ? { source: input.source } : {}),
      path: "legacy_fallback",
      reason: gatekeeperResult.reason,
      action: gatekeeperResult.action,
    });
    return {
      usedTypedPath: false,
      accepted: false,
      action: gatekeeperResult.action,
      reason: gatekeeperResult.reason,
      message: gatekeeperResult.message,
    };
  } catch (error) {
    input.logger.warn(`${input.logPrefix}.failed_legacy_fallback`, {
      userId: input.userId,
      ...(input.source ? { source: input.source } : {}),
      error: error instanceof Error ? error.message : "Unknown error",
    });
    return {
      usedTypedPath: false,
      accepted: false,
      action: null,
      reason: "FAILED_LEGACY_FALLBACK",
      message: DEFAULT_FALLBACK_MESSAGE,
    };
  }
}
