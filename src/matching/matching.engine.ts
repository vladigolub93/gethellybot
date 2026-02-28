import { EmbeddingsClient } from "../ai/embeddings.client";
import { LlmClient } from "../ai/llm.client";
import { Logger } from "../config/logger";
import { JobsRepository } from "../db/repositories/jobs.repo";
import { ProfilesRepository } from "../db/repositories/profiles.repo";
import { UsersRepository } from "../db/repositories/users.repo";
import { CandidateTechnicalSummaryV1 } from "../shared/types/candidate-summary.types";
import { JobTechnicalSummaryV2 } from "../shared/types/job-profile.types";
import { MatchingDecisionV1 } from "../shared/types/matching-decision.types";
import { MatchBreakdownV2, MatchReasonsV2, MatchingExplanationV1 } from "../shared/types/matching.types";
import { InterviewStorageService } from "../storage/interview-storage.service";
import { MatchRecord } from "../decisions/match.types";
import { MatchStorageService } from "../storage/match-storage.service";
import { QualityFlagsService } from "../qa/quality-flags.service";
import { MatchingExplanationService } from "./matching-explanation.service";
import { MatchingDecisionService } from "./matching-decision.service";
import { QdrantClient } from "./qdrant.client";
import { calculateMatchingScoreV2 } from "./scoring/matching-score.v2";
import { VectorSearchRepository } from "./vector-search.repo";
import { VectorSearchV2 } from "./vector-search.v2";

const SHORTLIST_TOP_N = 50;
const MAX_CANDIDATES_TO_SCORE = 200;
const TOP_K_RESULTS = 3;
const MINIMUM_SCORE_TO_NOTIFY_CANDIDATE = 70;
const MINIMUM_SCORE_TO_NOTIFY_MANAGER = 75;

export interface CandidateMatch {
  candidateUserId: number;
  score: number;
  breakdown: MatchBreakdownV2;
  reasons: MatchReasonsV2;
  explanation: string;
  explanationJson: MatchingExplanationV1;
  candidateSummary: string;
  candidateTechnicalSummary?: CandidateTechnicalSummaryV1 | null;
  jobTechnicalSummary?: JobTechnicalSummaryV2 | null;
  visibleToManager: boolean;
  decision: MatchingDecisionV1;
}

export interface MatchingRunResult {
  managerUserId: number;
  jobSummary: string;
  matches: CandidateMatch[];
}

export interface RunForUserResult {
  role: "candidate" | "manager";
  target: "roles" | "candidates";
  message: string;
}

export class MatchingEngine {
  private readonly vectorSearchV2: VectorSearchV2;
  private readonly explanationService: MatchingExplanationService;
  private readonly decisionService: MatchingDecisionService;

  constructor(
    private readonly storage: InterviewStorageService,
    private readonly embeddingsClient: EmbeddingsClient,
    private readonly vectorSearchRepository: VectorSearchRepository,
    private readonly profilesRepository: ProfilesRepository,
    private readonly jobsRepository: JobsRepository,
    private readonly usersRepository: UsersRepository,
    private readonly matchStorageService: MatchStorageService,
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
    private readonly qdrantClient?: QdrantClient,
    private readonly qualityFlagsService?: QualityFlagsService,
  ) {
    this.vectorSearchV2 = new VectorSearchV2(
      this.embeddingsClient,
      this.profilesRepository,
      this.vectorSearchRepository,
      this.storage,
      this.logger,
      this.qdrantClient,
    );
    this.explanationService = new MatchingExplanationService(this.llmClient);
    this.decisionService = new MatchingDecisionService(
      this.llmClient,
      this.logger,
      this.qualityFlagsService,
    );
  }

