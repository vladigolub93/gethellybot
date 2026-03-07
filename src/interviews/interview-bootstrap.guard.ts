import { UserRole, UserSessionState, UserState } from "../shared/types/state.types";

export interface BootstrapGuardResult {
  role: UserRole;
  nextState: UserState;
}

export function isInterviewingState(state: UserState): boolean {
  return state === "interviewing_candidate" || state === "interviewing_manager";
}

export function isDocumentUploadAllowedState(state: UserState): boolean {
  return state === "waiting_resume" || state === "waiting_job";
}

export function evaluateInterviewBootstrap(session: UserSessionState): BootstrapGuardResult {
  if (isInterviewingState(session.state)) {
    throw new Error("Interview is already in progress. Please answer the current question.");
  }

  if (session.state === "waiting_resume") {
    if (session.role !== "candidate") {
      throw new Error("Candidate role is required before resume processing. Use /start.");
    }
    return { role: "candidate", nextState: "interviewing_candidate" };
  }

  if (session.state === "waiting_job") {
    if (session.role !== "manager") {
      throw new Error("Hiring role is required before job description processing. Use /start.");
    }
    return { role: "manager", nextState: "interviewing_manager" };
  }

  throw new Error("Document upload is only allowed when waiting for resume or job description.");
}
