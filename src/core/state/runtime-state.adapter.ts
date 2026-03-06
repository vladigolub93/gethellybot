import {
  CURRENT_RUNTIME_STATES,
  CURRENT_RUNTIME_TO_HELLY_STATE,
  CurrentRuntimeState,
  HELLY_STATES,
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

/**
 * Contact step compatibility helper:
 * runtime "role_selection" + awaitingContactChoice should map to WAIT_CONTACT.
 */
export function mapRuntimeStateToContactStepHellyState(
  runtimeState: string,
  awaitingContactChoice: boolean,
): HellyState | null {
  const canonical = mapRuntimeStateToHellyState(runtimeState);
  if (!canonical) {
    return null;
  }
  if (canonical === HELLY_STATES.WAIT_ROLE && awaitingContactChoice) {
    return HELLY_STATES.WAIT_CONTACT;
  }
  return canonical;
}

/**
 * Candidate summary-review compatibility helper:
 * current runtime has no dedicated summary-review state.
 * We treat the very first candidate interview turn as the closest equivalent.
 */
export function mapRuntimeStateToCandidateSummaryReviewStepHellyState(
  runtimeState: string,
  input: {
    isCandidateRole: boolean;
    currentQuestionIndex: number | null;
    hasPendingFollowUp: boolean;
    hasFinalAnswers: boolean;
    currentQuestionText: string | null;
  },
): HellyState | null {
  const canonical = mapRuntimeStateToHellyState(runtimeState);
  if (!canonical) {
    return null;
  }
  const looksLikeSummaryReviewQuestion = (input.currentQuestionText ?? "").trim().toLowerCase();
  const isSummaryReviewQuestion =
    looksLikeSummaryReviewQuestion.includes("summary") ||
    looksLikeSummaryReviewQuestion.includes("confirm");
  if (
    canonical === HELLY_STATES.C_INTERVIEW_IN_PROGRESS &&
    input.isCandidateRole &&
    input.currentQuestionIndex === 0 &&
    !input.hasPendingFollowUp &&
    !input.hasFinalAnswers &&
    isSummaryReviewQuestion
  ) {
    return HELLY_STATES.C_SUMMARY_REVIEW;
  }
  return canonical;
}
