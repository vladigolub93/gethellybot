import assert from "node:assert/strict";
import {
  InterviewLifecycleService,
  InterviewLifecycleTransitionError,
} from "../../core/matching/interview-lifecycle.service";
import { INTERVIEW_STATUSES } from "../../core/matching/interview-statuses";

function testValidCompletionTransitions(): void {
  const service = new InterviewLifecycleService();

  assert.equal(
    service.completeInterview(INTERVIEW_STATUSES.STARTED),
    INTERVIEW_STATUSES.COMPLETED,
  );
  assert.equal(
    service.completeInterview(INTERVIEW_STATUSES.IN_PROGRESS),
    INTERVIEW_STATUSES.COMPLETED,
  );
}

function testInvalidCompletionTransition(): void {
  const service = new InterviewLifecycleService();

  assert.throws(
    () => service.completeInterview(INTERVIEW_STATUSES.INVITED),
    InterviewLifecycleTransitionError,
  );
  assert.equal(
    service.tryTransition("COMPLETE_INTERVIEW", INTERVIEW_STATUSES.INVITED),
    null,
  );
}

function testTransitionTableShape(): void {
  const service = new InterviewLifecycleService();
  const table = service.getTransitionTable();

  assert.equal(table.COMPLETE_INTERVIEW.to, INTERVIEW_STATUSES.COMPLETED);
  assert.equal(table.COMPLETE_INTERVIEW.from.includes(INTERVIEW_STATUSES.STARTED), true);
  assert.equal(table.COMPLETE_INTERVIEW.from.includes(INTERVIEW_STATUSES.IN_PROGRESS), true);
}

function run(): void {
  testValidCompletionTransitions();
  testInvalidCompletionTransition();
  testTransitionTableShape();
  process.stdout.write("interview-lifecycle.service tests passed.\n");
}

run();
