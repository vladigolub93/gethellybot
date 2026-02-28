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
    await this.telegramClient.sendUserMessage({
      source: "candidate_notifier.opportunity",
      chatId: params.chatId,
      text: candidateOpportunityMessage({
        score: params.score,
        jobSummary: params.jobSummary,
        explanationMessage: params.explanationMessage,
        jobTechnicalSummary: params.jobTechnicalSummary ?? null,
      }),
      replyMarkup: buildCandidateDecisionKeyboard(params.matchId),
    });
  }

  async notifyManagerRejected(chatId: number): Promise<void> {
    await this.telegramClient.sendUserMessage({
      source: "candidate_notifier.manager_rejected",
      chatId,
      text: candidateManagerRejectedMessage(),
    });
  }

  async notifyContactsShared(chatId: number, managerContact: string): Promise<void> {
    await this.telegramClient.sendUserMessage({
      source: "candidate_notifier.contacts_shared",
      chatId,
      text: contactsSharedToCandidateMessage(managerContact),
    });
  }
}
