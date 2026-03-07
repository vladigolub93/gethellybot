import { CandidateProfile, JobProfile } from "../shared/types/domain.types";

export class ProfileSummaryService {
  formatCandidateSummary(profile: CandidateProfile): string {
    return [
      "Candidate Profile Summary",
      "",
      `Headline: ${orDash(profile.headline)}`,
      `Seniority: ${profile.seniorityEstimate}`,
      `Core skills: ${formatList(profile.coreSkills)}`,
      `Secondary skills: ${formatList(profile.secondarySkills)}`,
      `Experience: ${orDash(profile.yearsExperienceTotal)}`,
      `Domains: ${formatList(profile.domains)}`,
      `Location/Timezone: ${orDash(profile.constraints.location)} / ${orDash(profile.constraints.timezone)}`,
      `Format: ${orDash(profile.constraints.workFormat)}`,
      `Salary: ${orDash(profile.constraints.salaryExpectation)}`,
      `Availability: ${orDash(profile.constraints.availabilityDate)}`,
      `Dealbreakers: ${formatList(profile.dealbreakers)}`,
    ].join("\n");
  }

  formatJobSummary(profile: JobProfile): string {
    return [
      "Job Profile Summary",
      "",
      `Title: ${orDash(profile.title)}`,
      `Seniority target: ${orDash(profile.seniorityTarget)}`,
      `Must-have skills: ${formatList(profile.mustHaveSkills)}`,
      `Nice-to-have skills: ${formatList(profile.niceToHaveSkills)}`,
      `Domain: ${orDash(profile.domain)}`,
      `Responsibilities: ${orDash(profile.responsibilitiesSummary)}`,
      `Timezone overlap: ${orDash(profile.constraints.timezoneOverlap)}`,
      `Location/Format: ${orDash(profile.constraints.location)} / ${orDash(profile.constraints.format)}`,
      `Budget: ${orDash(profile.constraints.budgetRange)}`,
      `Contract: ${orDash(profile.constraints.contractType)}`,
      `Urgency: ${orDash(profile.urgency)}`,
      `Dealbreakers: ${formatList(profile.dealbreakers)}`,
    ].join("\n");
  }
}

function formatList(items: ReadonlyArray<string>): string {
  if (items.length === 0) {
    return "-";
  }
  return items.slice(0, 8).join(", ");
}

function orDash(value: string): string {
  return value || "-";
}
