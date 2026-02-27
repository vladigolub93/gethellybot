import {
  CandidateConfidenceUpdate,
  InterviewAnswer,
  ManagerProfileUpdate,
  UserRole,
  UserSessionState,
  UserState,
} from "../shared/types/state.types";
import { assertTransition } from "./state-machine";
import {
  CandidateProfile,
  DocumentType,
  InterviewPlan,
  InterviewResultArtifact,
  JobProfile,
} from "../shared/types/domain.types";
import { CandidateInterviewPlanV2 } from "../shared/types/interview-plan.types";
import { CandidateTechnicalSummaryV1 } from "../shared/types/candidate-summary.types";
import { JobProfileV2, JobTechnicalSummaryV2 } from "../shared/types/job-profile.types";

export class StateService {
  private readonly sessions = new Map<number, UserSessionState>();
  private readonly maxProcessedUpdates = 200;

  getOrCreate(userId: number, chatId: number, username?: string): UserSessionState {
    const existing = this.sessions.get(userId);
    if (existing) {
      if (username) {
        existing.username = username;
      }
      return existing;
    }

    const created: UserSessionState = {
      userId,
      chatId,
      username,
      state: "role_selection",
    };
    this.sessions.set(userId, created);
    return created;
  }

  getSession(userId: number): UserSessionState | null {
    return this.sessions.get(userId) ?? null;
  }

  setSession(session: UserSessionState): UserSessionState {
    this.sessions.set(session.userId, session);
    return session;
  }

  reset(userId: number, chatId: number, username?: string): UserSessionState {
    const session: UserSessionState = {
      userId,
      chatId,
      username,
      state: "role_selection",
    };
    this.sessions.set(userId, session);
    return session;
  }

  transition(userId: number, to: UserState): UserSessionState {
    const session = this.sessions.get(userId);
    if (!session) {
      throw new Error(`Session not found for user: ${userId}`);
    }
    assertTransition(session.state, to);
    session.state = to;
    return session;
  }

  setRole(userId: number, role: UserRole): UserSessionState {
    const session = this.sessions.get(userId);
    if (!session) {
      throw new Error(`Session not found for user: ${userId}`);
    }
    session.role = role;
    return session;
  }

