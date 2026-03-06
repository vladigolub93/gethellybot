import { MatchRecord } from "./match.types";
import { MatchStorageService } from "../storage/match-storage.service";
import { JobsRepository } from "../db/repositories/jobs.repo";
import { Logger } from "../config/logger";
import { normalizeLegacyMatchStatus } from "../core/matching/lifecycle-normalizers";
import { MatchLifecycleService } from "../core/matching/match-lifecycle.service";
import { MATCH_STATUSES, MatchStatus } from "../core/matching/match-statuses";

export class DecisionService {
  constructor(
    private readonly matchStorageService: MatchStorageService,
    private readonly jobsRepository: JobsRepository,
    private readonly logger?: Logger,
    private readonly matchLifecycleService: MatchLifecycleService = new MatchLifecycleService(),
  ) {}

  async getMatch(matchId: string): Promise<MatchRecord | null> {
    return this.matchStorageService.getById(matchId);
  }

  async candidateApply(
    matchId: string,
    candidateUserId: number,
  ): Promise<MatchRecord> {
    const match = await this.requireMatchForCandidate(matchId, candidateUserId);
    await this.ensureCandidateCanActOnMatch(match);
    await this.ensureJobActive(match);
    if (match.candidateDecision !== "pending") {
      return match;
    }

    const canonicalNext = this.tryLogCandidateLifecycleTransition("candidate_accept", match);

    const updated = await this.matchStorageService.applyCandidateDecision(matchId, "applied", {
      canonicalMatchStatus: canonicalNext ?? undefined,
    });
    if (!updated) {
      throw new Error("Failed to save candidate decision.");
    }

    return updated;
  }

  async candidateReject(
    matchId: string,
    candidateUserId: number,
  ): Promise<MatchRecord> {
    const match = await this.requireMatchForCandidate(matchId, candidateUserId);
    await this.ensureCandidateCanActOnMatch(match);
    if (match.candidateDecision !== "pending") {
      return match;
    }

    const canonicalNext = this.tryLogCandidateLifecycleTransition("candidate_decline", match);

    const updated = await this.matchStorageService.applyCandidateDecision(matchId, "rejected", {
      canonicalMatchStatus: canonicalNext ?? undefined,
    });
    if (!updated) {
      throw new Error("Failed to save candidate decision.");
    }
    return updated;
  }

  async managerAccept(
    matchId: string,
    managerUserId: number,
  ): Promise<MatchRecord> {
    const match = await this.requireMatchForManager(matchId, managerUserId);
    await this.ensureManagerCanActOnMatch(match);
    await this.ensureJobActive(match);
    if (match.managerDecision !== "pending") {
      return match;
    }
    if (match.candidateDecision !== "applied") {
      throw new Error("Candidate has not applied for this match.");
    }

    const canonicalNext = this.tryLogManagerLifecycleTransition("manager_approve", match);

    const updated = await this.matchStorageService.applyManagerDecision(matchId, "accepted", {
      canonicalMatchStatus: canonicalNext ?? undefined,
    });
    if (!updated) {
      throw new Error("Failed to save manager decision.");
    }
    return updated;
  }

  async managerReject(
    matchId: string,
    managerUserId: number,
  ): Promise<MatchRecord> {
    const match = await this.requireMatchForManager(matchId, managerUserId);
    await this.ensureManagerCanActOnMatch(match);
    if (match.managerDecision !== "pending") {
      return match;
    }

    const canonicalNext = this.tryLogManagerLifecycleTransition("manager_reject", match);

    const updated = await this.matchStorageService.applyManagerDecision(matchId, "rejected", {
      canonicalMatchStatus: canonicalNext ?? undefined,
    });
    if (!updated) {
      throw new Error("Failed to save manager decision.");
    }
    return updated;
  }

  async markContactShared(
    matchId: string,
    managerUserId: number,
  ): Promise<MatchRecord> {
    const match = await this.requireMatchForManager(matchId, managerUserId);
    if (match.managerDecision !== "accepted") {
      throw new Error("Manager has not accepted this match yet.");
    }
    if (match.status === "contact_shared") {
      return match;
    }

    const updated = await this.matchStorageService.markContactShared(matchId);
    if (!updated) {
      throw new Error("Failed to mark contact exchange.");
    }
    return updated;
  }

