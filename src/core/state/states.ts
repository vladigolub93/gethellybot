/**
 * Helly canonical state contracts for the future extracted state engine.
 *
 * These constants intentionally include:
 * 1) target-product states (granular candidate/manager/deletion states), and
 * 2) compatibility aliases for currently observed runtime states.
 *
 * Runtime wiring is intentionally NOT added in this step.
 */
export const HELLY_STATES = {
  // Shared / session-level states
  WAIT_CONTACT: "WAIT_CONTACT",
  WAIT_ROLE: "WAIT_ROLE",
  CONTACT_SHARED: "CONTACT_SHARED",

  // Candidate flow states (target)
  C_ONBOARDING_INTRO: "C_ONBOARDING_INTRO",
  C_WAIT_CV: "C_WAIT_CV",
  C_CV_PROCESSING: "C_CV_PROCESSING",
  C_SUMMARY_REVIEW: "C_SUMMARY_REVIEW",
  C_SUMMARY_EDIT: "C_SUMMARY_EDIT",
  C_MANDATORY_QUESTIONNAIRE: "C_MANDATORY_QUESTIONNAIRE",
  C_MANDATORY_LOCATION: "C_MANDATORY_LOCATION",
  C_MANDATORY_WORK_FORMAT: "C_MANDATORY_WORK_FORMAT",
  C_MANDATORY_SALARY: "C_MANDATORY_SALARY",
  C_VIDEO_VERIFICATION_WAIT: "C_VIDEO_VERIFICATION_WAIT",
  C_READY: "C_READY",
  C_MATCH_OFFERED: "C_MATCH_OFFERED",
  C_INTERVIEW_IN_PROGRESS: "C_INTERVIEW_IN_PROGRESS",
  C_INTERVIEW_COMPLETED: "C_INTERVIEW_COMPLETED",

  // Hiring manager flow states (target)
  HM_ONBOARDING_INTRO: "HM_ONBOARDING_INTRO",
  HM_WAIT_JD: "HM_WAIT_JD",
  HM_JD_PROCESSING: "HM_JD_PROCESSING",
  HM_JD_REVIEW: "HM_JD_REVIEW",
  HM_JD_EDIT: "HM_JD_EDIT",
  HM_QUESTIONNAIRE: "HM_QUESTIONNAIRE",
  HM_MANDATORY_WORK_FORMAT: "HM_MANDATORY_WORK_FORMAT",
  HM_MANDATORY_COUNTRIES: "HM_MANDATORY_COUNTRIES",
  HM_MANDATORY_BUDGET: "HM_MANDATORY_BUDGET",
  HM_VACANCY_OPEN: "HM_VACANCY_OPEN",
  HM_MATCH_REVIEW: "HM_MATCH_REVIEW",
  HM_INTERVIEW_IN_PROGRESS: "HM_INTERVIEW_IN_PROGRESS",
  HM_INTERVIEW_COMPLETED: "HM_INTERVIEW_COMPLETED",

  // Decision handoff states
  WAIT_CANDIDATE_DECISION: "WAIT_CANDIDATE_DECISION",
  WAIT_MANAGER_DECISION: "WAIT_MANAGER_DECISION",

  // Deletion states (target)
  C_DELETE_PROFILE_CONFIRM_1: "C_DELETE_PROFILE_CONFIRM_1",
  C_DELETE_PROFILE_CONFIRM_2: "C_DELETE_PROFILE_CONFIRM_2",
  HM_DELETE_VACANCY_CONFIRM_1: "HM_DELETE_VACANCY_CONFIRM_1",
  HM_DELETE_VACANCY_CONFIRM_2: "HM_DELETE_VACANCY_CONFIRM_2",
} as const;

export type HellyState = (typeof HELLY_STATES)[keyof typeof HELLY_STATES];

/**
 * Runtime states currently present in the existing router/state service.
 * This is a documentation and typing bridge only; no runtime coupling yet.
 */
export const CURRENT_RUNTIME_STATES = {
  ROLE_SELECTION: "role_selection",
  ONBOARDING_CANDIDATE: "onboarding_candidate",
  WAITING_RESUME: "waiting_resume",
  EXTRACTING_RESUME: "extracting_resume",
  INTERVIEWING_CANDIDATE: "interviewing_candidate",
  CANDIDATE_PROFILE_READY: "candidate_profile_ready",
  CANDIDATE_MANDATORY_FIELDS: "candidate_mandatory_fields",
  ONBOARDING_MANAGER: "onboarding_manager",
  WAITING_JOB: "waiting_job",
  EXTRACTING_JOB: "extracting_job",
  INTERVIEWING_MANAGER: "interviewing_manager",
  JOB_PROFILE_READY: "job_profile_ready",
  MANAGER_MANDATORY_FIELDS: "manager_mandatory_fields",
  JOB_PUBLISHED: "job_published",
  WAITING_CANDIDATE_DECISION: "waiting_candidate_decision",
  WAITING_MANAGER_DECISION: "waiting_manager_decision",
  CONTACT_SHARED: "contact_shared",
} as const;

export type CurrentRuntimeState =
  (typeof CURRENT_RUNTIME_STATES)[keyof typeof CURRENT_RUNTIME_STATES];

/**
 * Compatibility mapping from current runtime states to canonical Helly states.
 * Note: some runtime states are coarse (e.g. mandatory_fields) and map to
 * aggregated canonical states. Fine-grained step states remain target design.
 */
export const CURRENT_RUNTIME_TO_HELLY_STATE: Record<CurrentRuntimeState, HellyState> = {
  role_selection: HELLY_STATES.WAIT_ROLE,
  onboarding_candidate: HELLY_STATES.C_ONBOARDING_INTRO,
  waiting_resume: HELLY_STATES.C_WAIT_CV,
  extracting_resume: HELLY_STATES.C_CV_PROCESSING,
  interviewing_candidate: HELLY_STATES.C_INTERVIEW_IN_PROGRESS,
  candidate_profile_ready: HELLY_STATES.C_READY,
  candidate_mandatory_fields: HELLY_STATES.C_MANDATORY_QUESTIONNAIRE,
  onboarding_manager: HELLY_STATES.HM_ONBOARDING_INTRO,
  waiting_job: HELLY_STATES.HM_WAIT_JD,
  extracting_job: HELLY_STATES.HM_JD_PROCESSING,
  interviewing_manager: HELLY_STATES.HM_INTERVIEW_IN_PROGRESS,
  job_profile_ready: HELLY_STATES.HM_JD_REVIEW,
  manager_mandatory_fields: HELLY_STATES.HM_QUESTIONNAIRE,
  job_published: HELLY_STATES.HM_VACANCY_OPEN,
  waiting_candidate_decision: HELLY_STATES.WAIT_CANDIDATE_DECISION,
  waiting_manager_decision: HELLY_STATES.WAIT_MANAGER_DECISION,
  contact_shared: HELLY_STATES.CONTACT_SHARED,
};
