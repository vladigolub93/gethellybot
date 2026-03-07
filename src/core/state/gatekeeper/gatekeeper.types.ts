import { HellyAction } from "../actions";
import { HellyState } from "../states";

export type GatekeeperInput = {
  currentState: HellyState;
  action: HellyAction | null;
  confidence: number;
  message: string;
};

export type GatekeeperReason =
  | "ACCEPTED"
  | "NO_ACTION"
  | "ACTION_NOT_ALLOWED"
  | "LOW_CONFIDENCE";

export type GatekeeperResult = {
  accepted: boolean;
  reason: GatekeeperReason;
  action: HellyAction | null;
  message: string;
};
