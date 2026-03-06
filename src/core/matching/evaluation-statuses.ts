/**
 * Canonical evaluation outcomes after interview completion.
 *
 * This is a contract-only layer. Runtime wiring is intentionally not added yet.
 */
export const EVALUATION_STATUSES = {
  STRONG: "STRONG",
  POSSIBLE: "POSSIBLE",
  WEAK: "WEAK",
} as const;

export type EvaluationStatus = (typeof EVALUATION_STATUSES)[keyof typeof EVALUATION_STATUSES];

