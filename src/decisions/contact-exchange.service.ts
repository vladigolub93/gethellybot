import { Logger } from "../config/logger";
import { UsersRepository } from "../db/repositories/users.repo";
import { MatchRecord } from "./match.types";
import { StateService } from "../state/state.service";
import { TelegramClient } from "../telegram/telegram.client";
import { buildContactRequestKeyboard } from "../telegram/ui/keyboards";
import {
  candidateContactRequiredForExchangeMessage,
  managerContactRequiredForExchangeMessage,
} from "../telegram/ui/messages";

type UserContact = Awaited<ReturnType<UsersRepository["getContact"]>>;

interface ContactExchangeReadyResult {
  ready: true;
  managerContact: string;
  candidateContact: string;
}

interface ContactExchangeBlockedResult {
  ready: false;
}

export type ContactExchangeResult = ContactExchangeReadyResult | ContactExchangeBlockedResult;

export class ContactExchangeService {
  constructor(
    private readonly stateService: StateService,
    private readonly usersRepository: UsersRepository,
    private readonly telegramClient: TelegramClient,
    private readonly logger: Logger,
  ) {}

  async prepareExchange(match: MatchRecord): Promise<ContactExchangeResult> {
    const managerContact = await this.usersRepository.getContact(match.managerUserId);
    const candidateContact = await this.usersRepository.getContact(match.candidateUserId);

    const managerMissing = !hasShareableContact(managerContact);
    const candidateMissing = !hasShareableContact(candidateContact);

    if (candidateMissing) {
      await this.promptCandidateForContact(match.candidateUserId);
    }
    if (managerMissing) {
      await this.promptManagerForContact(match.managerUserId);
    }

    if (managerMissing || candidateMissing) {
      this.logger.info("Contact exchange blocked until both contacts are shared", {
        managerUserId: match.managerUserId,
        candidateUserId: match.candidateUserId,
        managerMissing,
        candidateMissing,
      });
      return { ready: false };
    }

    return {
      ready: true,
      managerContact: formatContactDetails(managerContact),
      candidateContact: formatContactDetails(candidateContact),
    };
  }

  private async promptCandidateForContact(candidateUserId: number): Promise<void> {
    const session = this.stateService.getSession(candidateUserId);
    if (!session) {
      return;
    }
    await this.telegramClient.sendMessage(
      session.chatId,
      candidateContactRequiredForExchangeMessage(),
      { replyMarkup: buildContactRequestKeyboard() },
    );
  }

  private async promptManagerForContact(managerUserId: number): Promise<void> {
    const session = this.stateService.getSession(managerUserId);
    if (!session) {
      return;
    }
    await this.telegramClient.sendMessage(
      session.chatId,
      managerContactRequiredForExchangeMessage(),
      { replyMarkup: buildContactRequestKeyboard() },
    );
  }
}

function hasShareableContact(contact: UserContact): contact is NonNullable<UserContact> {
  return Boolean(
    contact &&
      contact.contactShared &&
      contact.firstName &&
      contact.firstName.trim() &&
      contact.phoneNumber &&
      contact.phoneNumber.trim(),
  );
}

function formatContactDetails(
  contact: NonNullable<UserContact>,
): string {
  const name = [contact.firstName ?? "", contact.lastName ?? ""]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(" ")
    .trim();
  const username = contact.telegramUsername ? `@${contact.telegramUsername}` : "not set";
  const phone = contact.phoneNumber ?? "not set";

  return [
    `Name: ${name || "not set"}`,
    `Telegram: ${username}`,
    `Phone: ${phone}`,
  ].join("\n");
}
