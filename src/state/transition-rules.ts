import { UserState } from "../shared/types/state.types";

const transitionRules: Record<UserState, UserState[]> = {
  role_selection: ["onboarding_candidate", "onboarding_manager", "waiting_resume", "waiting_job"],
  onboarding_candidate: ["waiting_resume", "role_selection"],
  waiting_resume: ["interviewing_candidate", "role_selection"],
  interviewing_candidate: ["candidate_profile_ready", "role_selection"],
  candidate_profile_ready: ["candidate_mandatory_fields", "waiting_candidate_decision", "role_selection"],
  candidate_mandatory_fields: ["candidate_profile_ready", "role_selection"],
  onboarding_manager: ["waiting_job", "role_selection"],
  waiting_job: ["interviewing_manager", "role_selection"],
  interviewing_manager: ["job_profile_ready", "role_selection"],
  job_profile_ready: ["manager_mandatory_fields", "job_published", "role_selection"],
  manager_mandatory_fields: ["job_profile_ready", "job_published", "role_selection"],
  job_published: ["manager_mandatory_fields", "waiting_candidate_decision", "waiting_manager_decision", "role_selection"],
  waiting_candidate_decision: [
    "waiting_manager_decision",
    "candidate_profile_ready",
    "candidate_mandatory_fields",
    "contact_shared",
    "role_selection",
  ],
  waiting_manager_decision: ["manager_mandatory_fields", "contact_shared", "job_published", "role_selection"],
  contact_shared: [
    "candidate_profile_ready",
    "candidate_mandatory_fields",
    "manager_mandatory_fields",
    "job_published",
    "role_selection",
  ],
};

export function isAllowedTransition(from: UserState, to: UserState): boolean {
  return transitionRules[from].includes(to);
}
