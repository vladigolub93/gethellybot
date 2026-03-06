import { UserSessionState } from "../shared/types/state.types";

export const ONBOARDING_STAGES = {
  ROLE_SELECTION: "ROLE_SELECTION",
  CONTACT_IDENTITY: "CONTACT_IDENTITY",
  CANDIDATE_CV_INTAKE: "CANDIDATE_CV_INTAKE",
  CANDIDATE_MANDATORY: "CANDIDATE_MANDATORY",
  CANDIDATE_REVIEW: "CANDIDATE_REVIEW",
  MANAGER_JD_INTAKE: "MANAGER_JD_INTAKE",
  MANAGER_MANDATORY: "MANAGER_MANDATORY",
  MANAGER_REVIEW: "MANAGER_REVIEW",
  CANDIDATE_DECISION: "CANDIDATE_DECISION",
  MANAGER_DECISION: "MANAGER_DECISION",
  INTERVIEW_INVITATION: "INTERVIEW_INVITATION",
  INTERVIEW_ANSWER: "INTERVIEW_ANSWER",
  OUT_OF_SCOPE: "OUT_OF_SCOPE",
} as const;

export type OnboardingStage = (typeof ONBOARDING_STAGES)[keyof typeof ONBOARDING_STAGES];

export type OnboardingStageResolverInput = {
  session: UserSessionState;
  context?: {
    awaitingContactChoice?: boolean;
    currentQuestionText?: string | null;
    currentQuestionIndex?: number | null;
    hasFinalAnswers?: boolean;
    hasMatchForInterviewInvite?: boolean;
  };
};

export function resolveOnboardingStage(input: OnboardingStageResolverInput): OnboardingStage {
  const session = input.session;

  if (session.state === "role_selection") {
    const awaitingContactChoice = input.context?.awaitingContactChoice ?? session.awaitingContactChoice === true;
    return awaitingContactChoice
      ? ONBOARDING_STAGES.CONTACT_IDENTITY
      : ONBOARDING_STAGES.ROLE_SELECTION;
  }

  if (session.state === "waiting_resume") {
    return ONBOARDING_STAGES.CANDIDATE_CV_INTAKE;
  }

  if (session.state === "candidate_mandatory_fields") {
    return ONBOARDING_STAGES.CANDIDATE_MANDATORY;
  }

  if (session.state === "waiting_job") {
    return ONBOARDING_STAGES.MANAGER_JD_INTAKE;
  }

  if (session.state === "manager_mandatory_fields") {
    return ONBOARDING_STAGES.MANAGER_MANDATORY;
  }

  if (session.state === "waiting_candidate_decision") {
    const hasMatchForInterviewInvite =
      input.context?.hasMatchForInterviewInvite ??
      hasInterviewInvitationMatch(session);
    if (hasMatchForInterviewInvite) {
      return ONBOARDING_STAGES.INTERVIEW_INVITATION;
    }
    return ONBOARDING_STAGES.CANDIDATE_DECISION;
  }

  if (session.state === "waiting_manager_decision") {
    return ONBOARDING_STAGES.MANAGER_DECISION;
  }

  if (session.state === "interviewing_candidate") {
    const currentQuestionText = input.context?.currentQuestionText ?? resolveCurrentQuestionText(session);
    const currentQuestionIndex = input.context?.currentQuestionIndex ?? resolveCurrentQuestionIndex(session);
    const hasFinalAnswers =
      input.context?.hasFinalAnswers ??
      (session.answers ?? []).some((answer) => answer.status !== "draft");
    if (
      session.role === "candidate" &&
      currentQuestionIndex === 0 &&
      !session.pendingFollowUp &&
      !hasFinalAnswers &&
      isSummaryReviewQuestion(currentQuestionText)
    ) {
      return ONBOARDING_STAGES.CANDIDATE_REVIEW;
    }
  }

  if (session.state === "interviewing_manager") {
    const currentQuestionText = input.context?.currentQuestionText ?? resolveCurrentQuestionText(session);
    const currentQuestionIndex = input.context?.currentQuestionIndex ?? resolveCurrentQuestionIndex(session);
    const hasFinalAnswers =
      input.context?.hasFinalAnswers ??
      (session.answers ?? []).some((answer) => answer.status !== "draft");
    if (
      session.role === "manager" &&
      currentQuestionIndex === 0 &&
      !session.pendingFollowUp &&
      !hasFinalAnswers &&
      isSummaryReviewQuestion(currentQuestionText)
    ) {
      return ONBOARDING_STAGES.MANAGER_REVIEW;
    }
  }

  if (session.state === "interviewing_candidate" || session.state === "interviewing_manager") {
    return ONBOARDING_STAGES.INTERVIEW_ANSWER;
  }

  return ONBOARDING_STAGES.OUT_OF_SCOPE;
}

function hasInterviewInvitationMatch(session: UserSessionState): boolean {
  const actionableMatchId = session.matching?.lastActionableMatchId?.trim();
  if (actionableMatchId) {
    return true;
  }
  return (session.matching?.lastShownMatchIds?.length ?? 0) > 0;
}

function resolveCurrentQuestionIndex(session: UserSessionState): number | null {
  if (session.pendingFollowUp && typeof session.pendingFollowUp.questionIndex === "number") {
    return session.pendingFollowUp.questionIndex;
  }
  if (typeof session.currentQuestionIndex === "number") {
    return session.currentQuestionIndex;
  }
  return null;
}

function resolveCurrentQuestionText(session: UserSessionState): string | null {
  if (session.pendingFollowUp?.questionText?.trim()) {
    return session.pendingFollowUp.questionText.trim();
  }
  if (!session.interviewPlan) {
    return null;
  }
  const index = resolveCurrentQuestionIndex(session);
  if (typeof index !== "number" || index < 0 || index >= session.interviewPlan.questions.length) {
    return null;
  }
  return session.interviewPlan.questions[index]?.question?.trim() || null;
}

function isSummaryReviewQuestion(currentQuestionText: string | null): boolean {
  const normalized = (currentQuestionText ?? "").trim().toLowerCase();
  return normalized.includes("summary") || normalized.includes("confirm");
}
