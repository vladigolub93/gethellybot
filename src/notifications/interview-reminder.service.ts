import { Logger } from "../config/logger";
import { StatesRepository } from "../db/repositories/states.repo";
import { UserSessionState } from "../shared/types/state.types";
import { TelegramClient } from "../telegram/telegram.client";

const THREE_DAYS_MS = 3 * 24 * 60 * 60 * 1000;
const CANDIDATE_INCOMPLETE_STATES: UserSessionState["state"][] = [
  "waiting_resume",
  "extracting_resume",
  "interviewing_candidate",
  "candidate_mandatory_fields",
];
const MANAGER_INCOMPLETE_STATES: UserSessionState["state"][] = [
  "waiting_job",
  "extracting_job",
  "interviewing_manager",
  "manager_mandatory_fields",
];

export class InterviewReminderService {
  constructor(
    private readonly statesRepository: StatesRepository,
    private readonly telegramClient: TelegramClient,
    private readonly logger: Logger,
  ) {}

  isEnabled(): boolean {
    return this.statesRepository.isEnabled();
  }

  async sendDueReminders(): Promise<void> {
    if (!this.isEnabled()) {
      return;
    }

    const rows = await this.statesRepository.listAllSessions();
    const now = Date.now();
    const nowIso = new Date(now).toISOString();
    let sent = 0;
    let scanned = 0;

    for (const item of rows) {
      const session = item.session;
      if (!isIncompleteInterviewState(session.state)) {
        continue;
      }
      scanned += 1;
      if (!isReminderDue(session, item.updatedAt, now)) {
        continue;
      }

      const text = buildReminderMessage(session);
      try {
        await this.telegramClient.sendUserMessage({
          source: "interview_reminder_service.push",
          chatId: session.chatId,
          text,
        });
        session.lastIncompleteInterviewReminderAt = nowIso;
        await this.statesRepository.saveSession(session);
        sent += 1;
      } catch (error) {
        this.logger.warn("interview.reminder.send_failed", {
          telegramUserId: session.userId,
          chatId: session.chatId,
          state: session.state,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    this.logger.info("interview.reminder.run", {
      scanned,
      sent,
    });
  }
}

function isIncompleteInterviewState(state: UserSessionState["state"]): boolean {
  return CANDIDATE_INCOMPLETE_STATES.includes(state) || MANAGER_INCOMPLETE_STATES.includes(state);
}

function isReminderDue(
  session: UserSessionState,
  updatedAt: string,
  now: number,
): boolean {
  const lastReminder = parseTime(session.lastIncompleteInterviewReminderAt);
  if (lastReminder > 0) {
    return now - lastReminder >= THREE_DAYS_MS;
  }

  const lastStateUpdate = parseTime(updatedAt);
  if (lastStateUpdate <= 0) {
    return false;
  }
  return now - lastStateUpdate >= THREE_DAYS_MS;
}

function parseTime(value?: string): number {
  if (!value) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function buildReminderMessage(session: UserSessionState): string {
  const candidateFlow = CANDIDATE_INCOMPLETE_STATES.includes(session.state);
  const preferredLanguage = session.preferredLanguage ?? "en";

  if (preferredLanguage === "ru") {
    return candidateFlow
      ? "Напоминание, интервью кандидата еще не завершено. Вернитесь к диалогу, и я продолжу с того места, где вы остановились."
      : "Напоминание, интервью по вакансии еще не завершено. Вернитесь к диалогу, и я продолжу с того места, где вы остановились.";
  }

  if (preferredLanguage === "uk") {
    return candidateFlow
      ? "Нагадування, інтерв'ю кандидата ще не завершене. Поверніться в діалог, і я продовжу з місця, де ви зупинились."
      : "Нагадування, інтерв'ю по вакансії ще не завершене. Поверніться в діалог, і я продовжу з місця, де ви зупинились.";
  }

  return candidateFlow
    ? "Quick reminder, your candidate interview is not finished yet. Return to the chat, and I will continue from where you stopped."
    : "Quick reminder, your hiring interview is not finished yet. Return to the chat, and I will continue from where you stopped.";
}

