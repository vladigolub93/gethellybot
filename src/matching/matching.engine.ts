import { EmbeddingsClient } from "../ai/embeddings.client";
import { LlmClient } from "../ai/llm.client";
import { Logger } from "../config/logger";
import { JobsRepository } from "../db/repositories/jobs.repo";
import { ProfilesRepository } from "../db/repositories/profiles.repo";
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
import { calculateMatchingScoreV2 } from "./scoring/matching-score.v2";
import { VectorSearchRepository } from "./vector-search.repo";
import { VectorSearchV2 } from "./vector-search.v2";

const SHORTLIST_TOP_N = 50;
const MAX_CANDIDATES_TO_SCORE = 200;
const TOP_K_RESULTS = 10;
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
    private readonly matchStorageService: MatchStorageService,
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
    private readonly qualityFlagsService?: QualityFlagsService,
  ) {
    this.vectorSearchV2 = new VectorSearchV2(
      this.embeddingsClient,
      this.profilesRepository,
      this.vectorSearchRepository,
      this.storage,
      this.logger,
    );
    this.explanationService = new MatchingExplanationService(this.llmClient);
    this.decisionService = new MatchingDecisionService(
      this.llmClient,
      this.logger,
      this.qualityFlagsService,
    );
  }

  async runForManager(managerUserId: number): Promise<MatchingRunResult | null> {
    const jobProfile = await this.jobsRepository.getJobProfileV2(managerUserId);
    if (!jobProfile) {
      return null;
    }
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
