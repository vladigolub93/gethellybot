import { HELLY_ACTIONS, HellyAction } from "../../core/state/actions";
import { ActionRouterResult } from "./action-router.types";

const ACTION_ENUM = Object.values(HELLY_ACTIONS);
const ACTION_SET = new Set<string>(ACTION_ENUM);

export const ACTION_ROUTER_RESULT_JSON_SCHEMA = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  title: "ActionRouterResult",
  type: "object",
  additionalProperties: false,
  required: ["action", "confidence", "message"],
  properties: {
    action: {
      anyOf: [
        { type: "null" },
        { type: "string", enum: ACTION_ENUM },
      ],
    },
    confidence: {
      type: "number",
      minimum: 0,
      maximum: 1,
    },
    message: {
      type: "string",
      minLength: 1,
    },
  },
} as const;

export function isActionRouterResult(value: unknown): value is ActionRouterResult {
  if (!isPlainObject(value)) {
    return false;
  }

  const keys = Object.keys(value);
  if (keys.length !== 3) {
    return false;
  }
  if (!keys.includes("action") || !keys.includes("confidence") || !keys.includes("message")) {
    return false;
  }

  const actionValue = value.action;
  if (!(actionValue === null || (typeof actionValue === "string" && ACTION_SET.has(actionValue)))) {
    return false;
  }

  const confidenceValue = value.confidence;
  if (typeof confidenceValue !== "number" || !Number.isFinite(confidenceValue)) {
    return false;
  }
  if (confidenceValue < 0 || confidenceValue > 1) {
    return false;
  }

  const messageValue = value.message;
  if (typeof messageValue !== "string" || messageValue.trim().length === 0) {
    return false;
  }

  return true;
}

export function normalizeActionRouterResult(value: ActionRouterResult): ActionRouterResult {
  const action = value.action === null ? null : normalizeAction(value.action);
  const confidence = clamp01(value.confidence);
  const message = value.message.trim() || "Please continue when ready.";

  return {
    action,
    confidence,
    message,
  };
}

function normalizeAction(action: HellyAction): HellyAction | null {
  return ACTION_SET.has(action) ? action : null;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  if (value < 0) {
    return 0;
  }
  if (value > 1) {
    return 1;
  }
  return value;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
