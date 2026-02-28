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
      await this.usersRepository.clearSensitivePersonalData(input.telegramUserId);
      this.logger.info("privacy.contact_data_cleared", {
        telegramUserId: input.telegramUserId,
      });
      return {
        requested: true,
        confirmationMessage:
          "Your data deletion request is registered. We will remove your data from Helly records.",
      };
    } catch (error) {
      this.logger.warn("Failed to persist data deletion request", {
        telegramUserId: input.telegramUserId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return {
        requested: false,
        confirmationMessage:
          "Your data deletion request is noted. We will process it as soon as storage is available.",
      };
    }
  }
}
