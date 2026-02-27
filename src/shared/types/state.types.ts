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
  | "interviewing_candidate"
  | "candidate_profile_ready"
  | "onboarding_manager"
  | "waiting_job"
  | "interviewing_manager"
  | "job_profile_ready"
  | "job_published"
  | "waiting_candidate_decision"
  | "waiting_manager_decision"
  | "contact_shared";

export interface UserSessionState {
  userId: number;
  chatId: number;
  state: UserState;
  role?: UserRole;
  preferredLanguage?: PreferredLanguage;
  languageSampleCount?: number;
  username?: string;
  onboardingCompleted?: boolean;
  firstMatchExplained?: boolean;
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
  candidateTechnicalSummary?: CandidateTechnicalSummaryV1;
  managerJobProfileV2?: JobProfileV2;
  managerProfileUpdates?: ManagerProfileUpdate[];
  managerContradictionFlags?: string[];
  managerTechnicalSummary?: JobTechnicalSummaryV2;
  currentQuestionIndex?: number;
  pendingFollowUp?: InterviewFollowUpState;
  answers?: InterviewAnswer[];
  interviewStartedAt?: string;
  interviewCompletedAt?: string;
  finalArtifact?: InterviewResultArtifact;
  candidateProfile?: CandidateProfile;
  jobProfile?: JobProfile;
  processedUpdateIds?: number[];
}

export interface InterviewAnswer {
  readonly questionIndex: number;
  readonly questionId: string;
  readonly questionText: string;
  readonly answerText: string;
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