  async runForManager(managerUserId: number, _jobId?: string): Promise<MatchingRunResult | null>;
  async runForManager(userId: string, jobId?: string): Promise<RunForUserResult>;
  async runForManager(
    managerUserIdOrUserId: number | string,
    jobId?: string,
  ): Promise<MatchingRunResult | RunForUserResult | null> {
    if (typeof managerUserIdOrUserId === "string") {
      return this.runForUserWithResult(managerUserIdOrUserId, "manager", jobId);
    }
    const managerUserId = managerUserIdOrUserId;

    const jobProfile = await this.jobsRepository.getJobProfileV2(managerUserId);
    if (!jobProfile) {
      return null;
    }
    const mandatoryComplete = await this.jobsRepository.evaluateJobCompleteness(managerUserId);
    if (!mandatoryComplete) {
      return null;
    }
    const jobMandatoryFields = await this.jobsRepository.getJobMandatoryFields(managerUserId);
    const jobTechnicalSummary = await this.jobsRepository.getJobTechnicalSummary(managerUserId);
    const jobSummary = buildJobSummary(jobTechnicalSummary, jobProfile);
    const jobStatus = await this.jobsRepository.getManagerJobStatus(managerUserId);
    const jobActiveStatus = jobStatus === "active";
    if (!jobSummary) {
      return null;
    }
    if (!jobActiveStatus) {
      return null;
    }

    const shortlistIds = await this.vectorSearchV2.shortlistCandidateIds({
      jobProfile,
      jobTechnicalSummary,
      topN: SHORTLIST_TOP_N,
    });

    const history = await this.matchStorageService.listAll();
    const ranked: CandidateMatch[] = [];
    for (const candidateUserId of shortlistIds.slice(0, MAX_CANDIDATES_TO_SCORE)) {
      const candidateMandatory = await this.usersRepository.getCandidateMandatoryFields(candidateUserId);
      if (!candidateMandatory.profileComplete) {
        continue;
      }
      if (!passesJobMandatoryFilters(jobMandatoryFields, candidateMandatory)) {
        continue;
      }
      if (!passesMandatoryConstraintFilters(jobProfile, candidateMandatory)) {
        continue;
      }

      const source = await this.profilesRepository.getCandidateMatchSource(candidateUserId);
      if (!source) {
        continue;
      }

      const score = calculateMatchingScoreV2(source.resumeAnalysis, jobProfile);
      if (!score.passHardFilters) {
        continue;
      }

      const explanationJson = await this.generateExplanation({
        jobTechnicalSummary,
        candidateTechnicalSummary: source.technicalSummary,
        score: score.totalScore,
        breakdown: score.breakdown,
        reasons: score.reasons,
      });

      const decision = await this.decisionService.decide({
        managerUserId,
        candidateUserId,
        matchScore: score.totalScore,
        breakdown: score.breakdown,
        hardFilterFailed: !score.passHardFilters,
        candidateUnresolvedRiskFlags: source.technicalSummary?.risk_flags ?? [],
        candidateInterviewConfidence: source.technicalSummary?.interview_confidence_level ?? "medium",
        jobActiveStatus,
        candidateActivityRecencyHours: hoursSinceLatestCandidateActivity(source),
        managerActivityRecencyHours: hoursSinceLatestManagerActivity(history, managerUserId),
        candidateCooldownStatus: isRecentCandidateNotification(history, candidateUserId, 12),
        managerCooldownStatus: isRecentManagerNotification(history, managerUserId, 6),
        candidatePreviouslyRejectedSameJob: hasCandidateRejectedSameJob(
          history,
          managerUserId,
          candidateUserId,
        ),
        managerPreviouslySkippedSameCandidate: hasManagerSkippedSameCandidate(
          history,
          managerUserId,
          candidateUserId,
        ),
      });

      if (score.totalScore >= 85 && (source.technicalSummary?.interview_confidence_level ?? "medium") === "low") {
        await this.qualityFlagsService?.raise({
          entityType: "match",
          entityId: `${managerUserId}:${candidateUserId}`,
          flag: "matching_score_high_but_confidence_low",
          details: {
            score: score.totalScore,
          },
        });
      }

      ranked.push({
        candidateUserId,
        score: score.totalScore,
        breakdown: score.breakdown,
        reasons: score.reasons,
        explanation: explanationJson.message_for_candidate,
        explanationJson,
        candidateSummary: buildCandidateSummary(source.technicalSummary, source.searchableText),
        candidateTechnicalSummary: source.technicalSummary,
        jobTechnicalSummary,
        visibleToManager: score.totalScore >= MINIMUM_SCORE_TO_NOTIFY_MANAGER,
        decision,
      });
    }

    ranked.sort((a, b) => b.score - a.score);
    const topMatches = ranked
      .filter(
        (item) =>
          item.score >= MINIMUM_SCORE_TO_NOTIFY_CANDIDATE &&
          item.decision.notify_candidate,
      )
      .slice(0, TOP_K_RESULTS);

    if (topMatches.length === 0) {
      return null;
    }

    return {
      managerUserId,
      jobSummary,
      matches: topMatches,
    };
  }

  async runForCandidate(userId: string): Promise<RunForUserResult> {
    return this.runForUserWithResult(userId, "candidate");
  }

  async runForUser(userId: string): Promise<void> {
    await this.runForUserWithResult(userId);
  }

