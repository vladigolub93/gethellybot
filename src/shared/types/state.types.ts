import {
  CandidateProfile,
  DocumentType,
  InterviewPlan,
  InterviewResultArtifact,
  JobProfile,
} from "./domain.types";
import { CandidateInterviewPlanV2 } from "./interview-plan.types";
import { CandidateTechnicalSummaryV1 } from "./candidate-summary.types";
import { JobProfileV2, JobTechnicalSummaryV2 } from "./job-profile.types";

export type UserRole = "candidate" | "manager";
export type PreferredLanguage = "en" | "ru" | "uk" | "unknown";

export type UserState =
  | "role_selection"
  | "onboarding_candidate"
  | "waiting_resume"
  | "extracting_resume"
  | "interviewing_candidate"
  | "candidate_profile_ready"
  | "candidate_mandatory_fields"
  | "onboarding_manager"
  | "waiting_job"
  | "extracting_job"
  | "interviewing_manager"
  | "job_profile_ready"
  | "manager_mandatory_fields"
  | "job_published"
  | "waiting_candidate_decision"
  | "waiting_manager_decision"
  | "contact_shared";

export type CandidateWorkMode = "remote" | "hybrid" | "onsite" | "flexible";
export type CandidateSalaryPeriod = "month" | "year";
export type CandidateSalaryCurrency = "USD" | "EUR" | "ILS" | "GBP" | "other";
export type CandidateMandatoryStep = "location" | "work_mode" | "salary";
export type JobWorkFormat = "remote" | "hybrid" | "onsite";
export type JobBudgetPeriod = "month" | "year";
export type JobBudgetCurrency = "USD" | "EUR" | "ILS" | "GBP" | "other";
export type ManagerMandatoryStep = "work_format" | "countries" | "budget";

export interface UserSessionState {
  userId: number;
  chatId: number;
  state: UserState;
  role?: UserRole;
  preferredLanguage?: PreferredLanguage;
  languageSampleCount?: number;
  username?: string;
  onboardingCompleted?: boolean;
  awaitingContactChoice?: boolean;
  firstMatchExplained?: boolean;
  contactShared?: boolean;
  contactSharedAt?: string;
  contactPhoneNumber?: string;
  contactFirstName?: string;
  contactLastName?: string;
  pendingDataDeletionConfirmation?: boolean;
  pendingDataDeletionRequestedAt?: string;
  lastBotMessage?: string;
  lastEmpathyLine?: string;
  reactionMessagesSinceLast?: number;
  lastReactionAt?: string;
  lastReactionEmoji?: string;
  candidateResumeText?: string;
  jobDescriptionText?: string;
  documentType?: DocumentType;
  interviewPlan?: InterviewPlan;
  candidateInterviewPlanV2?: CandidateInterviewPlanV2;
  candidateConfidenceUpdates?: CandidateConfidenceUpdate[];
  candidateContradictionFlags?: string[];
  candidateAiAssistedStreak?: number;
  candidateNeedsLiveValidation?: boolean;
  candidateTechnicalSummary?: CandidateTechnicalSummaryV1;
  managerJobProfileV2?: JobProfileV2;
  managerProfileUpdates?: ManagerProfileUpdate[];
  managerContradictionFlags?: string[];
  managerAiAssistedStreak?: number;
  managerNeedsLiveValidation?: boolean;
  managerTechnicalSummary?: JobTechnicalSummaryV2;
  jobWorkFormat?: JobWorkFormat;
  jobRemoteCountries?: string[];
  jobRemoteWorldwide?: boolean;
  jobBudgetMin?: number;
  jobBudgetMax?: number;
  jobBudgetCurrency?: JobBudgetCurrency;
  jobBudgetPeriod?: JobBudgetPeriod;
  jobProfileComplete?: boolean;
  managerMandatoryStep?: ManagerMandatoryStep;
  managerPendingBudget?: {
    min: number;
    max: number;
    currency: JobBudgetCurrency;
    period: JobBudgetPeriod;
    needsCurrencyConfirmation: boolean;
  };
  currentQuestionIndex?: number;
  skippedQuestionIndexes?: number[];
  waitingShortTextState?: "waiting_resume" | "waiting_job";
  waitingShortTextCount?: number;
  interviewMessageWithoutAnswerQuestionIndex?: number;
  interviewMessageWithoutAnswerCount?: number;
  answersSinceConfirm?: number;
  pendingFollowUp?: InterviewFollowUpState;
  reanswerRequestsByQuestion?: Record<string, number>;
  answers?: InterviewAnswer[];
  interviewStartedAt?: string;
  interviewCompletedAt?: string;
  finalArtifact?: InterviewResultArtifact;
  candidateProfile?: CandidateProfile;
  jobProfile?: JobProfile;
  candidateCountry?: string;
  candidateCity?: string;
  candidateWorkMode?: CandidateWorkMode;
  candidateSalaryAmount?: number;
  candidateSalaryCurrency?: CandidateSalaryCurrency;
  candidateSalaryPeriod?: CandidateSalaryPeriod;
  candidateProfileComplete?: boolean;
  candidateMandatoryStep?: CandidateMandatoryStep;
  candidatePendingSalary?: {
    amount: number;
    currency: CandidateSalaryCurrency;
    period: CandidateSalaryPeriod;
    needsCurrencyConfirmation: boolean;
  };
  processedUpdateIds?: number[];
}

export interface InterviewAnswer {
  readonly questionIndex: number;
  readonly questionId: string;
  readonly questionText: string;
  readonly answerText: string;
  readonly status?: "draft" | "final";
  readonly qualityWarning?: boolean;
  readonly authenticityScore?: number;
  readonly authenticitySignals?: string[];
  readonly authenticityLabel?: "likely_human" | "uncertain" | "likely_ai_assisted";
  readonly aiAssistedScore?: number;
  readonly originalText?: string;
  readonly normalizedEnglishText?: string;
  readonly detectedLanguage?: "en" | "ru" | "uk" | "other";
  readonly inputType: "text" | "voice";
  readonly telegramVoiceFileId?: string;
  readonly voiceDurationSec?: number;
  readonly transcriptionStatus?: "success" | "failed";
  readonly isFollowUp?: boolean;
  readonly answeredAt: string;
}

export interface InterviewFollowUpState {
  readonly questionIndex: number;
  readonly questionId: string;
  readonly questionText: string;
  readonly focus: string;
}

export interface CandidateConfidenceUpdate {
  field: string;
  previous_value: string;
  new_value: string;
  reason: string;
}

export interface ManagerProfileUpdate {
  field: string;
  previous_value: string;
  new_value: string;
  reason: string;
}
