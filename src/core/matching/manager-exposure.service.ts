import { Logger } from "../../config/logger";
import { normalizeLegacyMatchStatus } from "./lifecycle-normalizers";
import { MatchLifecycleService } from "./match-lifecycle.service";
import { MATCH_STATUSES, MatchStatus } from "./match-statuses";

export type ManagerExposureSource = "notification_push" | "match_card_pull";

export interface ManagerExposureInput {
  matchId: string;
  candidateUserId: number;
  managerUserId: number;
  legacyStatus: string;
  candidateDecision?: string | null;
  managerDecision?: string | null;
  contactShared?: boolean | null;
  source: ManagerExposureSource;
}

export interface ManagerExposureResult {
  canonicalObserved: MatchStatus | null;
  canonicalFrom: MatchStatus | null;
  canonicalTo: MatchStatus | null;
  partialCoverage: boolean;
}

/**
 * Read/write-safe seam for the moment a candidate becomes visible to a manager.
 *
 * Current scope is intentionally narrow:
 * - sidecar lifecycle computation
 * - telemetry only
 * - no behavior changes
 */
export class ManagerExposureService {
  constructor(
    private readonly logger?: Logger,
    private readonly matchLifecycleService: MatchLifecycleService = new MatchLifecycleService(),
  ) {}

  exposeCandidateToManager(input: ManagerExposureInput): ManagerExposureResult {
    const canonicalObserved = normalizeLegacyMatchStatus({
      status: input.legacyStatus,
      candidateDecision: input.candidateDecision,
      managerDecision: input.managerDecision,
      contactShared: input.contactShared ?? null,
    });

    let canonicalFrom: MatchStatus | null = null;
    let canonicalTo: MatchStatus | null = null;

    try {
      canonicalFrom = this.resolveSendToManagerEntryStatus(canonicalObserved);
      if (!canonicalFrom) {
        throw new Error("Canonical entry status for send-to-manager is unknown.");
      }

      canonicalTo = this.matchLifecycleService.sendToManager(canonicalFrom);
      this.logger?.debug("match_lifecycle.send_to_manager.transition", {
        matchId: input.matchId,
        candidateUserId: input.candidateUserId,
        managerUserId: input.managerUserId,
        legacyStatus: input.legacyStatus,
        canonicalObserved,
        canonicalFrom,
        canonicalTo,
        source: input.source,
      });
    } catch (error) {
      this.logger?.warn("match_lifecycle.transition_failed", {
        action: "send_to_manager",
        matchId: input.matchId,
        candidateUserId: input.candidateUserId,
        managerUserId: input.managerUserId,
        legacyStatus: input.legacyStatus,
        source: input.source,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    const partialCoverage = true;
    this.logger?.debug("manager_exposure.exposed", {
      matchId: input.matchId,
      candidateUserId: input.candidateUserId,
      managerUserId: input.managerUserId,
      source: input.source,
      canonicalObserved,
      canonicalFrom,
      canonicalTo,
      partialCoverage,
    });

    if (partialCoverage) {
      this.logger?.debug("manager_exposure.partial_coverage", {
        matchId: input.matchId,
        coveredSource: input.source,
        missingSource: "state_router.showTopMatchesWithActions",
      });
    }

    if (input.source === "match_card_pull") {
      this.logger?.debug("manager_exposure.pull_path_used", {
        matchId: input.matchId,
        candidateUserId: input.candidateUserId,
        managerUserId: input.managerUserId,
      });
    }

    return {
      canonicalObserved,
      canonicalFrom,
      canonicalTo,
      partialCoverage,
    };
  }

  private resolveSendToManagerEntryStatus(
    normalizedCurrent: MatchStatus | null,
  ): MatchStatus | null {
    if (normalizedCurrent === MATCH_STATUSES.INTERVIEW_COMPLETED) {
      return MATCH_STATUSES.INTERVIEW_COMPLETED;
    }
    if (normalizedCurrent === MATCH_STATUSES.SENT_TO_MANAGER) {
      // Legacy `candidate_applied` is already manager-review visible.
      // Canonically this corresponds to SEND_TO_MANAGER after interview completion.
      return MATCH_STATUSES.INTERVIEW_COMPLETED;
    }
    return null;
  }
}