  async runForUserWithResult(
    userId: string,
    roleHint?: "candidate" | "manager",
    jobId?: string,
  ): Promise<RunForUserResult> {
    const telegramUserId = Number(userId);
    if (!Number.isInteger(telegramUserId) || telegramUserId <= 0) {
      return {
        role: "candidate",
        target: "roles",
        message: "Could not run matching because user id is invalid.",
      };
    }

    const managerRun = roleHint === "candidate" ? null : await this.runForManager(telegramUserId, jobId);
    if (managerRun && roleHint !== "candidate") {
      const records = await this.matchStorageService.createForJob(
        telegramUserId,
        managerRun.jobSummary,
        managerRun.matches.map((match) => ({
          candidateUserId: match.candidateUserId,
          jobId: null,
          candidateId: null,
          candidateSummary: match.candidateSummary,
          jobTechnicalSummary: match.jobTechnicalSummary ?? null,
          candidateTechnicalSummary: match.candidateTechnicalSummary ?? null,
          score: match.score,
          breakdown: match.breakdown,
          reasons: match.reasons,
          explanationJson: match.explanationJson,
          matchingDecision: match.decision,
          explanation: match.explanation,
        })),
      );
      return {
        role: "manager",
        target: "candidates",
        message: this.formatManagerMatchMessage(
          managerRun.matches.map((match) => {
            const stored = records.find((item) => item.candidateUserId === match.candidateUserId);
            return {
              ...match,
              explanation: stored?.explanation ?? match.explanation,
            };
          }),
        ),
      };
    }
    if (roleHint === "manager") {
      return {
        role: "manager",
        target: "candidates",
        message: "I can start matching after we fill work format, allowed countries for remote roles, and budget.",
      };
    }

    const candidateSource = await this.profilesRepository.getCandidateMatchSource(telegramUserId);
    if (!candidateSource) {
      return {
        role: "candidate",
        target: "roles",
        message: "Profile is not ready for matching yet. Complete your interview first.",
      };
    }

    const mandatoryComplete = await this.usersRepository.evaluateCandidateCompleteness(telegramUserId);
    if (!mandatoryComplete) {
      return {
        role: "candidate",
        target: "roles",
        message: "I can start matching after we fill your location, work mode, and salary details.",
      };
    }

    const activeManagers = await this.jobsRepository.listActiveManagerTelegramUserIds(200);
    const candidateMatches: Array<{
      managerUserId: number;
      jobSummary: string;
      match: CandidateMatch;
    }> = [];

    for (const managerId of activeManagers) {
      const run = await this.runForManager(managerId);
      if (!run) {
        continue;
      }
      const candidateMatch = run.matches.find((item) => item.candidateUserId === telegramUserId);
      if (!candidateMatch) {
        continue;
      }
      candidateMatches.push({
        managerUserId: managerId,
        jobSummary: run.jobSummary,
        match: candidateMatch,
      });
    }

    if (candidateMatches.length === 0) {
      return {
        role: "candidate",
        target: "roles",
        message: "No matching roles found right now.",
      };
    }

    candidateMatches.sort((a, b) => b.match.score - a.match.score);
    const top = candidateMatches.slice(0, TOP_K_RESULTS);
    const lines = ["Top matching roles:", ""];
    for (const [index, item] of top.entries()) {
      lines.push(`${index + 1}) Score ${Math.round(item.match.score)}%`);
      lines.push(`   ${item.jobSummary.slice(0, 220)}`);
      lines.push(`   ${item.match.explanationJson.message_for_candidate}`);
    }

    return {
      role: "candidate",
      target: "roles",
      message: lines.join("\n"),
    };
  }

  formatManagerMatchMessage(matches: ReadonlyArray<CandidateMatch>): string {
    const managerVisible = matches.filter((item) => item.visibleToManager);
    if (managerVisible.length === 0) {
      return "No suitable candidates found yet.";
    }

    const lines = ["Top matching candidates:", ""];
    for (const [index, match] of managerVisible.entries()) {
      lines.push(`${index + 1}) Candidate #${match.candidateUserId} | score ${Math.round(match.score)}`);
      lines.push(`   ${match.explanationJson.message_for_manager}`);
    }

    return lines.join("\n");
  }

