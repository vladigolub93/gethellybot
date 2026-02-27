import { CandidateResumeAnalysisV2 } from "../../shared/types/candidate-analysis.types";
import { JobProfileV2 } from "../../shared/types/job-profile.types";
import { MatchScoreV2 } from "../../shared/types/matching.types";

const CORE_TECH_MAX = 35;
const DOMAIN_MAX = 20;
const OWNERSHIP_MAX = 15;
const ARCH_SCALE_MAX = 15;
const CHALLENGE_MAX = 15;

export function calculateMatchingScoreV2(
  candidateAnalysis: CandidateResumeAnalysisV2,
  jobProfile: JobProfileV2,
): MatchScoreV2 {
  const hardFilterFailures = evaluateHardFilters(candidateAnalysis, jobProfile);
  const passHardFilters = hardFilterFailures.length === 0;

  const coreTechDepth = scoreCoreTechDepth(candidateAnalysis, jobProfile);
  const domainAlignment = scoreDomainAlignment(candidateAnalysis, jobProfile);
  const ownershipAlignment = scoreOwnershipAlignment(candidateAnalysis, jobProfile);
  const architectureScaleAlignment = scoreArchitectureScaleAlignment(candidateAnalysis, jobProfile);
  const challengeAlignment = scoreChallengeAlignment(candidateAnalysis, jobProfile);

  const totalScore = clampScore(
    Math.round(
      coreTechDepth +
        domainAlignment +
        ownershipAlignment +
        architectureScaleAlignment +
        challengeAlignment,
    ),
  );

  return {
    totalScore,
    passHardFilters,
    hardFilterFailures,
    breakdown: {
      coreTechDepth,
      domainAlignment,
      ownershipAlignment,
      architectureScaleAlignment,
      challengeAlignment,
    },
    reasons: buildReasons(candidateAnalysis, jobProfile, hardFilterFailures),
  };
}

function evaluateHardFilters(
  candidateAnalysis: CandidateResumeAnalysisV2,
  jobProfile: JobProfileV2,
): string[] {
  const failures: string[] = [];

  const mandatoryCore = jobProfile.technology_map.core.filter((tech) => tech.mandatory);
  for (const tech of mandatoryCore) {
    const candidateDepth = resolveCandidateTechDepth(candidateAnalysis, tech.technology);
    if (candidateDepth <= 0) {
      failures.push(`Missing mandatory core technology: ${tech.technology}`);
    }
  }

  if (jobProfile.domain_requirements.domain_depth_required === "critical") {
    const requiredDomain = normalizeTechName(jobProfile.domain_requirements.primary_domain ?? "");
    const match = candidateAnalysis.domain_expertise.find((item) => {
      const domain = normalizeTechName(item.domain);
      if (!requiredDomain) {
        return item.depth_level === "medium" || item.depth_level === "high";
      }
      return domain.includes(requiredDomain) || requiredDomain.includes(domain);
    });
    if (!match || (match.depth_level !== "medium" && match.depth_level !== "high")) {
      failures.push("Critical domain depth requirement is not met.");
    }
  }

  if (
    jobProfile.ownership_expectation.decision_authority_required === "technical_lead" &&
    candidateAnalysis.decision_authority_level === "executor"
  ) {
    failures.push("Decision authority mismatch for technical lead expectation.");
  }

  if (
    jobProfile.ownership_expectation.production_responsibility === "yes" &&
    !candidateAnalysis.ownership_signals.production_responsibility
  ) {
    failures.push("Production responsibility is required by job but not validated for candidate.");
  }

  return failures;
}

function scoreCoreTechDepth(
  candidateAnalysis: CandidateResumeAnalysisV2,
  jobProfile: JobProfileV2,
): number {
  const core = jobProfile.technology_map.core;
  if (core.length === 0) {
    return 18;
  }

  let weightedScore = 0;
  let totalWeight = 0;

  for (const tech of core) {
    const weight = tech.mandatory ? 1.5 : 1;
    const requiredRank = depthRank(tech.required_depth);
    const candidateRank = resolveCandidateTechDepth(candidateAnalysis, tech.technology);
    const ratio =
      candidateRank >= requiredRank
        ? 1
        : candidateRank === requiredRank - 1
          ? 0.5
          : 0;

    weightedScore += ratio * weight;
    totalWeight += weight;
  }

  if (totalWeight === 0) {
    return 0;
  }

  return round2((weightedScore / totalWeight) * CORE_TECH_MAX);
}

