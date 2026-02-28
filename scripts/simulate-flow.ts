import { createLogger, Logger } from "../src/config/logger";
import { AlwaysOnRouterService } from "../src/router/always-on-router.service";
import { AlwaysOnRouterDecision } from "../src/shared/types/always-on-router.types";
import { NormalizedUpdate } from "../src/shared/types/telegram.types";
import { UserState } from "../src/shared/types/state.types";
import { CHAT_MODEL } from "../src/ai/llm.client";
import { HELLY_SYSTEM_PROMPT } from "../src/ai/system/helly.system";
import { buildLlmGateDispatcher } from "../src/router/dispatch/llm-gate.dispatcher";

type Role = "candidate" | "manager";

interface SimSession {
  state: UserState;
  role: Role;
  currentQuestion: string | null;
  questionIndex: number;
}

class FakeStateRouter {
  public readonly decisions: AlwaysOnRouterDecision[] = [];
  public routerCalledCount = 0;
  public fallbackSeen = false;
  private readonly sessions = new Map<number, SimSession>();

  constructor(
    private readonly alwaysOnRouterService: AlwaysOnRouterService,
    private readonly logger: Logger,
  ) {}

  setSession(userId: number, session: SimSession): void {
    this.sessions.set(userId, { ...session });
  }

  getSession(userId: number): SimSession | undefined {
    return this.sessions.get(userId);
  }

  async route(update: NormalizedUpdate): Promise<void> {
    const session = this.sessions.get(update.userId);
    if (!session) {
      throw new Error(`Missing simulated session for user ${update.userId}`);
    }
    const textEnglish = update.kind === "text" ? update.text : null;
    const decision = await this.alwaysOnRouterService.classify({
      updateId: update.updateId,
      telegramUserId: update.userId,
      currentState: session.state,
      userRole: session.role,
      hasText: Boolean(textEnglish),
      textEnglish,
      hasDocument: update.kind === "document",
      hasVoice: update.kind === "voice",
      currentQuestion: session.currentQuestion,
      lastBotMessage: null,
    });
    this.routerCalledCount += 1;
    this.decisions.push(decision);
    if (decision.reply.toLowerCase().includes("i had trouble understanding")) {
      this.fallbackSeen = true;
    }
    this.logger.info("simulate.route", {
      update_id: update.updateId,
      telegram_user_id: update.userId,
      route: decision.route,
      did_call_llm_router: true,
    });
    applyDecision(session, decision);
  }
}

class MockLlmClient {
  getModelName(): string {
    return CHAT_MODEL;
  }

  async generateStructuredJson(prompt: string): Promise<string> {
    const context = parseRuntimeContext(prompt);
    const text = String(context.text_english ?? "").toLowerCase();
    const state = String(context.current_state ?? "");
    const hasDocument = Boolean(context.has_document);
    const hasVoice = Boolean(context.has_voice);
    const hasText = Boolean(context.has_text);

    const base = {
      meta_type: null,
      control_type: null,
      matching_intent: null,
      should_advance: false,
      should_process_text_as_document: false,
    };

    if (hasDocument) {
      return JSON.stringify({
        ...base,
        route: "DOC",
        reply: "Document received. I will process it now.",
      });
    }

    if (hasVoice) {
      return JSON.stringify({
        ...base,
        route: "VOICE",
        reply: "Voice message received. I will transcribe it now.",
      });
    }

    if (!hasText) {
      return JSON.stringify({
        ...base,
        route: "OTHER",
        reply: "Please continue with the current step.",
      });
    }

    if (state === "waiting_job" && text.includes("can i paste")) {
      return JSON.stringify({
        ...base,
        route: "META",
        meta_type: "format",
        reply: "Yes. You can paste the job description text here, or send or forward a PDF or DOCX file. Both work.",
      });
    }

    if (state === "waiting_job" && text.length >= 400) {
      return JSON.stringify({
        ...base,
        route: "JD_TEXT",
        reply: "Got it. I will process this job description now.",
        should_process_text_as_document: true,
      });
    }

    if (state === "interviewing_manager" && text.includes("what do you mean")) {
      return JSON.stringify({
        ...base,
        route: "META",
        meta_type: "format",
        reply: "By architecture, I mean components, data flow, decisions, and trade offs.",
      });
    }

    if (state === "waiting_resume" && text.length >= 400) {
      return JSON.stringify({
        ...base,
        route: "RESUME_TEXT",
        reply: "Got it. I will process your resume now.",
        should_process_text_as_document: true,
      });
    }

    if (state === "interviewing_candidate" && (text.includes("russian") || text.includes("ukrainian"))) {
      return JSON.stringify({
        ...base,
        route: "META",
        meta_type: "language",
        reply: "Yes. You can answer interview questions by voice in Russian or Ukrainian. I will transcribe and understand.",
      });
    }

    return JSON.stringify({
      ...base,
      route: "INTERVIEW_ANSWER",
      reply: "Thanks, continuing interview.",
      should_advance: true,
    });
  }
}

function parseRuntimeContext(prompt: string): Record<string, unknown> {
  const marker = "Runtime context JSON:";
  const index = prompt.indexOf(marker);
  if (index < 0) {
    return {};
  }
  const text = prompt.slice(index + marker.length).trim();
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return {};
  }
}

