import { Logger } from "../config/logger";
import { JobsRepository } from "../db/repositories/jobs.repo";
import { UsersRepository } from "../db/repositories/users.repo";
import { MatchRecord } from "../decisions/match.types";
import { StateService } from "../state/state.service";
import { StatePersistenceService } from "../state/state-persistence.service";
import { TelegramClient } from "../telegram/telegram.client";
import {
  firstManagerMatchExplanationMessage,
  firstMatchExplanationMessage,
} from "../telegram/ui/messages";
import { CandidateNotifier } from "./candidate-notifier";
import { ManagerNotifier } from "./manager-notifier";
import { RateLimitService } from "./rate-limit.service";

export class NotificationEngine {
  constructor(
    private readonly stateService: StateService,
    private readonly statePersistenceService: StatePersistenceService,
    private readonly telegramClient: TelegramClient,
    private readonly candidateNotifier: CandidateNotifier,
    private readonly managerNotifier: ManagerNotifier,
    private readonly rateLimitService: RateLimitService,
    private readonly jobsRepository: JobsRepository,
    private readonly usersRepository: UsersRepository,
    private readonly logger: Logger,
  ) {}

  async notifyCandidateOpportunity(match: MatchRecord): Promise<void> {
    if (match.matchingDecision && !match.matchingDecision.notify_candidate) {
      this.logger.info("Candidate notification suppressed by matching decision", {
        candidateUserId: match.candidateUserId,
        matchId: match.id,
        reason: match.matchingDecision.reason,
      });
      return;
    }

    const candidateSession = this.stateService.getSession(match.candidateUserId);
    if (!candidateSession) {
      this.logger.warn("Candidate session not found, skipping opportunity notification", {
        candidateUserId: match.candidateUserId,
      });
      return;
    }

    const candidateCooldownHours = match.matchingDecision?.cooldown_hours_candidate ?? 12;
    const limit = await this.rateLimitService.checkAndConsumeCandidateNotification(
      match.candidateUserId,
      candidateCooldownHours,
    );
    if (!limit.allowed) {
      this.logger.info("Candidate notification blocked by rate limit", {
        candidateUserId: match.candidateUserId,
        matchId: match.id,
        reason: limit.reason ?? "unknown",
      });
      return;
    }

    const userFlags = await this.usersRepository.getUserFlags(match.candidateUserId);
    const firstMatchAlreadyExplained =
      Boolean(candidateSession.firstMatchExplained) || userFlags.firstMatchExplained;
    if (!firstMatchAlreadyExplained) {
      await this.telegramClient.sendMessage(candidateSession.chatId, firstMatchExplanationMessage());
      await this.usersRepository.markFirstMatchExplained(match.candidateUserId, true);
      this.stateService.setFirstMatchExplained(match.candidateUserId, true);
    }

    await this.safeTransition(match.candidateUserId, "waiting_candidate_decision");
    await this.candidateNotifier.notifyOpportunity({
      chatId: candidateSession.chatId,
      matchId: match.id,
      score: match.score,
      jobSummary: match.jobSummary,
      explanationMessage:
        match.explanationJson?.message_for_candidate ?? match.explanation,
      jobTechnicalSummary: match.jobTechnicalSummary ?? null,
    });
  }

  async notifyManagerCandidateApplied(match: MatchRecord): Promise<void> {
    const jobStatus = await this.jobsRepository.getManagerJobStatus(match.managerUserId);
    if (jobStatus !== "active") {
      this.logger.info("Manager notification skipped because job is not active", {
        managerUserId: match.managerUserId,
        matchId: match.id,
        jobStatus: jobStatus ?? "unknown",
      });
      return;
    }

    const managerSession = this.stateService.getSession(match.managerUserId);
    if (!managerSession) {
      this.logger.warn("Manager session not found, skipping candidate application notification", {
        managerUserId: match.managerUserId,
      });
      return;
    }

    const managerCooldownHours = match.matchingDecision?.cooldown_hours_manager ?? 6;
    const limit = await this.rateLimitService.checkAndConsumeManagerNotification(
      match.managerUserId,
      managerCooldownHours,
    );
    if (!limit.allowed) {
      this.logger.info("Manager notification blocked by rate limit", {
        managerUserId: match.managerUserId,
        matchId: match.id,
        reason: limit.reason ?? "unknown",
      });
      return;
    }

    const userFlags = await this.usersRepository.getUserFlags(match.managerUserId);
    const firstMatchAlreadyExplained =
      Boolean(managerSession.firstMatchExplained) || userFlags.firstMatchExplained;
    if (!firstMatchAlreadyExplained) {
      await this.telegramClient.sendMessage(managerSession.chatId, firstManagerMatchExplanationMessage());
      await this.usersRepository.markFirstMatchExplained(match.managerUserId, true);
      this.stateService.setFirstMatchExplained(match.managerUserId, true);
    }

    await this.safeTransition(match.managerUserId, "waiting_manager_decision");
    await this.managerNotifier.notifyCandidateApplied({
      chatId: managerSession.chatId,
      matchId: match.id,
      candidateUserId: match.candidateUserId,
      score: match.score,
      candidateSummary: match.candidateSummary,
      candidateTechnicalSummary: match.candidateTechnicalSummary ?? null,
      explanationMessage:
        match.explanationJson?.message_for_manager ?? match.explanation,
    });
  }

  async notifyManagerRejected(match: MatchRecord): Promise<void> {
    const candidateSession = this.stateService.getSession(match.candidateUserId);
    if (!candidateSession) {
      return;
    }
    await this.safeTransition(match.candidateUserId, "candidate_profile_ready");
    await this.candidateNotifier.notifyManagerRejected(candidateSession.chatId);
  }

  async notifyContactsShared(match: MatchRecord, managerContact: string, candidateContact: string): Promise<void> {
    const candidateSession = this.stateService.getSession(match.candidateUserId);
    const managerSession = this.stateService.getSession(match.managerUserId);

    await this.safeTransition(match.managerUserId, "contact_shared");
    await this.safeTransition(match.candidateUserId, "contact_shared");

    if (candidateSession) {
      await this.candidateNotifier.notifyContactsShared(candidateSession.chatId, managerContact);
    }

    if (managerSession) {
      await this.managerNotifier.notifyContactsShared(managerSession.chatId, candidateContact);
    }
  }

  private async safeTransition(
    userId: number,
    state: "waiting_candidate_decision" | "waiting_manager_decision" | "candidate_profile_ready" | "contact_shared",
  ): Promise<void> {
    const session = this.stateService.getSession(userId);
    if (!session) {
      return;
    }
    if (session.state === state) {
      return;
    }
    try {
      this.stateService.transition(userId, state);
      const latest = this.stateService.getSession(userId);
      if (latest) {
        await this.statePersistenceService.persistSession(latest);
      }
    } catch {
      return;
    }
  }
}
