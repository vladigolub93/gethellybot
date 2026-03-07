import { HellyAction } from "../../core/state/actions";
import { HellyState } from "../../core/state/states";

export type ActionRouterInput = {
  userMessage: string;
  currentState: HellyState;
};

export type ActionRouterResult = {
  action: HellyAction | null;
  confidence: number;
  message: string;
};