async function run(): Promise<void> {
  if (!HELLY_SYSTEM_PROMPT.trim()) {
    throw new Error("HELLY_SYSTEM_PROMPT is empty.");
  }

  const logger = createLogger();
  const llmClient = new MockLlmClient();
  const router = new AlwaysOnRouterService(llmClient as never, logger);
  const fakeStateRouter = new FakeStateRouter(router, logger);
  const dispatcher = buildLlmGateDispatcher({
    stateRouter: fakeStateRouter as never,
    logger,
  });

  const flows: Array<{
    name: string;
    initial: SimSession;
    updates: NormalizedUpdate[];
  }> = [
    {
      name: "manager_jd_flow",
      initial: {
        state: "waiting_job",
        role: "manager",
        currentQuestion: "What are the top tasks in the first three months?",
        questionIndex: 0,
      },
      updates: [
        textUpdate(1, 1001, "Can I paste it as text?"),
        textUpdate(2, 1001, buildLongJdText()),
        textUpdate(3, 1001, "What do you mean by architecture here?"),
      ],
    },
    {
      name: "candidate_resume_flow",
      initial: {
        state: "waiting_resume",
        role: "candidate",
        currentQuestion: "Describe your strongest backend project.",
        questionIndex: 0,
      },
      updates: [
        textUpdate(4, 2001, buildLongResumeText()),
        textUpdate(5, 2001, "Can I answer by voice in Russian?"),
        voiceUpdate(6, 2001),
      ],
    },
  ];

  let totalUpdates = 0;
  for (const flow of flows) {
    fakeStateRouter.setSession(flow.updates[0].userId, flow.initial);
    for (const update of flow.updates) {
      totalUpdates += 1;
      await dispatcher.handleIncomingUpdate(update);
    }
  }

  assert(fakeStateRouter.routerCalledCount === totalUpdates, "router was not called for every step");
  assert(!fakeStateRouter.fallbackSeen, "generic fallback reply detected");
  const managerFinal = fakeStateRouter.getSession(1001);
  const candidateFinal = fakeStateRouter.getSession(2001);
  assert(Boolean(managerFinal), "manager session missing");
  assert(Boolean(candidateFinal), "candidate session missing");
  assert((managerFinal?.questionIndex ?? 0) === 0, "manager interview advanced on meta step");
  assert((candidateFinal?.questionIndex ?? 0) === 0, "candidate interview advanced on meta step");
  console.log("simulate-flow passed");
}

function applyDecision(session: SimSession, decision: AlwaysOnRouterDecision): void {
  if (
    (decision.route === "JD_TEXT" || decision.route === "DOC") &&
    (session.state === "waiting_job" || session.state === "extracting_job")
  ) {
    session.state = "interviewing_manager";
    session.currentQuestion = "What is the real architecture complexity for this role?";
    return;
  }
  if (
    (decision.route === "RESUME_TEXT" || decision.route === "DOC") &&
    (session.state === "waiting_resume" || session.state === "extracting_resume")
  ) {
    session.state = "interviewing_candidate";
    session.currentQuestion = "Tell me about one project where you owned architecture decisions.";
    return;
  }
  if (decision.route === "INTERVIEW_ANSWER" && decision.should_advance) {
    session.questionIndex += 1;
  }
}

function textUpdate(updateId: number, userId: number, text: string): NormalizedUpdate {
  return {
    kind: "text",
    updateId,
    chatId: userId,
    userId,
    text,
  };
}

function voiceUpdate(updateId: number, userId: number): NormalizedUpdate {
  return {
    kind: "voice",
    updateId,
    chatId: userId,
    userId,
    fileId: `voice_${updateId}`,
    durationSec: 21,
  };
}

function buildLongJdText(): string {
  return [
    "Role: Senior Backend Engineer.",
    "We are hiring for a B2B platform product in growth stage.",
    "Responsibilities: design services, improve reliability, optimize performance, deliver features.",
    "Requirements: Node.js, PostgreSQL, distributed systems, observability, incident ownership.",
    "Tech stack: Node.js, TypeScript, PostgreSQL, Redis, Kafka, Docker, Kubernetes.",
    "Must have: production ownership, architecture decisions, mentoring.",
    "Nice to have: fintech domain context.",
    "This is a long JD text used in simulation to trigger JD intake routing.",
  ].join("\n");
}

function buildLongResumeText(): string {
  return [
    "Summary: Senior backend engineer with 8 years of hands-on experience.",
    "Work experience: 2019-2026 Platform Engineer at Example Corp.",
    "Designed microservices, owned PostgreSQL schema design, handled production incidents.",
    "Skills: Node.js, TypeScript, PostgreSQL, Redis, Kafka, Docker, Kubernetes.",
    "Projects: payment processing platform, high-load notification system, data pipelines.",
    "Education: Computer Science.",
    "LinkedIn: https://linkedin.example/profile",
    "GitHub: https://github.com/example",
  ].join("\n");
}

function assert(condition: unknown, message: string): void {
  if (!condition) {
    throw new Error(`simulate-flow failed, ${message}`);
  }
}

run().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(1);
});
