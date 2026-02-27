import { MatchRecord } from "./match.types";
import { MatchStorageService } from "../storage/match-storage.service";
import { JobsRepository } from "../db/repositories/jobs.repo";

export class DecisionService {
  constructor(
    private readonly matchStorageService: MatchStorageService,
    private readonly jobsRepository: JobsRepository,
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

    const updated = await this.matchStorageService.applyCandidateDecision(matchId, "applied");
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

    const updated = await this.matchStorageService.applyCandidateDecision(matchId, "rejected");
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

    const updated = await this.matchStorageService.applyManagerDecision(matchId, "accepted");
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

    const updated = await this.matchStorageService.applyManagerDecision(matchId, "rejected");
    if (!updated) {
      throw new Error("Failed to save manager decision.");
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
    if (match.status === "closed" || match.status === "contact_shared") {
      throw new Error("This match is already closed.");
    }
  }

  private async ensureManagerCanActOnMatch(match: MatchRecord): Promise<void> {
    if (match.status === "closed" || match.status === "contact_shared") {
      throw new Error("This match is already closed.");
    }
    if (match.candidateDecision !== "applied") {
      throw new Error("Candidate has not applied for this match.");
    }
  }
}