  private async requireMatchForCandidate(
    matchId: string,
    candidateUserId: number,
  ): Promise<MatchRecord> {
    const match = await this.matchStorageService.getById(matchId);
    if (!match) {
      throw new Error("Match not found.");
    }
    if (match.candidateUserId !== candidateUserId) {
      throw new Error("This action is not available for you.");
    }
    return match;
  }

  private async requireMatchForManager(
    matchId: string,
    managerUserId: number,
  ): Promise<MatchRecord> {
    const match = await this.matchStorageService.getById(matchId);
    if (!match) {
      throw new Error("Match not found.");
    }
    if (match.managerUserId !== managerUserId) {
      throw new Error("This action is not available for you.");
    }
    return match;
  }

  private async ensureJobActive(match: MatchRecord): Promise<void> {
    const status = await this.jobsRepository.getManagerJobStatus(match.managerUserId);
    if (status && status !== "active") {
      throw new Error("This job is no longer active.");
    }
  }

  private async ensureCandidateCanActOnMatch(match: MatchRecord): Promise<void> {
    if (match.status !== "proposed") {
      throw new Error("This match is no longer available for this action.");
    }
  }

  private async ensureManagerCanActOnMatch(match: MatchRecord): Promise<void> {
    if (match.status !== "candidate_applied") {
      throw new Error("Candidate has not applied for this match, or it is no longer available.");
    }
  }

  private tryLogCandidateLifecycleTransition(
    action: "candidate_accept" | "candidate_decline",
    match: MatchRecord,
  ): MatchStatus | null {
    try {
      const normalizedCurrent = normalizeLegacyMatchStatus({
        status: match.status,
        candidateDecision: match.candidateDecision,
        managerDecision: match.managerDecision,
        contactShared: match.status === "contact_shared",
      });
      const transitionFrom = this.resolveCandidateDecisionEntryStatus(normalizedCurrent);
      if (!transitionFrom) {
        throw new Error("Canonical current status is unknown.");
      }

      const next =
        action === "candidate_accept"
          ? this.matchLifecycleService.candidateAcceptsMatch(transitionFrom)
          : this.matchLifecycleService.candidateDeclinesMatch(transitionFrom);

      const logName =
        action === "candidate_accept"
          ? "match_lifecycle.candidate_accept.transition"
          : "match_lifecycle.candidate_decline.transition";

      this.logger?.debug(logName, {
        matchId: match.id,
        candidateUserId: match.candidateUserId,
        legacyStatus: match.status,
        canonicalFrom: transitionFrom,
        canonicalTo: next,
      });
      return next;
    } catch (error) {
      this.logger?.warn("match_lifecycle.transition_failed", {
        action,
        matchId: match.id,
        candidateUserId: match.candidateUserId,
        legacyStatus: match.status,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return null;
    }
  }

  private resolveCandidateDecisionEntryStatus(
    normalizedCurrent: MatchStatus | null,
  ): MatchStatus | null {
    if (normalizedCurrent === MATCH_STATUSES.PROPOSED) {
      // In current legacy flow, actionable candidate decisions happen on `proposed`.
      // Canonically this is closest to an invitation already visible to candidate.
      return MATCH_STATUSES.INVITED;
    }
    return normalizedCurrent;
  }

  private tryLogManagerLifecycleTransition(
    action: "manager_approve" | "manager_reject",
    match: MatchRecord,
  ): MatchStatus | null {
    try {
      const transitionFrom = normalizeLegacyMatchStatus({
        status: match.status,
        candidateDecision: match.candidateDecision,
        managerDecision: match.managerDecision,
        contactShared: match.status === "contact_shared",
      });
      if (!transitionFrom) {
        throw new Error("Canonical current status is unknown.");
      }

      const next =
        action === "manager_approve"
          ? this.matchLifecycleService.managerApprovesCandidate(transitionFrom)
          : this.matchLifecycleService.managerRejectsCandidate(transitionFrom);

      const logName =
        action === "manager_approve"
          ? "match_lifecycle.manager_approve.transition"
          : "match_lifecycle.manager_reject.transition";

      this.logger?.debug(logName, {
        matchId: match.id,
        managerUserId: match.managerUserId,
        legacyStatus: match.status,
        canonicalFrom: transitionFrom,
        canonicalTo: next,
      });
      return next;
    } catch (error) {
      this.logger?.warn("match_lifecycle.transition_failed", {
        action,
        matchId: match.id,
        managerUserId: match.managerUserId,
        legacyStatus: match.status,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return null;
    }
  }

}
