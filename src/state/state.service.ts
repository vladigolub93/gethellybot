import {
  CandidateMandatoryStep,
  CandidateSalaryCurrency,
  CandidateSalaryPeriod,
  CandidateWorkMode,
  JobBudgetCurrency,
  JobBudgetPeriod,
  JobWorkFormat,
  ManagerMandatoryStep,
  CandidateConfidenceUpdate,
  InterviewAnswer,
  ManagerProfileUpdate,
  PreferredLanguage,
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
      awaitingContactChoice: false,
      preferredLanguage: "unknown",
      candidateProfileComplete: false,
      jobProfileComplete: false,
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
    const existing = this.sessions.get(userId);
    const session: UserSessionState = {
      userId,
      chatId,
      username,
      state: "role_selection",
      awaitingContactChoice: true,
      preferredLanguage: existing?.preferredLanguage ?? "unknown",
      firstMatchExplained: existing?.firstMatchExplained,
      onboardingCompleted: existing?.onboardingCompleted,
      candidateCountry: existing?.candidateCountry,
      candidateCity: existing?.candidateCity,
      candidateWorkMode: existing?.candidateWorkMode,
      candidateSalaryAmount: existing?.candidateSalaryAmount,
      candidateSalaryCurrency: existing?.candidateSalaryCurrency,
      candidateSalaryPeriod: existing?.candidateSalaryPeriod,
      candidateProfileComplete: existing?.candidateProfileComplete ?? false,
      jobWorkFormat: existing?.jobWorkFormat,
      jobRemoteCountries: existing?.jobRemoteCountries,
      jobRemoteWorldwide: existing?.jobRemoteWorldwide,
      jobBudgetMin: existing?.jobBudgetMin,
      jobBudgetMax: existing?.jobBudgetMax,
      jobBudgetCurrency: existing?.jobBudgetCurrency,
      jobBudgetPeriod: existing?.jobBudgetPeriod,
      jobProfileComplete: existing?.jobProfileComplete ?? false,
      waitingShortTextState: existing?.waitingShortTextState,
      waitingShortTextCount: existing?.waitingShortTextCount,
      answersSinceConfirm: 0,
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

  setPreferredLanguage(userId: number, preferredLanguage: PreferredLanguage): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.preferredLanguage = preferredLanguage;
    return session;
  }

  recordPreferredLanguageSample(
    userId: number,
    detectedLanguage: "en" | "ru" | "uk" | "unknown" | "other",
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    const currentCount = session.languageSampleCount ?? 0;
    if (currentCount >= 3) {
      return session;
    }

    session.languageSampleCount = currentCount + 1;
    if (detectedLanguage === "other") {
      if (!session.preferredLanguage) {
        session.preferredLanguage = "unknown";
      }
      return session;
    }

    if (detectedLanguage === "ru" || detectedLanguage === "uk") {
      session.preferredLanguage = detectedLanguage;
      return session;
    }

    if (!session.preferredLanguage || session.preferredLanguage === "unknown") {
      session.preferredLanguage = "en";
    }
    return session;
  }

  setOnboardingCompleted(userId: number, completed: boolean): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.onboardingCompleted = completed;
    return session;
  }

  setAwaitingContactChoice(userId: number, awaiting: boolean): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.awaitingContactChoice = awaiting;
    return session;
  }

  setFirstMatchExplained(userId: number, explained: boolean): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.firstMatchExplained = explained;
    return session;
  }

  setCandidateMandatoryStep(
    userId: number,
    step?: CandidateMandatoryStep,
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidateMandatoryStep = step;
    return session;
  }

  setCandidateLocation(
    userId: number,
    location: {
      country: string;
      city: string;
    },
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidateCountry = location.country;
    session.candidateCity = location.city;
    return session;
  }

  setCandidateWorkMode(
    userId: number,
    workMode: CandidateWorkMode,
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidateWorkMode = workMode;
    return session;
  }

  setCandidateSalary(
    userId: number,
    salary: {
      amount: number;
      currency: CandidateSalaryCurrency;
      period: CandidateSalaryPeriod;
    },
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidateSalaryAmount = salary.amount;
    session.candidateSalaryCurrency = salary.currency;
    session.candidateSalaryPeriod = salary.period;
    return session;
  }

  setCandidateProfileComplete(userId: number, complete: boolean): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidateProfileComplete = complete;
    return session;
  }

  setCandidatePendingSalary(
    userId: number,
    pending?: {
      amount: number;
      currency: CandidateSalaryCurrency;
      period: CandidateSalaryPeriod;
      needsCurrencyConfirmation: boolean;
    },
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidatePendingSalary = pending;
    return session;
  }

  isCandidateProfileComplete(userId: number): boolean {
    const session = this.getRequiredSession(userId);
    return Boolean(
      session.candidateCountry?.trim() &&
      session.candidateCity?.trim() &&
      session.candidateWorkMode &&
      typeof session.candidateSalaryAmount === "number" &&
      Number.isFinite(session.candidateSalaryAmount) &&
      session.candidateSalaryAmount > 0 &&
      session.candidateSalaryCurrency &&
      session.candidateSalaryPeriod,
    );
  }

  setManagerMandatoryStep(
    userId: number,
    step?: ManagerMandatoryStep,
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.managerMandatoryStep = step;
    return session;
  }

  setJobWorkFormat(
    userId: number,
    workFormat: JobWorkFormat,
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.jobWorkFormat = workFormat;
    return session;
  }

  setJobRemotePolicy(
    userId: number,
    input: {
      worldwide: boolean;
      countries: string[];
    },
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.jobRemoteWorldwide = input.worldwide;
    session.jobRemoteCountries = input.countries;
    return session;
  }

  setJobBudget(
    userId: number,
    input: {
      min: number;
      max: number;
      currency: JobBudgetCurrency;
      period: JobBudgetPeriod;
    },
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.jobBudgetMin = input.min;
    session.jobBudgetMax = input.max;
    session.jobBudgetCurrency = input.currency;
    session.jobBudgetPeriod = input.period;
    return session;
  }

  setJobProfileComplete(userId: number, complete: boolean): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.jobProfileComplete = complete;
    return session;
  }

  setManagerPendingBudget(
    userId: number,
    pending?: {
      min: number;
      max: number;
      currency: JobBudgetCurrency;
      period: JobBudgetPeriod;
      needsCurrencyConfirmation: boolean;
    },
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.managerPendingBudget = pending;
    return session;
  }

  isJobProfileComplete(userId: number): boolean {
    const session = this.getRequiredSession(userId);
    const workFormat = session.jobWorkFormat;
    const countries = session.jobRemoteCountries ?? [];
    const remotePolicyValid =
      workFormat !== "remote" ||
      session.jobRemoteWorldwide === true ||
      countries.length > 0;
    return Boolean(
      workFormat &&
      remotePolicyValid &&
      typeof session.jobBudgetMin === "number" &&
      typeof session.jobBudgetMax === "number" &&
      session.jobBudgetMin > 0 &&
      session.jobBudgetMax >= session.jobBudgetMin &&
      session.jobBudgetCurrency &&
      session.jobBudgetPeriod,
    );
  }

  setContactInfo(input: {
    userId: number;
    phoneNumber: string;
    firstName: string;
    lastName?: string;
    sharedAt?: string;
  }): UserSessionState {
    const session = this.getRequiredSession(input.userId);
    session.contactPhoneNumber = input.phoneNumber;
    session.contactFirstName = input.firstName;
    session.contactLastName = input.lastName;
    session.contactShared = true;
    session.contactSharedAt = input.sharedAt ?? new Date().toISOString();
    return session;
  }

  clearContactInfo(userId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.contactPhoneNumber = undefined;
    session.contactFirstName = undefined;
    session.contactLastName = undefined;
    session.contactShared = false;
    session.contactSharedAt = undefined;
    return session;
  }

  setLastEmpathyLine(userId: number, line?: string): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.lastEmpathyLine = line;
    return session;
  }

  setLastBotMessage(userId: number, message?: string): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.lastBotMessage = message;
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
    session.candidateAiAssistedStreak = 0;
    session.candidateNeedsLiveValidation = false;
    session.candidateTechnicalSummary = undefined;
    session.managerJobProfileV2 = undefined;
    session.managerProfileUpdates = [];
    session.managerContradictionFlags = [];
    session.managerAiAssistedStreak = 0;
    session.managerNeedsLiveValidation = false;
    session.managerTechnicalSummary = undefined;
    session.answers = [];
    session.skippedQuestionIndexes = [];
    session.interviewMessageWithoutAnswerCount = 0;
    session.interviewMessageWithoutAnswerQuestionIndex = undefined;
    session.answersSinceConfirm = 0;
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
    session.answersSinceConfirm = 0;
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
    if (session.interviewMessageWithoutAnswerQuestionIndex !== index) {
      session.interviewMessageWithoutAnswerQuestionIndex = index;
      session.interviewMessageWithoutAnswerCount = 0;
    }
    return session;
  }

  clearCurrentQuestionIndex(userId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.currentQuestionIndex = undefined;
    session.interviewMessageWithoutAnswerCount = 0;
    session.interviewMessageWithoutAnswerQuestionIndex = undefined;
    return session;
  }

  getSkippedQuestionIndexes(userId: number): number[] {
    const session = this.getRequiredSession(userId);
    return session.skippedQuestionIndexes ?? [];
  }

  markQuestionSkipped(userId: number, questionIndex: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    const current = session.skippedQuestionIndexes ?? [];
    if (!current.includes(questionIndex)) {
      session.skippedQuestionIndexes = [...current, questionIndex];
    } else {
      session.skippedQuestionIndexes = current;
    }
    return session;
  }

  clearSkippedQuestions(userId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.skippedQuestionIndexes = [];
    return session;
  }

  clearWaitingShortTextCounter(userId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.waitingShortTextState = undefined;
    session.waitingShortTextCount = 0;
    return session;
  }

  incrementWaitingShortTextCounter(
    userId: number,
    state: "waiting_resume" | "waiting_job",
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    if (session.waitingShortTextState !== state) {
      session.waitingShortTextState = state;
      session.waitingShortTextCount = 1;
      return session;
    }
    session.waitingShortTextCount = (session.waitingShortTextCount ?? 0) + 1;
    return session;
  }

  resetInterviewNoAnswerCounter(userId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.interviewMessageWithoutAnswerCount = 0;
    session.interviewMessageWithoutAnswerQuestionIndex = session.currentQuestionIndex;
    return session;
  }

  incrementAnswersSinceConfirm(userId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.answersSinceConfirm = (session.answersSinceConfirm ?? 0) + 1;
    return session;
  }

  resetAnswersSinceConfirm(userId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.answersSinceConfirm = 0;
    return session;
  }

  incrementInterviewNoAnswerCounter(
    userId: number,
    questionIndex: number,
  ): UserSessionState {
    const session = this.getRequiredSession(userId);
    if (session.interviewMessageWithoutAnswerQuestionIndex !== questionIndex) {
      session.interviewMessageWithoutAnswerQuestionIndex = questionIndex;
      session.interviewMessageWithoutAnswerCount = 1;
      return session;
    }
    session.interviewMessageWithoutAnswerCount =
      (session.interviewMessageWithoutAnswerCount ?? 0) + 1;
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

  setCandidateAiAssistedStreak(userId: number, streak: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidateAiAssistedStreak = Math.max(0, Math.floor(streak));
    return session;
  }

  incrementCandidateAiAssistedStreak(userId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidateAiAssistedStreak = (session.candidateAiAssistedStreak ?? 0) + 1;
    return session;
  }

  setCandidateNeedsLiveValidation(userId: number, required: boolean): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.candidateNeedsLiveValidation = required;
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

  setManagerAiAssistedStreak(userId: number, streak: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.managerAiAssistedStreak = Math.max(0, Math.floor(streak));
    return session;
  }

  incrementManagerAiAssistedStreak(userId: number): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.managerAiAssistedStreak = (session.managerAiAssistedStreak ?? 0) + 1;
    return session;
  }

  setManagerNeedsLiveValidation(userId: number, required: boolean): UserSessionState {
    const session = this.getRequiredSession(userId);
    session.managerNeedsLiveValidation = required;
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