  private async generateExplanation(input: {
    jobTechnicalSummary: JobTechnicalSummaryV2 | null;
    candidateTechnicalSummary: CandidateTechnicalSummaryV1 | null;
    score: number;
    breakdown: MatchBreakdownV2;
    reasons: MatchReasonsV2;
  }): Promise<MatchingExplanationV1> {
    try {
      return await this.explanationService.generate({
        jobTechnicalSummary: input.jobTechnicalSummary,
        candidateTechnicalSummary: input.candidateTechnicalSummary,
        deterministicScore: input.score,
        breakdown: input.breakdown,
        reasons: input.reasons,
      });
    } catch (error) {
      this.logger.warn("Matching explanation generation failed, using fallback explanation", {
        error: error instanceof Error ? error.message : "Unknown error",
      });
      const jobHeadline = input.jobTechnicalSummary?.headline || "this role";
      const candidateHeadline = input.candidateTechnicalSummary?.headline || "candidate profile";
      return {
        message_for_candidate: `This role matches your profile for ${jobHeadline}. Review details and Apply or Reject.`,
        message_for_manager: `${candidateHeadline} aligns on key requirements. Review and choose Want to talk or Skip.`,
        one_suggested_live_question:
          "Can you describe one recent project that best reflects this role requirements?",
      };
    }
  }
}

function hasCandidateRejectedSameJob(
  history: ReadonlyArray<MatchRecord>,
  managerUserId: number,
  candidateUserId: number,
): boolean {
  return history.some(
    (item) =>
      item.managerUserId === managerUserId &&
      item.candidateUserId === candidateUserId &&
      item.candidateDecision === "rejected",
  );
}

function hasManagerSkippedSameCandidate(
  history: ReadonlyArray<MatchRecord>,
  managerUserId: number,
  candidateUserId: number,
): boolean {
  return history.some(
    (item) =>
      item.managerUserId === managerUserId &&
      item.candidateUserId === candidateUserId &&
      item.managerDecision === "rejected",
  );
}

function hoursSinceLatestManagerActivity(
  history: ReadonlyArray<MatchRecord>,
  managerUserId: number,
): number | null {
  const latest = history
    .filter((item) => item.managerUserId === managerUserId)
    .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))[0];
  if (!latest) {
    return null;
  }
  return hoursBetween(latest.updatedAt, new Date().toISOString());
}

function hoursSinceLatestCandidateActivity(source: {
  searchableText: string;
}): number | null {
  if (!source.searchableText.trim()) {
    return null;
  }
  return null;
}

function isRecentCandidateNotification(
  history: ReadonlyArray<MatchRecord>,
  candidateUserId: number,
  windowHours: number,
): boolean {
  const latest = history
    .filter((item) => item.candidateUserId === candidateUserId)
    .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))[0];
  if (!latest) {
    return false;
  }
  return hoursBetween(latest.updatedAt, new Date().toISOString()) < windowHours;
}

function isRecentManagerNotification(
  history: ReadonlyArray<MatchRecord>,
  managerUserId: number,
  windowHours: number,
): boolean {
  const latest = history
    .filter((item) => item.managerUserId === managerUserId)
    .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))[0];
  if (!latest) {
    return false;
  }
  return hoursBetween(latest.updatedAt, new Date().toISOString()) < windowHours;
}

function hoursBetween(fromIso: string, toIso: string): number {
  const from = new Date(fromIso).getTime();
  const to = new Date(toIso).getTime();
  if (!Number.isFinite(from) || !Number.isFinite(to)) {
    return 9999;
  }
  return Math.max(0, (to - from) / (1000 * 60 * 60));
}

function buildJobSummary(
  summary: JobTechnicalSummaryV2 | null,
  jobProfile: {
    role_title: string | null;
    product_context: { what_the_product_does: string | null };
    technology_map: { core: Array<{ technology: string }> };
    work_scope: { current_tasks: string[] };
  },
): string {
  if (summary) {
    return [
      summary.headline,
      summary.product_context,
      summary.core_tech.join(", "),
      summary.key_requirements.join(", "),
      summary.notes_for_matching,
    ]
      .filter((item) => Boolean(item))
      .join(" | ")
      .slice(0, 1200);
  }

  return [
    jobProfile.role_title ?? "",
    jobProfile.product_context.what_the_product_does ?? "",
    jobProfile.technology_map.core.map((tech) => tech.technology).join(", "),
    jobProfile.work_scope.current_tasks.join(", "),
  ]
    .filter((item) => Boolean(item))
    .join(" | ")
    .slice(0, 1200);
}

function buildCandidateSummary(
  technicalSummary: CandidateTechnicalSummaryV1 | null,
  fallbackSearchableText: string,
): string {
  if (technicalSummary) {
    return [
      technicalSummary.headline,
      technicalSummary.technical_depth_summary,
      technicalSummary.ownership_and_authority,
    ]
      .filter((item) => Boolean(item))
      .join(" | ")
      .slice(0, 500);
  }

  return fallbackSearchableText.slice(0, 500);
}

