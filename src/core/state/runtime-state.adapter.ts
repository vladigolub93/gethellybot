import {
  CURRENT_RUNTIME_STATES,
  CURRENT_RUNTIME_TO_HELLY_STATE,
  CurrentRuntimeState,
  HellyState,
} from "./states";

const CURRENT_RUNTIME_STATE_SET = new Set<string>(
  Object.values(CURRENT_RUNTIME_STATES),
);

export function isCurrentRuntimeState(value: string): value is CurrentRuntimeState {
  return CURRENT_RUNTIME_STATE_SET.has(value);
}

export function mapRuntimeStateToHellyState(runtimeState: string): HellyState | null {
  if (!isCurrentRuntimeState(runtimeState)) {
    return null;
  }
  return CURRENT_RUNTIME_TO_HELLY_STATE[runtimeState] ?? null;
}
