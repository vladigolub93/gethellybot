import assert from "node:assert/strict";
import { HELLY_ACTIONS } from "../../core/state/actions";
import { HELLY_STATES } from "../../core/state/states";
import { GatekeeperService } from "../../core/state/gatekeeper/gatekeeper.service";

function testAllowedActionAccepted(): void {
  const gatekeeper = new GatekeeperService({ minConfidence: 0.6 });

  const result = gatekeeper.evaluate({
    currentState: HELLY_STATES.WAIT_ROLE,
    action: HELLY_ACTIONS.SELECT_ROLE_CANDIDATE,
    confidence: 0.91,
    message: "Great, I can set you as candidate.",
  });

  assert.equal(result.accepted, true);
  assert.equal(result.reason, "ACCEPTED");
  assert.equal(result.action, HELLY_ACTIONS.SELECT_ROLE_CANDIDATE);
  assert.equal(result.message, "Great, I can set you as candidate.");
}

function testNullActionRejected(): void {
  const gatekeeper = new GatekeeperService({ minConfidence: 0.6 });

  const result = gatekeeper.evaluate({
    currentState: HELLY_STATES.C_WAIT_CV,
    action: null,
    confidence: 0.95,
    message: "Could you share a bit more detail?",
  });

  assert.equal(result.accepted, false);
  assert.equal(result.reason, "NO_ACTION");
  assert.equal(result.action, null);
  assert.equal(result.message, "Could you share a bit more detail?");
}

function testActionRejectedWhenNotAllowedInState(): void {
  const gatekeeper = new GatekeeperService({ minConfidence: 0.6 });

  const result = gatekeeper.evaluate({
    currentState: HELLY_STATES.C_CV_PROCESSING,
    action: HELLY_ACTIONS.DELETE_PROFILE,
    confidence: 0.9,
    message: "I can process that once processing is complete.",
  });

  assert.equal(result.accepted, false);
  assert.equal(result.reason, "ACTION_NOT_ALLOWED");
  assert.equal(result.action, HELLY_ACTIONS.DELETE_PROFILE);
  assert.equal(result.message, "I can process that once processing is complete.");
}

function testLowConfidenceRejected(): void {
  const gatekeeper = new GatekeeperService({ minConfidence: 0.6 });

  const result = gatekeeper.evaluate({
    currentState: HELLY_STATES.WAIT_ROLE,
    action: HELLY_ACTIONS.SELECT_ROLE_MANAGER,
    confidence: 0.25,
    message: "I think you may want manager role.",
  });

  assert.equal(result.accepted, false);
  assert.equal(result.reason, "LOW_CONFIDENCE");
  assert.equal(result.action, HELLY_ACTIONS.SELECT_ROLE_MANAGER);
  assert.equal(result.message, "I think you may want manager role.");
}

function run(): void {
  testAllowedActionAccepted();
  testNullActionRejected();
  testActionRejectedWhenNotAllowedInState();
  testLowConfidenceRejected();
  process.stdout.write("gatekeeper.service tests passed.\n");
}

run();