function passesMandatoryConstraintFilters(
  jobProfile: {
    constraints: string[];
  },
  candidate: {
    country: string;
    workMode: "remote" | "hybrid" | "onsite" | "flexible" | null;
    salaryAmount: number | null;
    salaryCurrency: "USD" | "EUR" | "ILS" | "GBP" | "other" | null;
    salaryPeriod: "month" | "year" | null;
  },
): boolean {
  const constraintsText = jobProfile.constraints.join(" ").toLowerCase();
  if (!constraintsText.trim()) {
    return true;
  }

  if (
    (constraintsText.includes("remote only") || constraintsText.includes("remote-first")) &&
    candidate.workMode === "onsite"
  ) {
    return false;
  }

  if (
    (constraintsText.includes("onsite") || constraintsText.includes("on-site")) &&
    candidate.workMode === "remote"
  ) {
    return false;
  }

  if (
    candidate.country &&
    constraintsText.includes("location") &&
    !constraintsText.includes(candidate.country.toLowerCase())
  ) {
    return false;
  }

  const budget = extractBudgetFromConstraintText(constraintsText);
  if (
    budget &&
    candidate.salaryAmount !== null &&
    candidate.salaryCurrency !== null &&
    candidate.salaryPeriod !== null &&
    candidate.salaryCurrency === budget.currency &&
    candidate.salaryPeriod === budget.period &&
    candidate.salaryAmount > budget.amount * 1.2
  ) {
    return false;
  }

  return true;
}

function passesJobMandatoryFilters(
  jobMandatory: {
    workFormat: "remote" | "hybrid" | "onsite" | null;
    remoteCountries: string[];
    remoteWorldwide: boolean;
    budgetMin: number | null;
    budgetMax: number | null;
    budgetCurrency: "USD" | "EUR" | "ILS" | "GBP" | "other" | null;
    budgetPeriod: "month" | "year" | null;
  },
  candidate: {
    country: string;
    workMode: "remote" | "hybrid" | "onsite" | "flexible" | null;
    salaryAmount: number | null;
    salaryCurrency: "USD" | "EUR" | "ILS" | "GBP" | "other" | null;
    salaryPeriod: "month" | "year" | null;
  },
): boolean {
  if (jobMandatory.workFormat === "onsite" && candidate.workMode === "remote") {
    return false;
  }
  if (jobMandatory.workFormat === "hybrid" && candidate.workMode === "remote") {
    return false;
  }
  if (jobMandatory.workFormat === "remote") {
    if (!jobMandatory.remoteWorldwide && jobMandatory.remoteCountries.length > 0) {
      if (!candidate.country.trim()) {
        return false;
      }
      const candidateCountry = candidate.country.trim().toLowerCase();
      const allowed = jobMandatory.remoteCountries.some(
        (country) => country.trim().toLowerCase() === candidateCountry,
      );
      if (!allowed) {
        return false;
      }
    }
  }

  if (
    typeof jobMandatory.budgetMax === "number" &&
    candidate.salaryAmount !== null &&
    candidate.salaryCurrency &&
    candidate.salaryPeriod &&
    jobMandatory.budgetCurrency &&
    jobMandatory.budgetPeriod &&
    candidate.salaryCurrency === jobMandatory.budgetCurrency &&
    candidate.salaryPeriod === jobMandatory.budgetPeriod &&
    candidate.salaryAmount > jobMandatory.budgetMax
  ) {
    return false;
  }

  return true;
}

function extractBudgetFromConstraintText(text: string): {
  amount: number;
  currency: "USD" | "EUR" | "ILS" | "GBP" | "other";
  period: "month" | "year";
} | null {
  const match = text.match(/(\d+(?:[.,]\d+)?)(\s*[k])?\s*(usd|eur|ils|gbp|other)?/i);
  if (!match) {
    return null;
  }

  const base = Number((match[1] ?? "").replace(",", "."));
  if (!Number.isFinite(base) || base <= 0) {
    return null;
  }
  const amount = match[2] ? Math.round(base * 1000) : Math.round(base);

  const currencyRaw = (match[3] ?? "USD").toUpperCase();
  const currency =
    currencyRaw === "USD" ||
    currencyRaw === "EUR" ||
    currencyRaw === "ILS" ||
    currencyRaw === "GBP" ||
    currencyRaw === "OTHER"
      ? (currencyRaw === "OTHER" ? "other" : currencyRaw)
      : "USD";

  const period: "month" | "year" = /\byear|annual/.test(text) ? "year" : "month";

  return {
    amount,
    currency,
    period,
  };
}
