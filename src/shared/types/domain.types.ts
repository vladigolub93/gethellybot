export interface InterviewQuestion {
  readonly id: string;
  readonly question: string;
  readonly goal: string;
  readonly gapToClarify: string;
}

export interface InterviewPlan {
  readonly summary: string;
  readonly questions: ReadonlyArray<InterviewQuestion>;
}

export interface CandidateProject {
  readonly role: string;
  readonly impact: string;
  readonly stack: ReadonlyArray<string>;
}

export interface CandidateConstraints {
  readonly timezone: string;
  readonly location: string;
  readonly workFormat: string;
  readonly salaryExpectation: string;
  readonly availabilityDate: string;
}

export interface CandidateCommunication {
  readonly englishLevelEstimate: string;
  readonly notes: string;
}

export interface CandidateProfile {
  readonly candidateId: string;
  readonly headline: string;
  readonly seniorityEstimate: "junior" | "mid" | "senior" | "lead" | "unknown";
  readonly coreSkills: ReadonlyArray<string>;
  readonly secondarySkills: ReadonlyArray<string>;
  readonly yearsExperienceTotal: string;
  readonly relevantExperienceSummary: string;
  readonly domains: ReadonlyArray<string>;
  readonly notableProjects: ReadonlyArray<CandidateProject>;
  readonly constraints: CandidateConstraints;
  readonly communication: CandidateCommunication;
  readonly redFlags: ReadonlyArray<string>;
  readonly dealbreakers: ReadonlyArray<string>;
  readonly searchableText: string;
}

export interface JobConstraints {
  readonly timezoneOverlap: string;
  readonly location: string;
  readonly format: string;
  readonly budgetRange: string;
  readonly contractType: string;
}

export interface JobProfile {
  readonly jobId: string;
  readonly title: string;
  readonly mustHaveSkills: ReadonlyArray<string>;
  readonly niceToHaveSkills: ReadonlyArray<string>;
  readonly responsibilitiesSummary: string;
  readonly domain: string;
  readonly seniorityTarget: string;
  readonly constraints: JobConstraints;
  readonly interviewProcessSummary: string;
  readonly urgency: string;
  readonly dealbreakers: ReadonlyArray<string>;
  readonly searchableText: string;
}

export type DocumentType = "pdf" | "docx" | "unknown";

export interface CandidateInterviewArtifact {
  readonly title: "Interview Summary";
  readonly profileSnapshot: string;
  readonly strengths: ReadonlyArray<string>;
  readonly gaps: ReadonlyArray<string>;
  readonly nextStep: string;
}

export interface HiringInterviewArtifact {
  readonly title: "Role Intake Summary";
  readonly roleOverview: string;
  readonly mustHaves: ReadonlyArray<string>;
  readonly risks: ReadonlyArray<string>;
  readonly nextStep: string;
}

export type InterviewResultArtifact = CandidateInterviewArtifact | HiringInterviewArtifact;
