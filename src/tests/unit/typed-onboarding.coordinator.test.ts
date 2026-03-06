import assert from "node:assert/strict";
import { HELLY_ACTIONS } from "../../core/state/actions";
import { StateService } from "../../state/state.service";
import { TypedOnboardingCoordinator } from "../../router/typed-onboarding.coordinator";

type LogEntry = {
  level: "debug" | "warn";
  message: string;
  meta?: Record<string, unknown>;
};

function createLogger(entries: LogEntry[]) {
  return {
    debug(message: string, meta?: Record<string, unknown>) {
      entries.push({ level: "debug", message, meta });
    },
    warn(message: string, meta?: Record<string, unknown>) {
      entries.push({ level: "warn", message, meta });
    },
  };
}

function createCoordinator(input?: {
  flags?: Partial<{
    enableTypedRoleSelectionRouter: boolean;
    enableTypedContactRouter: boolean;
    enableTypedCvRouter: boolean;
    enableTypedJdRouter: boolean;
    enableTypedCandidateReviewRouter: boolean;
    enableTypedManagerReviewRouter: boolean;
  }>;
  actionRouterResult?: {
    action: typeof HELLY_ACTIONS[keyof typeof HELLY_ACTIONS] | null;
    confidence: number;
    message: string;
  };
  gatekeeperResult?: {
    accepted: boolean;
    reason: "ACCEPTED" | "NO_ACTION" | "ACTION_NOT_ALLOWED" | "LOW_CONFIDENCE";
    action: typeof HELLY_ACTIONS[keyof typeof HELLY_ACTIONS] | null;
    message: string;
  };
}): {
  coordinator: TypedOnboardingCoordinator;
  actionRouterCalls: () => number;
  gatekeeperCalls: () => number;
  logs: LogEntry[];
} {
  const opts = input ?? {};
  let actionRouterCalls = 0;
  let gatekeeperCalls = 0;
  const logs: LogEntry[] = [];
  const logger = createLogger(logs);
  const coordinator = new TypedOnboardingCoordinator(
    {
      enableTypedRoleSelectionRouter: opts.flags?.enableTypedRoleSelectionRouter ?? true,
      enableTypedContactRouter: opts.flags?.enableTypedContactRouter ?? true,
      enableTypedCvRouter: opts.flags?.enableTypedCvRouter ?? true,
      enableTypedJdRouter: opts.flags?.enableTypedJdRouter ?? true,
      enableTypedCandidateReviewRouter:
        opts.flags?.enableTypedCandidateReviewRouter ?? true,
      enableTypedManagerReviewRouter:
        opts.flags?.enableTypedManagerReviewRouter ?? true,
    },
    {
      async classify() {
        actionRouterCalls += 1;
        return (
          opts.actionRouterResult ?? {
            action: HELLY_ACTIONS.SELECT_ROLE_CANDIDATE,
            confidence: 0.95,
            message: "Typed action detected.",
          }
        );
      },
    } as never,
    {
      evaluate(inputEvaluate: {
        action: typeof HELLY_ACTIONS[keyof typeof HELLY_ACTIONS] | null;
        confidence: number;
        message: string;
      }) {
        gatekeeperCalls += 1;
        return (
          opts.gatekeeperResult ?? {
            accepted: true,
            reason: "ACCEPTED",
            action: inputEvaluate.action,
            message: inputEvaluate.message,
          }
        );
      },
    } as never,
    logger,
  );

  return {
    coordinator,
    actionRouterCalls: () => actionRouterCalls,
    gatekeeperCalls: () => gatekeeperCalls,
    logs,
  };
}

function createSession(userId: number, chatId: number) {
  const stateService = new StateService();
  return stateService.getOrCreate(userId, chatId);
}

async function testRoleSelectionRunsThroughCoordinator(): Promise<void> {
  const harness = createCoordinator();
  const session = createSession(1, 1);
  session.state = "role_selection";

  const result = await harness.coordinator.attemptRoleSelection({
    session,
    userMessage: "I am a Candidate",
  });

  assert.equal(result.attempted, true);
  assert.equal(result.accepted, true);
  assert.equal(result.action, HELLY_ACTIONS.SELECT_ROLE_CANDIDATE);
  assert.equal(harness.actionRouterCalls(), 1);
  assert.equal(harness.gatekeeperCalls(), 1);
}

