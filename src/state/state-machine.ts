import { UserState } from "../shared/types/state.types";
import { isAllowedTransition } from "./transition-rules";

export function assertTransition(from: UserState, to: UserState): void {
  if (!isAllowedTransition(from, to)) {
    throw new Error(`Invalid transition from ${from} to ${to}`);
  }
}
