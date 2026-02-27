export type GuardrailsResponseStyle = "normal" | "redirect" | "refuse";

export type GuardrailsAction =
  | "none"
  | "request_more_hiring_context"
  | "privacy_block"
  | "data_deletion_request";

export interface HiringScopeGuardrailsDecisionV1 {
  allowed: boolean;
  response_style: GuardrailsResponseStyle;
  safe_reply: string;
  action: GuardrailsAction;
}
