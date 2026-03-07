import assert from "node:assert/strict";
import {
  MatchLifecycleService,
  MatchLifecycleTransitionError,
} from "../../core/matching/match-lifecycle.service";
import { MATCH_STATUSES } from "../../core/matching/match-statuses";

function testValidTransitions(): void {
  const service = new MatchLifecycleService();

  assert.equal(
    service.inviteCandidate(MATCH_STATUSES.PROPOSED),
    MATCH_STATUSES.INVITED,
  );
  assert.equal(
    service.candidateDeclinesMatch(MATCH_STATUSES.INVITED),
    MATCH_STATUSES.DECLINED,
  );
  assert.equal(
    service.startInterview(MATCH_STATUSES.INVITED),
    MATCH_STATUSES.INTERVIEW_STARTED,
  );
  assert.equal(
    service.completeInterview(MATCH_STATUSES.INTERVIEW_STARTED),
    MATCH_STATUSES.INTERVIEW_COMPLETED,
  );
  assert.equal(
    service.sendToManager(MATCH_STATUSES.INTERVIEW_COMPLETED),
    MATCH_STATUSES.SENT_TO_MANAGER,
  );
  assert.equal(
    service.managerApprovesCandidate(MATCH_STATUSES.SENT_TO_MANAGER),
    MATCH_STATUSES.APPROVED,
  );
}

function testInvalidTransitions(): void {
  const service = new MatchLifecycleService();

  assert.throws(
    () => service.inviteCandidate(MATCH_STATUSES.INVITED),
    MatchLifecycleTransitionError,
  );
  assert.throws(
    () => service.completeInterview(MATCH_STATUSES.INVITED),
    MatchLifecycleTransitionError,
  );
  assert.throws(
    () => service.managerRejectsCandidate(MATCH_STATUSES.INTERVIEW_COMPLETED),
    MatchLifecycleTransitionError,
  );

  assert.equal(
    service.tryTransition("MANAGER_APPROVES_CANDIDATE", MATCH_STATUSES.INTERVIEW_COMPLETED),
    null,
  );
}

function testInvariantEnforcement(): void {
  const service = new MatchLifecycleService();

  assert.throws(
    () => service.sendToManager(MATCH_STATUSES.INTERVIEW_STARTED),
    MatchLifecycleTransitionError,
  );
  assert.throws(
    () => service.sendToManager(MATCH_STATUSES.INVITED),
    MatchLifecycleTransitionError,
  );
}

function testFullHappyLifecyclePath(): void {
  const service = new MatchLifecycleService();

  const created = service.createMatch(MATCH_STATUSES.PROPOSED);
  const invited = service.inviteCandidate(created);
  const started = service.candidateAcceptsMatch(invited);
  const completed = service.completeInterview(started);
  const sent = service.sendToManager(completed);
  const approved = service.managerApprovesCandidate(sent);

  assert.equal(created, MATCH_STATUSES.PROPOSED);
  assert.equal(invited, MATCH_STATUSES.INVITED);
  assert.equal(started, MATCH_STATUSES.INTERVIEW_STARTED);
  assert.equal(completed, MATCH_STATUSES.INTERVIEW_COMPLETED);
  assert.equal(sent, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(approved, MATCH_STATUSES.APPROVED);
}

function testTransitionTableShape(): void {
  const service = new MatchLifecycleService();
  const table = service.getTransitionTable();
  assert.equal(table.INVITE_CANDIDATE.to, MATCH_STATUSES.INVITED);
  assert.equal(table.SEND_TO_MANAGER.from.includes(MATCH_STATUSES.INTERVIEW_COMPLETED), true);
}

function run(): void {
  testValidTransitions();
  testInvalidTransitions();
  testInvariantEnforcement();
  testFullHappyLifecyclePath();
  testTransitionTableShape();
  process.stdout.write("match-lifecycle.service tests passed.\n");
}

run();
