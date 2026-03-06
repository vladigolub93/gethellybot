import assert from "node:assert/strict";
import {
  FLOW_STAGES,
  resolveFlowStage,
} from "../../router/flow-stage.resolver";
import { StateService } from "../../state/state.service";

function createSession(userId: number, chatId: number) {
  const stateService = new StateService();
  return stateService.getOrCreate(userId, chatId);
}

function testRoleSelectionStage(): void {
  const session = createSession(1, 1);
  session.state = "role_selection";
  session.awaitingContactChoice = false;

  const stage = resolveFlowStage({ session });
  assert.equal(stage, FLOW_STAGES.ROLE_SELECTION);
}

function testContactIdentityStage(): void {
  const session = createSession(2, 2);
  session.state = "role_selection";
  session.awaitingContactChoice = true;

  const stage = resolveFlowStage({ session });
  assert.equal(stage, FLOW_STAGES.CONTACT_IDENTITY);
}

function testCandidateCvIntakeStage(): void {
  const session = createSession(3, 3);
  session.state = "waiting_resume";

  const stage = resolveFlowStage({ session });
  assert.equal(stage, FLOW_STAGES.CANDIDATE_CV_INTAKE);
}

function testCandidateMandatoryStage(): void {
  const session = createSession(8, 8);
  session.state = "candidate_mandatory_fields";
  session.role = "candidate";

  const stage = resolveFlowStage({ session });
  assert.equal(stage, FLOW_STAGES.CANDIDATE_MANDATORY);
}

function testCandidateReviewStage(): void {
  const session = createSession(4, 4);
  session.state = "interviewing_candidate";
  session.role = "candidate";
  session.currentQuestionIndex = 0;
  session.pendingFollowUp = undefined;
  session.answers = [];

  const stage = resolveFlowStage({
    session,
    context: {
      currentQuestionText: "Please confirm your profile summary.",
      currentQuestionIndex: 0,
      hasFinalAnswers: false,
    },
  });
  assert.equal(stage, FLOW_STAGES.CANDIDATE_REVIEW);
}

function testManagerJdIntakeStage(): void {
  const session = createSession(5, 5);
  session.state = "waiting_job";

  const stage = resolveFlowStage({ session });
  assert.equal(stage, FLOW_STAGES.MANAGER_JD_INTAKE);
}

function testManagerMandatoryStage(): void {
  const session = createSession(9, 9);
  session.state = "manager_mandatory_fields";
  session.role = "manager";

  const stage = resolveFlowStage({ session });
  assert.equal(stage, FLOW_STAGES.MANAGER_MANDATORY);
}

function testCandidateDecisionStage(): void {
  const session = createSession(10, 10);
  session.state = "waiting_candidate_decision";
  session.role = "candidate";

  const stage = resolveFlowStage({ session });
  assert.equal(stage, FLOW_STAGES.CANDIDATE_DECISION);
}

function testInterviewInvitationStage(): void {
  const session = createSession(12, 12);
  session.state = "waiting_candidate_decision";
  session.role = "candidate";
  session.matching = {
    lastShownMatchIds: ["match_1"],
    lastActionableMatchId: "match_1",
  };

  const stage = resolveFlowStage({ session });
  assert.equal(stage, FLOW_STAGES.INTERVIEW_INVITATION);
}

function testManagerDecisionStage(): void {
  const session = createSession(11, 11);
  session.state = "waiting_manager_decision";
  session.role = "manager";

  const stage = resolveFlowStage({ session });
  assert.equal(stage, FLOW_STAGES.MANAGER_DECISION);
}

function testManagerReviewStage(): void {
  const session = createSession(6, 6);
  session.state = "interviewing_manager";
  session.role = "manager";
  session.currentQuestionIndex = 0;
  session.pendingFollowUp = undefined;
  session.answers = [];

  const stage = resolveFlowStage({
    session,
    context: {
      currentQuestionText: "Please confirm your vacancy summary.",
      currentQuestionIndex: 0,
      hasFinalAnswers: false,
    },
  });
  assert.equal(stage, FLOW_STAGES.MANAGER_REVIEW);
}

function testCandidateInterviewAnswerStage(): void {
  const session = createSession(13, 13);
  session.state = "interviewing_candidate";
  session.role = "candidate";
  session.currentQuestionIndex = 1;
  session.answers = [];

  const stage = resolveFlowStage({
    session,
    context: {
      currentQuestionText: "Describe a recent migration project you led.",
      currentQuestionIndex: 1,
      hasFinalAnswers: true,
    },
  });
  assert.equal(stage, FLOW_STAGES.INTERVIEW_ANSWER);
}

function testManagerInterviewAnswerStage(): void {
  const session = createSession(14, 14);
  session.state = "interviewing_manager";
  session.role = "manager";
  session.currentQuestionIndex = 1;
  session.answers = [];

  const stage = resolveFlowStage({
    session,
    context: {
      currentQuestionText: "What delivery timeline is acceptable?",
      currentQuestionIndex: 1,
      hasFinalAnswers: true,
    },
  });
  assert.equal(stage, FLOW_STAGES.INTERVIEW_ANSWER);
}

function testOutOfScopeStage(): void {
  const session = createSession(7, 7);
  session.state = "candidate_profile_ready";

  const stage = resolveFlowStage({ session });
  assert.equal(stage, FLOW_STAGES.OUT_OF_SCOPE);
}

function run(): void {
  testRoleSelectionStage();
  testContactIdentityStage();
  testCandidateCvIntakeStage();
  testCandidateMandatoryStage();
  testCandidateReviewStage();
  testManagerJdIntakeStage();
  testManagerMandatoryStage();
  testCandidateDecisionStage();
  testInterviewInvitationStage();
  testManagerDecisionStage();
  testManagerReviewStage();
  testCandidateInterviewAnswerStage();
  testManagerInterviewAnswerStage();
  testOutOfScopeStage();
  process.stdout.write("flow-stage.resolver tests passed.\n");
}

run();