  setOnboardingCompleted(userId: number, completed: boolean): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.onboardingCompleted = completed;
    return session;
  }

  setFirstMatchExplained(userId: number, explained: boolean): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.firstMatchExplained = explained;
    return session;
  }

  setLastEmpathyLine(userId: number, line?: string): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.lastEmpathyLine = line;
    return session;
  }

  setReactionState(input: {
    userId: number;
    lastReactionAt?: string;
    lastReactionEmoji?: string;
    reactionMessagesSinceLast?: number;
  }): UserSessionState {
    const session = this.getRequiredSession(input.userId);
    if (typeof input.lastReactionAt === "string") {
      session.lastReactionAt = input.lastReactionAt;
    }
    if (typeof input.lastReactionEmoji === "string") {
      session.lastReactionEmoji = input.lastReactionEmoji;
    }
    if (typeof input.reactionMessagesSinceLast === "number") {
      session.reactionMessagesSinceLast = Math.max(0, Math.floor(input.reactionMessagesSinceLast));
    }
    return session;
  }

  isDuplicateUpdate(userId: number, updateId: number): boolean {
    const session = this.getRequiredSession(userId);
    const processed = session.processedUpdateIds ?? [];
    return processed.includes(updateId);
  }

  markUpdateProcessed(userId: number, updateId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    const processed = session.processedUpdateIds ?? [];
    if (!processed.includes(updateId)) {
      processed.push(updateId);
      if (processed.length > this.maxProcessedUpdates) {
        session.processedUpdateIds = processed.slice(processed.length - this.maxProcessedUpdates);
      } else {
        session.processedUpdateIds = processed;
      }
    }
    return session;
  }

  setCandidateResumeText(userId: number, text: string): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidateResumeText = text;
    return session;
  }

  setJobDescriptionText(userId: number, text: string): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.jobDescriptionText = text;
    return session;
  }

  setInterviewPlan(userId: number, plan: InterviewPlan): UserSessionState {
    const session = this.getRequiredSession(userId);
    if (session.interviewPlan) {
      throw new Error("Interview plan is immutable and cannot be regenerated in this session.");
    }
    session.interviewPlan = plan;
    session.pendingFollowUp = undefined;
    session.candidateConfidenceUpdates = [];
    session.candidateContradictionFlags = [];
    session.candidateTechnicalSummary = undefined;
    session.managerJobProfileV2 = undefined;
    session.managerProfileUpdates = [];
    session.managerContradictionFlags = [];
    session.managerTechnicalSummary = undefined;
    session.answers = [];
    return session;
  }

  setCandidateInterviewPlanV2(userId: number, plan: CandidateInterviewPlanV2): UserSessionState {
    const session = this.getRequiredSession(userId);
    if (session.candidateInterviewPlanV2) {
      throw new Error("Candidate interview plan v2 is immutable and cannot be regenerated in this session.");
    }
    session.candidateInterviewPlanV2 = plan;
    return session;
  }

  markInterviewStarted(userId: number, documentType: DocumentType, startedAt: string): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.documentType = documentType;
    session.interviewStartedAt = startedAt;
    return session;
  }

  markInterviewCompleted(
    userId: number,
    completedAt: string,
    finalArtifact?: InterviewResultArtifact,
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.interviewCompletedAt = completedAt;
    if (finalArtifact) {
      session.finalArtifact = finalArtifact;
    }
    return session;
  }

  setCandidateProfile(userId: number, profile: CandidateProfile): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidateProfile = profile;
    return session;
  }

  setJobProfile(userId: number, profile: JobProfile): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.jobProfile = profile;
    return session;
  }

  setCurrentQuestionIndex(userId: number, index: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.currentQuestionIndex = index;
    return session;
  }

  clearCurrentQuestionIndex(userId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.currentQuestionIndex = undefined;
    return session;
  }

  setPendingFollowUp(
    userId: number,
    followUp: UserSessionState["pendingFollowUp"],
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.pendingFollowUp = followUp;
    return session;
  }

  clearPendingFollowUp(userId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.pendingFollowUp = undefined;
    return session;
  }

  addCandidateConfidenceUpdates(
    userId: number,
    updates: ReadonlyArray<CandidateConfidenceUpdate>,
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    const existing = session.candidateConfidenceUpdates ?? [];
    if (updates.length === 0) {
      session.candidateConfidenceUpdates = existing;
      return session;
    }
    session.candidateConfidenceUpdates = [...existing, ...updates];
    return session;
  }

  addCandidateContradictionFlags(userId: number, flags: ReadonlyArray<string>): UserSessionState {
    const session = this.getRequiredSession(userId);
    const existing = session.candidateContradictionFlags ?? [];
    const normalized = flags
      .map((flag) => flag.trim())
      .filter((flag) => Boolean(flag));
    if (normalized.length === 0) {
      session.candidateContradictionFlags = existing;
      return session;
    }
    const set = new Set([...existing, ...normalized]);
    session.candidateContradictionFlags = Array.from(set);
    return session;
  }

  setCandidateTechnicalSummary(
    userId: number,
    summary: CandidateTechnicalSummaryV1,
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidateTechnicalSummary = summary;
    return session;
  }

  setManagerJobProfileV2(userId: number, profile: JobProfileV2): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.managerJobProfileV2 = profile;
    return session;
  }

  addManagerProfileUpdates(
    userId: number,
    updates: ReadonlyArray<ManagerProfileUpdate>,
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    const existing = session.managerProfileUpdates ?? [];
    if (updates.length === 0) {
      session.managerProfileUpdates = existing;
      return session;
    }
    session.managerProfileUpdates = [...existing, ...updates];
    return session;
  }

  addManagerContradictionFlags(userId: number, flags: ReadonlyArray<string>): UserSessionState {
    const session = this.getRequiredSession(userId);
    const existing = session.managerContradictionFlags ?? [];
    const normalized = flags
      .map((flag) => flag.trim())
      .filter((flag) => Boolean(flag));
    if (normalized.length === 0) {
      session.managerContradictionFlags = existing;
      return session;
    }
    const set = new Set([...existing, ...normalized]);
    session.managerContradictionFlags = Array.from(set);
    return session;
  }

  setManagerTechnicalSummary(
    userId: number,
    summary: JobTechnicalSummaryV2,
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.managerTechnicalSummary = summary;
    return session;
  }

  getAnswers(userId: number): InterviewAnswer[] {
    const session = this.getRequiredSession(userId);
    return session.answers ?? [];
  }

  upsertAnswer(userId: number, answer: InterviewAnswer): UserSessionState {
    const session = this.getRequiredSession(userId);
    const answers = session.answers ?? [];
    answers.push(answer);
    session.answers = answers;
    return session;
  }

  private getRequiredSession(userId: number): UserSessionState {
    const session = this.sessions.get(userId);
    if (!session) {
      throw new Error(`Session not found for user: ${userId}`);
    }
    return session;
  }
}
