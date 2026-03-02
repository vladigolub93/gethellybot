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

/** Dialogue phase for state redesign v2 (dynamic prescreen, max 10). */
export type DialoguePhase =
  | "onboarding_contact"
  | "onboarding_role"
  | "collecting_document"
  | "prescreen_active"
  | "prescreen_paused"
  | "profile_ready"
  | "matching_idle";

/** Current question in prescreen v2. */
export interface PrescreenCurrentQuestionV2 {
  id: string;
  text: string;
  mapsTo: string[];
  isMandatory: boolean;
}

/** Mandatory fields for candidate (filled during prescreen, max 10 Qs). */
export interface PrescreenMandatoryCandidateV2 {
  location?: boolean;
  workFormat?: boolean;
  salary?: boolean;
}

/** Mandatory fields for manager. */
export interface PrescreenMandatoryManagerV2 {
  workFormat?: boolean;
  allowedCountries?: boolean;
  budget?: boolean;
}

/** Prescreen state v2: dynamic loop, max 10 questions, follow-ups tracked. */
export interface PrescreenStateV2 {
  totalQuestionsAsked: number;
  maxQuestions: number;
  currentQuestion: PrescreenCurrentQuestionV2 | null;
  followUpUsedForQuestionIds: string[];
  askedQuestionIds: string[];
  lastMicroConfirmationAt: string | null;
  mandatory: PrescreenMandatoryCandidateV2 | PrescreenMandatoryManagerV2;
  lastIntent: string | null;
}

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
export type CandidatePrescreenVersion = "v1" | "v2";
export type JobPrescreenVersion = "v1" | "v2";
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
  lastIncompleteInterviewReminderAt?: string;
  lastBotMessage?: string;
  lastBotMessageHash?: string;
  lastBotMessageAt?: string;
  lastEmpathyLine?: string;
  reactionMessagesSinceLast?: number;
  lastReactionAt?: string;
  lastReactionEmoji?: string;
  candidateResumeText?: string;
  jobDescriptionText?: string;
  documentType?: DocumentType;
  interviewPlan?: InterviewPlan;
  candidateInterviewPlanV2?: CandidateInterviewPlanV2;
  prescreenVersion?: CandidatePrescreenVersion;
  prescreenQuestionIndex?: number;
  prescreenPlan?: CandidatePrescreenQuestionState[];
  prescreenAnswers?: CandidatePrescreenAnswerState[];
  prescreenFacts?: CandidatePrescreenFactState[];
  prescreenFollowUpsByQuestion?: Record<string, number>;
  prescreenTotalFollowUps?: number;
  prescreenAiRetriesByQuestion?: Record<string, number>;
  jobPrescreenVersion?: JobPrescreenVersion;
  jobPrescreenQuestionIndex?: number;
  jobPrescreenPlan?: JobPrescreenQuestionState[];
  jobPrescreenAnswers?: JobPrescreenAnswerState[];
  jobPrescreenFacts?: JobPrescreenFactState[];
  jobPrescreenFollowUpsByQuestion?: Record<string, number>;
  jobPrescreenTotalFollowUps?: number;
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
  /** Conversation state redesign v2: phase-driven flow. */
  dialoguePhase?: DialoguePhase;
  /** Prescreen v2: dynamic questions, max 10, mandatory tracking. */
  prescreenV2?: PrescreenStateV2;
  /** Stage 10: matching by request — last shown cards, for text "apply"/"reject". */
  matching?: MatchingStateV1;
  /** Stage 10: manager's active job id for matching (telegram user id or future job id). */
  lastActiveJobId?: string | null;
}

/** Matching UI state: last shown match IDs and the one actionable (for text intents). */
export interface MatchingStateV1 {
  lastShownMatchIds: string[];
  lastActionableMatchId: string | null;
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
  readonly aiAssistedLikelihood?: "low" | "medium" | "high";
  readonly aiAssistedConfidence?: number;
  readonly missingElements?: string[];
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

export interface CandidatePrescreenQuestionState {
  readonly id: string;
  readonly tech_or_topic: string;
  readonly question: string;
  readonly intent: "verify_claim";
  readonly expected_answer_shape: "short_story";
  readonly followup_policy: "at_most_one_soft_followup";
}

export interface CandidatePrescreenFactState {
  readonly key: string;
  readonly value: string | number | boolean | null;
  readonly confidence: number;
}

export interface CandidatePrescreenAnswerState {
  readonly question_id: string;
  readonly question_text: string;
  readonly answer_text: string;
  readonly interpreted_facts: CandidatePrescreenFactState[];
  readonly notes: string;
  readonly ai_assisted_likelihood: "low" | "medium" | "high";
  readonly ai_assisted_confidence: number;
  readonly quality_warning?: boolean;
  readonly created_at: string;
}

export interface JobPrescreenQuestionState {
  readonly id: string;
  readonly topic: string;
  readonly question: string;
  readonly intent: "clarify";
  readonly followup_policy: "at_most_one_soft_followup";
}

export interface JobPrescreenFactState {
  readonly key: string;
  readonly value: string | number | boolean | null;
  readonly confidence: number;
}

export interface JobPrescreenAnswerState {
  readonly question_id: string;
  readonly question_text: string;
  readonly answer_text: string;
  readonly interpreted_facts: JobPrescreenFactState[];
  readonly notes: string;
  readonly created_at: string;
}

export interface ManagerProfileUpdate {
  field: string;
  previous_value: string;
  new_value: string;
  reason: string;
}
