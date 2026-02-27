import { TelegramClient } from "../telegram/telegram.client";
import { buildCandidateDecisionKeyboard } from "../telegram/ui/keyboards";
import {
  candidateOpportunityMessage,
  candidateManagerRejectedMessage,
  contactsSharedToCandidateMessage,
} from "../telegram/ui/messages";

export class CandidateNotifier {
  constructor(private readonly telegramClient: TelegramClient) {}

  async notifyOpportunity(params: {
    chatId: number;
    matchId: string;
    score: number;
    jobSummary: string;
    explanationMessage: string;
    jobTechnicalSummary?: {
      headline: string;
      product_context: string;
      core_tech: string[];
    } | null;
  }): Promise<void> {
    await this.telegramClient.sendMessage(
      params.chatId,
      candidateOpportunityMessage({
        score: params.score,
        jobSummary: params.jobSummary,
        explanationMessage: params.explanationMessage,
        jobTechnicalSummary: params.jobTechnicalSummary ?? null,
      }),
      { replyMarkup: buildCandidateDecisionKeyboard(params.matchId) },
    );
  }

  async notifyManagerRejected(chatId: number): Promise<void> {
    await this.telegramClient.sendMessage(chatId, candidateManagerRejectedMessage());
  }

  async notifyContactsShared(chatId: number, managerContact: string): Promise<void> {
    await this.telegramClient.sendMessage(chatId, contactsSharedToCandidateMessage(managerContact));
  }
}