function scoreDomainAlignment(
  candidateAnalysis: CandidateResumeAnalysisV2,
  jobProfile: JobProfileV2,
): number {
  const requiredLevel = jobProfile.domain_requirements.domain_depth_required;
  const requiredDomain = normalizeTechName(jobProfile.domain_requirements.primary_domain ?? "");
  const matchedDomain = candidateAnalysis.domain_expertise.find((domain) => {
    if (!requiredDomain) {
      return true;
    }
    const candidateDomain = normalizeTechName(domain.domain);
    return (
      candidateDomain.includes(requiredDomain) ||
      requiredDomain.includes(candidateDomain)
    );
  });

  if (requiredLevel === "none") {
    return 10;
  }
  if (requiredLevel === "helpful") {
    return matchedDomain ? 14 : 8;
  }
  if (requiredLevel === "important") {
    if (!matchedDomain) {
      return 5;
    }
    if (matchedDomain.depth_level === "high" || matchedDomain.depth_level === "medium") {
      return 18;
    }
    return 12;
  }
  if (requiredLevel === "critical") {
    if (!matchedDomain) {
      return 0;
    }
    if (matchedDomain.depth_level === "high") {
      return 20;
    }
    if (matchedDomain.depth_level === "medium") {
      return 16;
    }
    return 8;
  }
  return 10;
}

function scoreOwnershipAlignment(
  candidateAnalysis: CandidateResumeAnalysisV2,
  jobProfile: JobProfileV2,
): number {
  const required = authorityRank(jobProfile.ownership_expectation.decision_authority_required);
  const candidate = authorityRank(candidateAnalysis.decision_authority_level);
  const distance = Math.abs(required - candidate);

  let score = distance === 0 ? 12 : distance === 1 ? 9 : distance === 2 ? 5 : 2;
  if (candidateAnalysis.hands_on_level === "high") {
    score += 2;
  } else if (candidateAnalysis.hands_on_level === "medium") {
    score += 1;
  }

  if (jobProfile.ownership_expectation.production_responsibility === "yes") {
    score += candidateAnalysis.ownership_signals.production_responsibility ? 2 : -3;
  }

  return clampToRange(round2(score), 0, OWNERSHIP_MAX);
}

function scoreArchitectureScaleAlignment(
  candidateAnalysis: CandidateResumeAnalysisV2,
  jobProfile: JobProfileV2,
): number {
  let score = 0;
  const architectureStyle = jobProfile.architecture_and_scale.architecture_style;

  if (architectureStyle === "unknown") {
    score += 4;
  } else if (architectureStyle === "microservices" && candidateAnalysis.architecture_signals.microservices) {
    score += 6;
  } else if (architectureStyle === "monolith" && candidateAnalysis.architecture_signals.monolith) {
    score += 6;
  } else if (architectureStyle === "event_driven" && candidateAnalysis.architecture_signals.event_driven) {
    score += 6;
  } else if (architectureStyle === "mixed" && candidateAnalysis.architecture_signals.distributed_systems) {
    score += 6;
  } else {
    score += 2;
  }

  if (jobProfile.architecture_and_scale.distributed_systems === "yes") {
    score += candidateAnalysis.architecture_signals.distributed_systems ? 3 : 0;
  } else if (jobProfile.architecture_and_scale.distributed_systems === "unknown") {
    score += 1;
  } else {
    score += 2;
  }

  if (jobProfile.architecture_and_scale.high_load === "yes") {
    score += candidateAnalysis.architecture_signals.high_load ? 3 : 0;
  } else if (jobProfile.architecture_and_scale.high_load === "unknown") {
    score += 1;
  } else {
    score += 2;
  }

  const complexity = candidateAnalysis.system_complexity_level;
  if (complexity === "high") {
    score += 3;
  } else if (complexity === "medium") {
    score += 2;
  } else if (complexity === "low") {
    score += 1;
  }

  return clampToRange(round2(score), 0, ARCH_SCALE_MAX);
}

function scoreChallengeAlignment(
  candidateAnalysis: CandidateResumeAnalysisV2,
  jobProfile: JobProfileV2,
): number {
  const challengeText = [
    ...jobProfile.work_scope.current_challenges,
    ...jobProfile.work_scope.current_tasks,
    ...jobProfile.work_scope.deliverables_or_outcomes,
  ].join(" ");
  const candidateSignals = [
    ...candidateAnalysis.impact_indicators,
    ...candidateAnalysis.interview_focus_recommendations,
    ...candidateAnalysis.core_technologies.map((tech) => tech.name),
  ].join(" ");

  const challengeTokens = tokenize(challengeText);
  const candidateTokens = tokenize(candidateSignals);

  if (challengeTokens.size === 0) {
    return 8;
  }

  const overlap = countOverlap(challengeTokens, candidateTokens);
  const overlapRatio = overlap / challengeTokens.size;

  const jobTech = new Set(jobProfile.technology_map.core.map((tech) => normalizeTechName(tech.technology)));
  const candidateTech = new Set(
    [
      ...candidateAnalysis.skill_depth_classification.deep_experience,
      ...candidateAnalysis.skill_depth_classification.working_experience,
      ...candidateAnalysis.skill_depth_classification.mentioned_only,
    ].map((item) => normalizeTechName(item)),
  );
  const techOverlap = countOverlap(jobTech, candidateTech);
  const techRatio = jobTech.size === 0 ? 0.4 : techOverlap / jobTech.size;

  return clampToRange(round2(overlapRatio * 10 + techRatio * 5), 0, CHALLENGE_MAX);
}

