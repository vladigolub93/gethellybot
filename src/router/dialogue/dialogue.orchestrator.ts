import { Logger } from "../../config/logger";
import type { UserSessionState } from "../../shared/types/state.types";
import type { IntentClassificationResult } from "./intent.classifier";
import { IntentClassifier } from "./intent.classifier";
import type { DialogueLanguage } from "./language.service";
import { LanguageService } from "./language.service";
import type { ReplyComposeV2Result } from "./reply.composer";
import { ReplyComposerV2 } from "./reply.composer";

export type DialogueNextAction =
  | "prescreen_next_question"
  | "interpret_answer"
  | "run_matching"
  | "answer_question"
  | "ask_for_resume"
  | "ask_for_jd"
  | "help"
  | "pause_stop"
  | "skip_step"
  | "profile_status"
  | "none";

export interface DialogueOrchestratorResult {
  intent: IntentClassificationResult["intent"];
  language: DialogueLanguage;
  confidence: number;
  nextAction: DialogueNextAction;
  /** When we need to send a conversational reply, use this (from LLM). Null if composer failed or not needed. */
  composedReply: ReplyComposeV2Result | null;
  /** If user asked a clarifying question, we answered it and should continue with prescreen. */
  wasClarification: boolean;
}

function isInterviewingState(state: string): boolean {
  return state === "interviewing_candidate" || state === "interviewing_manager";
}

function isWaitingResume(state: string): boolean {
  return state === "waiting_resume";
}

function isWaitingJob(state: string): boolean {
  return state === "waiting_job";
}

function intentToNextAction(
  intent: IntentClassificationResult["intent"],
  state: string,
  role: "candidate" | "manager" | undefined,
): DialogueNextAction {
  switch (intent) {
    case "answer_to_current_question":
      return isInterviewingState(state) ? "interpret_answer" : "none";
    case "ask_bot_question":
      return "answer_question";
    case "request_matching":
      return "run_matching";
    case "pause_stop":
      return "pause_stop";
    case "skip":
      return "skip_step";
    case "profile_status":
      return "profile_status";
    case "admin_debug":
      return "help";
    case "other":
    default:
      if (isWaitingResume(state)) return "ask_for_resume";
      if (isWaitingJob(state)) return "ask_for_jd";
      return "none";
  }
}

export interface OrchestratorInput {
  userMessage: string;
  session: UserSessionState;
  /** Optional: when we already know we need to send a reply (e.g. meta, clarification), compose it. */
  composeReply?: boolean;
  /** Optional: next question text to include in composed reply (e.g. after clarification). */
  nextQuestionText?: string | null;
  /** Optional: profile summary lines for context. */
  profileSummaryFacts?: string[];
}

export class DialogueOrchestrator {
  constructor(
    private readonly intentClassifier: IntentClassifier,
    private readonly languageService: LanguageService,
    private readonly replyComposer: ReplyComposerV2,
    private readonly logger: Logger,
  ) {}

  async run(input: OrchestratorInput): Promise<DialogueOrchestratorResult> {
    const { userMessage, session, composeReply = true, nextQuestionText, profileSummaryFacts } = input;
    const role = session.role ?? "candidate";
    const state = session.state;

    const [classification, storedLanguage] = await Promise.all([
      this.intentClassifier.classify({
        userMessage,
        role,
        currentState: state,
        currentQuestionHint: getCurrentQuestionHint(session),
      }),
      this.languageService.getUserLanguage(session.userId),
    ]);

    const language = this.languageService.resolveLanguage(
      classification.language,
      storedLanguage,
      userMessage,
    );

    const nextAction = intentToNextAction(classification.intent, state, role);
    const wasClarification = classification.intent === "ask_bot_question";

    let composedReply: ReplyComposeV2Result | null = null;
    if (composeReply) {
      composedReply = await this.replyComposer.compose({
        userRole: role,
        userLanguage: language,
        currentState: state,
        nextQuestionText: wasClarification ? nextQuestionText : undefined,
        lastUserMessage: userMessage,
        profileSummaryFacts: profileSummaryFacts ?? [],
        lastBotMessage: session.lastBotMessage ?? undefined,
        avoidPhrase: session.lastBotMessage ?? undefined,
      });
    }

    this.logger.debug("dialogue.orchestrator.result", {
      intent: classification.intent,
      nextAction,
      language,
      hasComposedReply: !!composedReply,
    });

    return {
      intent: classification.intent,
      language,
      confidence: classification.confidence,
      nextAction,
      composedReply,
      wasClarification,
    };
  }
}

function getCurrentQuestionHint(session: UserSessionState): string | null {
  const planV2 = session.candidateInterviewPlanV2;
  if (planV2?.questions?.length) {
    const idx = session.prescreenQuestionIndex ?? session.currentQuestionIndex ?? 0;
    const q = planV2.questions[idx];
    return q?.question_text ?? null;
  }
  const jobPlan = session.jobPrescreenPlan;
  if (Array.isArray(jobPlan) && jobPlan.length) {
    const idx = session.jobPrescreenQuestionIndex ?? 0;
    const q = jobPlan[idx];
    return (q as { question?: string })?.question ?? null;
  }
  const legacyPlan = session.interviewPlan as unknown;
  if (legacyPlan && typeof legacyPlan === "object" && "questions" in legacyPlan) {
    const questions = (legacyPlan as { questions: ReadonlyArray<{ text?: string; question?: string }> }).questions;
    const idx = session.currentQuestionIndex ?? 0;
    const q = questions[idx];
    return q?.question ?? q?.text ?? null;
  }
  return null;
}
