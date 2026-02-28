import { Logger } from "../config/logger";
import { DataDeletionRepository } from "../db/repositories/data-deletion.repo";
import { UsersRepository } from "../db/repositories/users.repo";

export interface DataDeletionResult {
  requested: boolean;
  confirmationMessage: string;
}

export class DataDeletionService {
  constructor(
    private readonly repository: DataDeletionRepository,
    private readonly usersRepository: UsersRepository,
    private readonly logger: Logger,
  ) {}

  async requestDeletion(input: {
    telegramUserId: number;
    telegramUsername?: string;
    reason?: string;
  }): Promise<DataDeletionResult> {
    try {
      await this.repository.markRequested(input);
      await this.repository.purgeUserData(input.telegramUserId);
      this.logger.info("privacy.contact_data_cleared", {
        telegramUserId: input.telegramUserId,
      });
      return {
        requested: true,
        confirmationMessage:
          "Your data was deleted. I reset your session and you can start again.",
      };
    } catch (error) {
      this.logger.warn("Failed to persist data deletion request", {
        telegramUserId: input.telegramUserId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      try {
        await this.usersRepository.clearSensitivePersonalData(input.telegramUserId);
      } catch {
        // Keep fallback silent, original failure is already logged.
      }
      return {
        requested: false,
        confirmationMessage:
          "I could not fully delete your data right now. I removed sensitive fields and reset your session.",
      };
    }
  }
}