function buildReasons(
  candidateAnalysis: CandidateResumeAnalysisV2,
  jobProfile: JobProfileV2,
  hardFilterFailures: string[],
): MatchScoreV2["reasons"] {
  const topMatches: string[] = [];
  const topGaps: string[] = [];
  const risks: string[] = [...hardFilterFailures];

  const coreMatches = jobProfile.technology_map.core
    .filter((tech) => resolveCandidateTechDepth(candidateAnalysis, tech.technology) > 0)
    .slice(0, 3)
    .map((tech) => tech.technology);
  if (coreMatches.length > 0) {
    topMatches.push(`Core tech overlap: ${coreMatches.join(", ")}.`);
  }

  if (candidateAnalysis.ownership_signals.production_responsibility) {
    topMatches.push("Production responsibility signal is present.");
  }

  if (candidateAnalysis.domain_expertise.length > 0) {
    topMatches.push(
      `Domain exposure: ${candidateAnalysis.domain_expertise
        .slice(0, 2)
        .map((item) => item.domain)
        .join(", ")}.`,
    );
  }

  const missingMandatory = jobProfile.technology_map.core
    .filter(
      (tech) =>
        tech.mandatory && resolveCandidateTechDepth(candidateAnalysis, tech.technology) <= 0,
    )
    .map((tech) => tech.technology);
  if (missingMandatory.length > 0) {
    topGaps.push(`Missing mandatory technologies: ${missingMandatory.join(", ")}.`);
  }

  if (candidateAnalysis.hands_on_level === "low" || candidateAnalysis.hands_on_level === "unclear") {
    topGaps.push("Hands-on depth is unclear for required scope.");
  }

  risks.push(...candidateAnalysis.technical_risk_flags.slice(0, 3));

  return {
    topMatches: topMatches.slice(0, 5),
    topGaps: topGaps.slice(0, 5),
    risks: Array.from(new Set(risks.filter((item) => Boolean(item)))).slice(0, 5),
  };
}

function resolveCandidateTechDepth(
  candidateAnalysis: CandidateResumeAnalysisV2,
  techName: string,
): number {
  const normalized = normalizeTechName(techName);
  if (!normalized) {
    return 0;
  }

  if (hasTech(candidateAnalysis.skill_depth_classification.deep_experience, normalized)) {
    return depthRank("expert");
  }
  if (hasTech(candidateAnalysis.skill_depth_classification.working_experience, normalized)) {
    return depthRank("strong");
  }
  if (hasTech(candidateAnalysis.skill_depth_classification.mentioned_only, normalized)) {
    return depthRank("basic");
  }

  const fromCore = candidateAnalysis.core_technologies.find(
    (tech) => normalizeTechName(tech.name) === normalized,
  );
  if (fromCore) {
    return fromCore.confidence >= 0.75 ? depthRank("working") : depthRank("basic");
  }

  return 0;
}

function hasTech(values: ReadonlyArray<string>, normalizedTech: string): boolean {
  return values.some((value) => normalizeTechName(value) === normalizedTech);
}

export function normalizeTechName(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9+#.]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function depthRank(
  depth: "none" | "basic" | "working" | "strong" | "expert",
): number {
  switch (depth) {
    case "basic":
      return 1;
    case "working":
      return 2;
    case "strong":
      return 3;
    case "expert":
      return 4;
    default:
      return 0;
  }
}

function authorityRank(
  value:
    | "executor"
    | "contributor"
    | "owner"
    | "technical_lead"
    | "unknown"
    | "tech_lead"
    | "unclear",
): number {
  switch (value) {
    case "executor":
      return 1;
    case "contributor":
      return 2;
    case "owner":
      return 3;
    case "technical_lead":
    case "tech_lead":
      return 4;
    default:
      return 2;
  }
}

export function tokenize(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .replace(/[^a-z0-9+#.]/g, " ")
      .split(/\s+/)
      .map((token) => token.trim())
      .filter((token) => token.length >= 3),
  );
}

function countOverlap(left: Set<string>, right: Set<string>): number {
  let total = 0;
  for (const token of left) {
    if (right.has(token)) {
      total += 1;
    }
  }
  return total;
}

function clampScore(value: number): number {
  return clampToRange(value, 0, 100);
}

function clampToRange(value: number, min: number, max: number): number {
  if (value < min) {
    return min;
  }
  if (value > max) {
    return max;
  }
  return value;
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}
