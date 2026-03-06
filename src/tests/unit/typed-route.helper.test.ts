import assert from "node:assert/strict";
import { HELLY_ACTIONS } from "../../core/state/actions";
import { HELLY_STATES } from "../../core/state/states";
import { runTypedRoute } from "../../router/helpers/typed-route.helper";

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

async function testFeatureFlagOffSkipsTypedRoute(): Promise<void> {
  let classifyCalled = false;
  let gatekeeperCalled = false;
  const logs: LogEntry[] = [];
  const logger = createLogger(logs);

  const result = await runTypedRoute({
    enabled: false,
    logPrefix: "typed_test",
    userId: 1,
    runtimeState: "role_selection",
    userMessage: "I am a Candidate",
    expectedCanonicalState: HELLY_STATES.WAIT_ROLE,
    resolveCanonicalState: () => HELLY_STATES.WAIT_ROLE,
    acceptedActions: [HELLY_ACTIONS.SELECT_ROLE_CANDIDATE],
    actionRouterService: {
      async classify() {
        classifyCalled = true;
        return {
          action: HELLY_ACTIONS.SELECT_ROLE_CANDIDATE,
          confidence: 0.99,
          message: "Candidate role selected.",
        };
      },
    },
    gatekeeperService: {
      evaluate() {
        gatekeeperCalled = true;
        return {
          accepted: true,
          reason: "ACCEPTED",
          action: HELLY_ACTIONS.SELECT_ROLE_CANDIDATE,
          message: "Candidate role selected.",
        };
      },
    },
    logger,
  });

  assert.equal(result.accepted, false);
  assert.equal(result.usedTypedPath, false);
  assert.equal(result.reason, "FEATURE_FLAG_OFF");
  assert.equal(classifyCalled, false);
  assert.equal(gatekeeperCalled, false);
  assert.equal(logs.length, 0);
}

async function testAcceptedTypedPath(): Promise<void> {
  const logs: LogEntry[] = [];
  const logger = createLogger(logs);

  const result = await runTypedRoute({
    enabled: true,
    logPrefix: "typed_test",
    userId: 2,
    runtimeState: "role_selection",
    userMessage: "I am a Candidate",
    expectedCanonicalState: HELLY_STATES.WAIT_ROLE,
    resolveCanonicalState: () => HELLY_STATES.WAIT_ROLE,
    acceptedActions: [HELLY_ACTIONS.SELECT_ROLE_CANDIDATE],
    actionRouterService: {
      async classify() {
        return {
          action: HELLY_ACTIONS.SELECT_ROLE_CANDIDATE,
          confidence: 0.97,
          message: "Candidate role selected.",
        };
      },
    },
    gatekeeperService: {
      evaluate() {
        return {
          accepted: true,
          reason: "ACCEPTED",
          action: HELLY_ACTIONS.SELECT_ROLE_CANDIDATE,
          message: "Candidate role selected.",
        };
      },
    },
    logger,
  });

  assert.equal(result.accepted, true);
  assert.equal(result.usedTypedPath, true);
  assert.equal(result.reason, "ACCEPTED");
  assert.equal(
    logs.some((entry) => entry.message === "typed_test.path" && entry.meta?.path === "typed"),
    true,
  );
}

async function testUnmappedStateFallsBack(): Promise<void> {
  let classifyCalled = false;
  const logs: LogEntry[] = [];
  const logger = createLogger(logs);

  const result = await runTypedRoute({
    enabled: true,
    logPrefix: "typed_test",
    userId: 3,
    runtimeState: "unknown_state",
    userMessage: "hello",
    expectedCanonicalState: HELLY_STATES.WAIT_ROLE,
    resolveCanonicalState: () => null,
    acceptedActions: [HELLY_ACTIONS.SELECT_ROLE_CANDIDATE],
    actionRouterService: {
      async classify() {
        classifyCalled = true;
        return {
          action: HELLY_ACTIONS.SELECT_ROLE_CANDIDATE,
          confidence: 0.9,
          message: "Candidate role selected.",
        };
      },
    },
    gatekeeperService: {
      evaluate() {
        return {
          accepted: true,
          reason: "ACCEPTED",
          action: HELLY_ACTIONS.SELECT_ROLE_CANDIDATE,
          message: "Candidate role selected.",
        };
      },
    },
    logger,
  });

  assert.equal(result.accepted, false);
  assert.equal(result.usedTypedPath, false);
  assert.equal(result.reason, "UNMAPPED_STATE_OR_MISSING_DEPS");
  assert.equal(classifyCalled, false);
  assert.equal(
    logs.some((entry) => entry.message === "typed_test.path" && entry.meta?.reason === "UNMAPPED_STATE_OR_MISSING_DEPS"),
    true,
  );
}

async function testClassifierFailureFallsBack(): Promise<void> {
  const logs: LogEntry[] = [];
  const logger = createLogger(logs);

  const result = await runTypedRoute({
    enabled: true,
    logPrefix: "typed_test",
    userId: 4,
    runtimeState: "role_selection",
    userMessage: "I am a Candidate",
    expectedCanonicalState: HELLY_STATES.WAIT_ROLE,
    resolveCanonicalState: () => HELLY_STATES.WAIT_ROLE,
    acceptedActions: [HELLY_ACTIONS.SELECT_ROLE_CANDIDATE],
    actionRouterService: {
      async classify() {
        throw new Error("LLM timeout");
      },
    },
    gatekeeperService: {
      evaluate() {
        return {
          accepted: true,
          reason: "ACCEPTED",
          action: HELLY_ACTIONS.SELECT_ROLE_CANDIDATE,
          message: "Candidate role selected.",
        };
      },
    },
    logger,
  });

  assert.equal(result.accepted, false);
  assert.equal(result.usedTypedPath, false);
  assert.equal(result.reason, "FAILED_LEGACY_FALLBACK");
  assert.equal(
    logs.some((entry) => entry.level === "warn" && entry.message === "typed_test.failed_legacy_fallback"),
    true,
  );
}

async function run(): Promise<void> {
  await testFeatureFlagOffSkipsTypedRoute();
  await testAcceptedTypedPath();
  await testUnmappedStateFallsBack();
  await testClassifierFailureFallsBack();
  process.stdout.write("typed-route.helper tests passed.\n");
}

void run();
