import {
  CALLBACK_CANDIDATE_APPLY_PREFIX,
  CALLBACK_CANDIDATE_ASK_PREFIX,
  CALLBACK_CANDIDATE_REJECT_PREFIX,
  CALLBACK_MANAGER_ACCEPT_PREFIX,
  CALLBACK_MANAGER_ASK_PREFIX,
  CALLBACK_MANAGER_REJECT_PREFIX,
  CALLBACK_MANAGER_WORK_FORMAT_HYBRID,
  CALLBACK_MANAGER_WORK_FORMAT_ONSITE,
  CALLBACK_MANAGER_WORK_FORMAT_REMOTE,
  CALLBACK_ROLE_BACK,
  CALLBACK_ROLE_CANDIDATE,
  CALLBACK_ROLE_LEARN_MORE,
  CALLBACK_ROLE_MANAGER,
} from "../../shared/constants";
import { TelegramReplyMarkup } from "../../shared/types/telegram.types";

export function buildRoleSelectionKeyboard(): TelegramReplyMarkup {
  return {
    inline_keyboard: [
      [
        { text: "I am a Candidate", callback_data: CALLBACK_ROLE_CANDIDATE },
        { text: "I am Hiring", callback_data: CALLBACK_ROLE_MANAGER },
      ],
      [{ text: "Learn how this works", callback_data: CALLBACK_ROLE_LEARN_MORE }],
    ],
  };
}

export function buildRoleLearnMoreKeyboard(): TelegramReplyMarkup {
  return {
    inline_keyboard: [[{ text: "Back", callback_data: CALLBACK_ROLE_BACK }]],
  };
}

export function buildCandidateDecisionKeyboard(matchId: string): TelegramReplyMarkup {
  return {
    inline_keyboard: [
      [
        { text: "Apply", callback_data: `${CALLBACK_CANDIDATE_APPLY_PREFIX}${matchId}` },
        { text: "Reject", callback_data: `${CALLBACK_CANDIDATE_REJECT_PREFIX}${matchId}` },
        { text: "Ask question", callback_data: `${CALLBACK_CANDIDATE_ASK_PREFIX}${matchId}` },
      ],
    ],
  };
}

export function buildManagerDecisionKeyboard(matchId: string): TelegramReplyMarkup {
  return {
    inline_keyboard: [
      [
        { text: "Want to talk", callback_data: `${CALLBACK_MANAGER_ACCEPT_PREFIX}${matchId}` },
        { text: "Skip", callback_data: `${CALLBACK_MANAGER_REJECT_PREFIX}${matchId}` },
        { text: "Ask question", callback_data: `${CALLBACK_MANAGER_ASK_PREFIX}${matchId}` },
      ],
    ],
  };
}

export function buildContactRequestKeyboard(): TelegramReplyMarkup {
  return {
    keyboard: [
      [{ text: "Share my contact", request_contact: true }],
      [{ text: "Skip for now" }],
    ],
    resize_keyboard: true,
    one_time_keyboard: false,
  };
}

export function buildRemoveReplyKeyboard(): TelegramReplyMarkup {
  return {
    remove_keyboard: true,
  };
}

export function buildCandidateMandatoryLocationKeyboard(): TelegramReplyMarkup {
  return {
    keyboard: [
      [{ text: "Share location", request_location: true }],
      [{ text: "Type country and city" }],
    ],
    resize_keyboard: true,
    one_time_keyboard: false,
  };
}

export function buildCandidateWorkModeKeyboard(): TelegramReplyMarkup {
  return {
    keyboard: [
      [{ text: "remote" }, { text: "hybrid" }],
      [{ text: "onsite" }, { text: "flexible" }],
    ],
    resize_keyboard: true,
    one_time_keyboard: false,
  };
}

export function buildManagerWorkFormatKeyboard(): TelegramReplyMarkup {
  return {
    inline_keyboard: [[
      { text: "Remote", callback_data: CALLBACK_MANAGER_WORK_FORMAT_REMOTE },
      { text: "Hybrid", callback_data: CALLBACK_MANAGER_WORK_FORMAT_HYBRID },
      { text: "Onsite", callback_data: CALLBACK_MANAGER_WORK_FORMAT_ONSITE },
    ]],
  };
}

export function buildCandidateMatchingActionsKeyboard(): TelegramReplyMarkup {
  return {
    keyboard: [
      [{ text: "Find roles" }, { text: "Show matches" }],
      [{ text: "Pause matching" }, { text: "Resume matching" }],
    ],
    resize_keyboard: true,
    one_time_keyboard: false,
  };
}

export function buildManagerMatchingActionsKeyboard(): TelegramReplyMarkup {
  return {
    keyboard: [
      [{ text: "Find candidates" }, { text: "Show matches" }],
      [{ text: "Pause matching" }, { text: "Resume matching" }],
    ],
    resize_keyboard: true,
    one_time_keyboard: false,
  };
}