async function testOutOfScopeSkipsAttempt(): Promise<void> {
  const harness = createCoordinator();
  const session = createSession(2, 2);
  session.state = "waiting_resume";

  const result = await harness.coordinator.attemptRoleSelection({
    session,
    userMessage: "I am a Candidate",
  });

  assert.equal(result.attempted, false);
  assert.equal(result.accepted, false);
  assert.equal(result.reason, "OUT_OF_SCOPE");
  assert.equal(harness.actionRouterCalls(), 0);
  assert.equal(harness.gatekeeperCalls(), 0);
}

async function testFeatureFlagOffStillPreservesFallback(): Promise<void> {
  const harness = createCoordinator({
    flags: {
      enableTypedContactRouter: false,
    },
  });
  const session = createSession(3, 3);
  session.state = "role_selection";

  const result = await harness.coordinator.attemptContactIdentity({
    session,
    userMessage: "share my contact",
    awaitingContactChoice: true,
  });

  assert.equal(result.attempted, true);
  assert.equal(result.accepted, false);
  assert.equal(result.reason, "FEATURE_FLAG_OFF");
  assert.equal(harness.actionRouterCalls(), 0);
  assert.equal(harness.gatekeeperCalls(), 0);
}

async function testCandidateReviewContextUsesCoordinatorRules(): Promise<void> {
  const harness = createCoordinator({
    actionRouterResult: {
      action: HELLY_ACTIONS.APPROVE,
      confidence: 0.91,
      message: "Summary approved.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: HELLY_ACTIONS.APPROVE,
      message: "Summary approved.",
    },
  });
  const session = createSession(4, 4);
  session.state = "interviewing_candidate";
  session.role = "candidate";
  session.interviewPlan = {
    summary: "Candidate",
    questions: [
      {
        id: "q1",
        question: "Please confirm your profile summary is correct.",
        goal: "summary",
        gapToClarify: "fit",
      },
    ],
  };
  session.currentQuestionIndex = 0;
  session.answers = [];
  session.pendingFollowUp = undefined;

  const result = await harness.coordinator.attemptCandidateReview({
    session,
    userMessage: "approve",
    currentQuestion: "Please confirm your profile summary is correct.",
    currentQuestionIndex: 0,
    hasFinalAnswers: false,
  });

  assert.equal(result.attempted, true);
  assert.equal(result.accepted, true);
  assert.equal(result.action, HELLY_ACTIONS.APPROVE);
  assert.equal(harness.actionRouterCalls(), 1);
  assert.equal(harness.gatekeeperCalls(), 1);
}

async function testManagerReviewContextUsesCoordinatorRules(): Promise<void> {
  const harness = createCoordinator({
    actionRouterResult: {
      action: HELLY_ACTIONS.APPROVE,
      confidence: 0.9,
      message: "Vacancy summary approved.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: HELLY_ACTIONS.APPROVE,
      message: "Vacancy summary approved.",
    },
  });
  const session = createSession(5, 5);
  session.state = "interviewing_manager";
  session.role = "manager";
  session.interviewPlan = {
    summary: "Manager",
    questions: [
      {
        id: "q1",
        question: "Please confirm your vacancy summary is correct.",
        goal: "summary",
        gapToClarify: "fit",
      },
    ],
  };
  session.currentQuestionIndex = 0;
  session.answers = [];
  session.pendingFollowUp = undefined;

  const result = await harness.coordinator.attemptManagerReview({
    session,
    userMessage: "approve",
    currentQuestion: "Please confirm your vacancy summary is correct.",
    currentQuestionIndex: 0,
    hasFinalAnswers: false,
  });

  assert.equal(result.attempted, true);
  assert.equal(result.accepted, true);
  assert.equal(result.action, HELLY_ACTIONS.APPROVE);
  assert.equal(harness.actionRouterCalls(), 1);
  assert.equal(harness.gatekeeperCalls(), 1);
}

async function run(): Promise<void> {
  await testRoleSelectionRunsThroughCoordinator();
  await testOutOfScopeSkipsAttempt();
  await testFeatureFlagOffStillPreservesFallback();
  await testCandidateReviewContextUsesCoordinatorRules();
  await testManagerReviewContextUsesCoordinatorRules();
  process.stdout.write("typed-onboarding.coordinator tests passed.\n");
}

void run();
