import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { Logger } from "../config/logger";
import { MatchCandidateInput, MatchRecord } from "../decisions/match.types";
import { MatchesRepository } from "../db/repositories/matches.repo";

const STORAGE_DIR = path.resolve(process.cwd(), "data", "matches");
const STORAGE_FILE = path.join(STORAGE_DIR, "matches.json");

interface MatchDecisionUpdate {
  candidateDecision?: MatchRecord["candidateDecision"];
  managerDecision?: MatchRecord["managerDecision"];
  status?: MatchRecord["status"];
}

export class MatchStorageService {
  constructor(
    private readonly logger?: Logger,
    private readonly matchesRepository?: MatchesRepository,
  ) {}

  async createForJob(
    managerUserId: number,
    jobSummary: string,
    candidates: ReadonlyArray<MatchCandidateInput>,
  ): Promise<MatchRecord[]> {
    const items = await this.readAll();
    const createdAt = new Date().toISOString();

    const created = candidates.map((candidate, index) => ({
      id: buildMatchId(managerUserId, candidate.candidateUserId, createdAt, index),
      managerUserId,
      candidateUserId: candidate.candidateUserId,
      jobId: candidate.jobId ?? null,
      candidateId: candidate.candidateId ?? null,
      jobSummary,
      jobTechnicalSummary: candidate.jobTechnicalSummary ?? null,
      candidateSummary: candidate.candidateSummary,
      candidateTechnicalSummary: candidate.candidateTechnicalSummary ?? null,
      score: candidate.score,
      breakdown: candidate.breakdown,
      reasons: candidate.reasons,
      explanationJson: candidate.explanationJson ?? null,
      matchingDecision: candidate.matchingDecision ?? null,
      explanation: candidate.explanation,
      candidateDecision: "pending" as const,
      managerDecision: "pending" as const,
      status: "suggested" as const,
      createdAt,
      updatedAt: createdAt,
    }));

    items.push(...created);
    await this.writeAll(items);
    await this.syncMany(created);
    return created;
  }

  async getById(matchId: string): Promise<MatchRecord | null> {
    const items = await this.readAll();
    return items.find((item) => item.id === matchId) ?? null;
  }

  async listAll(): Promise<MatchRecord[]> {
    return this.readAll();
  }

  async applyCandidateDecision(
    matchId: string,
    decision: "applied" | "rejected",
  ): Promise<MatchRecord | null> {
    if (decision === "applied") {
      return this.updateDecision(matchId, {
        candidateDecision: "applied",
        status: "manager_pending",
      });
    }

    return this.updateDecision(matchId, {
      candidateDecision: "rejected",
      status: "closed",
    });
  }

  async applyManagerDecision(
    matchId: string,
    decision: "accepted" | "rejected",
  ): Promise<MatchRecord | null> {
    if (decision === "accepted") {
      return this.updateDecision(matchId, {
        managerDecision: "accepted",
        status: "manager_accepted",
      });
    }

    return this.updateDecision(matchId, {
      managerDecision: "rejected",
      status: "closed",
    });
  }

  async markContactShared(matchId: string): Promise<MatchRecord | null> {
    return this.updateDecision(matchId, {
      status: "contact_shared",
    });
  }

  private async updateDecision(
    matchId: string,
    update: MatchDecisionUpdate,
  ): Promise<MatchRecord | null> {
    const items = await this.readAll();
    const index = items.findIndex((item) => item.id === matchId);
    if (index < 0) {
      return null;
    }

    const existing = items[index];
    const updated: MatchRecord = {
      ...existing,
      ...update,
      updatedAt: new Date().toISOString(),
    };
    items[index] = updated;
    await this.writeAll(items);
    await this.syncOne(updated);
    return updated;
  }

  private async readAll(): Promise<MatchRecord[]> {
    await mkdir(STORAGE_DIR, { recursive: true });
    try {
      const raw = await readFile(STORAGE_FILE, "utf-8");
      const parsed = JSON.parse(raw) as MatchRecord[];
      if (!Array.isArray(parsed)) {
        return [];
      }
      return parsed;
    } catch {
      return [];
    }
  }

  private async writeAll(items: MatchRecord[]): Promise<void> {
    await mkdir(STORAGE_DIR, { recursive: true });
    await writeFile(STORAGE_FILE, JSON.stringify(items, null, 2), "utf-8");
  }

  private async syncMany(matches: ReadonlyArray<MatchRecord>): Promise<void> {
    for (const match of matches) {
      await this.syncOne(match);
    }
  }

  private async syncOne(match: MatchRecord): Promise<void> {
    if (!this.matchesRepository) {
      return;
    }
    try {
      await this.matchesRepository.upsertMatch(match);
    } catch (error) {
      this.logger?.warn("Failed to mirror match record to Supabase", {
        matchId: match.id,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }
}

function buildMatchId(
  managerUserId: number,
  candidateUserId: number,
  timestamp: string,
  index: number,
): string {
  const cleanedTime = timestamp.replace(/[:.]/g, "-");
  return `m_${managerUserId}_${candidateUserId}_${cleanedTime}_${index}`;
}
