import {
  CALLBACK_CANDIDATE_APPLY_PREFIX,
  CALLBACK_CANDIDATE_ASK_PREFIX,
  CALLBACK_CANDIDATE_REJECT_PREFIX,
  CALLBACK_MANAGER_ACCEPT_PREFIX,
  CALLBACK_MANAGER_ASK_PREFIX,
  CALLBACK_MANAGER_REJECT_PREFIX,
  CALLBACK_ONBOARDING_UPLOAD_JOB,
  CALLBACK_ONBOARDING_UPLOAD_RESUME,
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

export function buildCandidateOnboardingKeyboard(): TelegramReplyMarkup {
  return {
    inline_keyboard: [[{ text: "Upload Resume", callback_data: CALLBACK_ONBOARDING_UPLOAD_RESUME }]],
  };
}

export function buildManagerOnboardingKeyboard(): TelegramReplyMarkup {
  return {
    inline_keyboard: [[{ text: "Upload Job Description", callback_data: CALLBACK_ONBOARDING_UPLOAD_JOB }]],
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
