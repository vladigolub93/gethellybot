import { ActionRouterService } from "../ai/action-router/action-router.service";
import { Logger } from "../config/logger";
import { HELLY_ACTIONS, HellyAction } from "../core/state/actions";
import { GatekeeperService } from "../core/state/gatekeeper/gatekeeper.service";
import { mapRuntimeStateToHellyState } from "../core/state/runtime-state.adapter";
import { HELLY_STATES } from "../core/state/states";
import { UserSessionState } from "../shared/types/state.types";
import {
  runTypedRoute,
  RunTypedRouteResult,
  TypedRouteReason,
} from "./helpers/typed-route.helper";
import {
  FLOW_STAGES,
  FlowStage,
  resolveFlowStage,
} from "./flow-stage.resolver";

const DEFAULT_FALLBACK_MESSAGE = "Please continue with the current step.";

type TypedFlowFlags = {
  enableTypedRoleSelectionRouter: boolean;
  enableTypedContactRouter: boolean;
  enableTypedCvRouter: boolean;
  enableTypedJdRouter: boolean;
  enableTypedCandidateMandatoryRouter: boolean;
  enableTypedManagerMandatoryRouter: boolean;
  enableTypedCandidateDecisionRouter: boolean;
  enableTypedManagerDecisionRouter: boolean;
  enableTypedInterviewInviteRouter: boolean;
  enableTypedInterviewAnswerRouter: boolean;
  enableTypedCandidateReviewRouter: boolean;
  enableTypedManagerReviewRouter: boolean;
};

export type TypedFlowCoordinatorResult = {
  attempted: boolean;
  usedTypedPath: boolean;
  accepted: boolean;
  action: HellyAction | null;
  reason: TypedRouteReason | "OUT_OF_SCOPE";
  message: string;
};

type TypedCandidateReviewInput = {
  session: UserSessionState;
  userMessage: string;
  currentQuestion: string;
  currentQuestionIndex: number | null;
  hasFinalAnswers: boolean;
};

type TypedManagerReviewInput = {
  session: UserSessionState;
  userMessage: string;
  currentQuestion: string;
  currentQuestionIndex: number | null;
  hasFinalAnswers: boolean;
};

export class TypedFlowCoordinator {
  constructor(
    private readonly flags: TypedFlowFlags,
    private readonly actionRouterService: ActionRouterService | undefined,
    private readonly gatekeeperService: GatekeeperService | undefined,
    private readonly logger: Pick<Logger, "debug" | "warn">,
  ) {}

  async attemptRoleSelection(input: {
    session: UserSessionState;
    userMessage: string;
  }): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({ session: input.session });
    return this.runIfInScope(input.session.state === "role_selection", () =>
      runTypedRoute({
        enabled: this.flags.enableTypedRoleSelectionRouter,
        logPrefix: "typed_role_selection",
        userId: input.session.userId,
        runtimeState: input.session.state,
        userMessage: input.userMessage,
        expectedCanonicalState: HELLY_STATES.WAIT_ROLE,
        resolveCanonicalState: (runtimeState) =>
          this.resolveCanonicalStateForFlowStage(runtimeState, stage),
        acceptedActions: [
          HELLY_ACTIONS.SELECT_ROLE_CANDIDATE,
          HELLY_ACTIONS.SELECT_ROLE_MANAGER,
        ],
        actionRouterService: this.actionRouterService,
        gatekeeperService: this.gatekeeperService,
        logger: this.logger,
      }),
    );
  }

  async attemptContactIdentity(input: {
    session: UserSessionState;
    userMessage: string;
    awaitingContactChoice: boolean;
  }): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({
      session: input.session,
      context: {
        awaitingContactChoice: input.awaitingContactChoice,
      },
    });
    return this.runIfInScope(input.awaitingContactChoice, () =>
      runTypedRoute({
        enabled: this.flags.enableTypedContactRouter,
        logPrefix: "typed_contact",
        userId: input.session.userId,
        runtimeState: input.session.state,
        userMessage: input.userMessage,
        expectedCanonicalState: HELLY_STATES.WAIT_CONTACT,
        resolveCanonicalState: (runtimeState) =>
          this.resolveCanonicalStateForFlowStage(runtimeState, stage),
        acceptedActions: [
          HELLY_ACTIONS.SHARE_PHONE_TEXT,
          HELLY_ACTIONS.SHARE_CONTACT,
        ],
        actionRouterService: this.actionRouterService,
        gatekeeperService: this.gatekeeperService,
        logger: this.logger,
      }),
    );
  }

  async attemptCandidateCvIntake(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text" | "document" | "voice";
  }): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({ session: input.session });
    return this.runIfInScope(input.session.state === "waiting_resume", () =>
      runTypedRoute({
        enabled: this.flags.enableTypedCvRouter,
        logPrefix: "typed_cv",
        userId: input.session.userId,
        source: input.source,
        runtimeState: input.session.state,
        userMessage: input.userMessage,
        expectedCanonicalState: HELLY_STATES.C_WAIT_CV,
        resolveCanonicalState: (runtimeState) =>
          this.resolveCanonicalStateForFlowStage(runtimeState, stage),
        acceptedActions: [
          HELLY_ACTIONS.SUBMIT_CV,
          HELLY_ACTIONS.SUBMIT_TEXT,
          HELLY_ACTIONS.SUBMIT_FILE,
          HELLY_ACTIONS.SUBMIT_VOICE,
        ],
        actionRouterService: this.actionRouterService,
        gatekeeperService: this.gatekeeperService,
        logger: this.logger,
      }),
    );
  }

  async attemptCandidateMandatory(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text" | "location";
  }): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({ session: input.session });
    return this.runIfInScope(stage === FLOW_STAGES.CANDIDATE_MANDATORY, () =>
      runTypedRoute({
        enabled: this.flags.enableTypedCandidateMandatoryRouter,
        logPrefix: "typed_candidate_mandatory",
        userId: input.session.userId,
        source: input.source,
        runtimeState: input.session.state,
        userMessage: input.userMessage,
        expectedCanonicalState: HELLY_STATES.C_MANDATORY_QUESTIONNAIRE,
        resolveCanonicalState: (runtimeState) =>
          this.resolveCanonicalStateForFlowStage(runtimeState, stage),
        acceptedActions: [
          HELLY_ACTIONS.ANSWER_QUESTION,
          HELLY_ACTIONS.SUBMIT_TEXT,
          HELLY_ACTIONS.SHARE_LOCATION,
        ],
        actionRouterService: this.actionRouterService,
        gatekeeperService: this.gatekeeperService,
        logger: this.logger,
      }),
    );
  }

  async attemptManagerJdIntake(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text" | "document" | "voice";
  }): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({ session: input.session });
    return this.runIfInScope(input.session.state === "waiting_job", () =>
      runTypedRoute({
        enabled: this.flags.enableTypedJdRouter,
        logPrefix: "typed_jd",
        userId: input.session.userId,
        source: input.source,
        runtimeState: input.session.state,
        userMessage: input.userMessage,
        expectedCanonicalState: HELLY_STATES.HM_WAIT_JD,
        resolveCanonicalState: (runtimeState) =>
          this.resolveCanonicalStateForFlowStage(runtimeState, stage),
        acceptedActions: [
          HELLY_ACTIONS.SUBMIT_JD,
          HELLY_ACTIONS.SUBMIT_TEXT,
          HELLY_ACTIONS.SUBMIT_FILE,
          HELLY_ACTIONS.SUBMIT_VOICE,
          HELLY_ACTIONS.SUBMIT_VIDEO,
        ],
        actionRouterService: this.actionRouterService,
        gatekeeperService: this.gatekeeperService,
        logger: this.logger,
      }),
    );
  }

  async attemptManagerMandatory(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text";
  }): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({ session: input.session });
    return this.runIfInScope(stage === FLOW_STAGES.MANAGER_MANDATORY, () =>
      runTypedRoute({
        enabled: this.flags.enableTypedManagerMandatoryRouter,
        logPrefix: "typed_manager_mandatory",
        userId: input.session.userId,
        source: input.source,
        runtimeState: input.session.state,
        userMessage: input.userMessage,
        expectedCanonicalState: HELLY_STATES.HM_QUESTIONNAIRE,
        resolveCanonicalState: (runtimeState) =>
          this.resolveCanonicalStateForFlowStage(runtimeState, stage),
        acceptedActions: [
          HELLY_ACTIONS.ANSWER_QUESTION,
          HELLY_ACTIONS.SUBMIT_TEXT,
        ],
        actionRouterService: this.actionRouterService,
        gatekeeperService: this.gatekeeperService,
        logger: this.logger,
      }),
    );
  }

  async attemptCandidateDecision(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text";
  }): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({ session: input.session });
    return this.runIfInScope(
      stage === FLOW_STAGES.CANDIDATE_DECISION ||
      stage === FLOW_STAGES.INTERVIEW_INVITATION,
      () =>
        runTypedRoute({
          enabled: this.flags.enableTypedCandidateDecisionRouter,
          logPrefix: "typed_candidate_decision",
          userId: input.session.userId,
          source: input.source,
          runtimeState: input.session.state,
          userMessage: input.userMessage,
          expectedCanonicalState: HELLY_STATES.WAIT_CANDIDATE_DECISION,
          resolveCanonicalState: (runtimeState) =>
            this.resolveCanonicalStateForFlowStage(runtimeState, stage),
          acceptedActions: [
            HELLY_ACTIONS.YES,
            HELLY_ACTIONS.NO,
            HELLY_ACTIONS.SHARE_CONTACT,
          ],
          actionRouterService: this.actionRouterService,
          gatekeeperService: this.gatekeeperService,
          logger: this.logger,
        }),
    );
  }

  async attemptManagerDecision(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text";
  }): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({ session: input.session });
    return this.runIfInScope(stage === FLOW_STAGES.MANAGER_DECISION, () =>
      runTypedRoute({
        enabled: this.flags.enableTypedManagerDecisionRouter,
        logPrefix: "typed_manager_decision",
        userId: input.session.userId,
        source: input.source,
        runtimeState: input.session.state,
        userMessage: input.userMessage,
        expectedCanonicalState: HELLY_STATES.WAIT_MANAGER_DECISION,
        resolveCanonicalState: (runtimeState) =>
          this.resolveCanonicalStateForFlowStage(runtimeState, stage),
        acceptedActions: [
          HELLY_ACTIONS.YES,
          HELLY_ACTIONS.NO,
          HELLY_ACTIONS.SHARE_CONTACT,
        ],
        actionRouterService: this.actionRouterService,
        gatekeeperService: this.gatekeeperService,
        logger: this.logger,
      }),
    );
  }

  async attemptInterviewInvitation(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text";
  }): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({ session: input.session });
    return this.runIfInScope(stage === FLOW_STAGES.INTERVIEW_INVITATION, () =>
      runTypedRoute({
        enabled: this.flags.enableTypedInterviewInviteRouter,
        logPrefix: "typed_interview_invite",
        userId: input.session.userId,
        source: input.source,
        runtimeState: input.session.state,
        userMessage: input.userMessage,
        expectedCanonicalState: HELLY_STATES.WAIT_CANDIDATE_DECISION,
        resolveCanonicalState: (runtimeState) =>
          this.resolveCanonicalStateForFlowStage(runtimeState, stage),
        acceptedActions: [
          HELLY_ACTIONS.YES,
          HELLY_ACTIONS.NO,
        ],
        actionRouterService: this.actionRouterService,
        gatekeeperService: this.gatekeeperService,
        logger: this.logger,
      }),
    );
  }

  async attemptInterviewAnswer(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text" | "voice";
  }): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({ session: input.session });

    if (input.session.state === "interviewing_candidate") {
      return this.runIfInScope(stage === FLOW_STAGES.INTERVIEW_ANSWER, () =>
        runTypedRoute({
          enabled: this.flags.enableTypedInterviewAnswerRouter,
          logPrefix: "typed_interview_answer",
          userId: input.session.userId,
          source: input.source,
          runtimeState: input.session.state,
          userMessage: input.userMessage,
          expectedCanonicalState: HELLY_STATES.C_INTERVIEW_IN_PROGRESS,
          resolveCanonicalState: (runtimeState) =>
            this.resolveCanonicalStateForFlowStage(runtimeState, stage),
          acceptedActions: [
            HELLY_ACTIONS.ANSWER_QUESTION,
            HELLY_ACTIONS.SUBMIT_TEXT,
            HELLY_ACTIONS.SUBMIT_VOICE,
            HELLY_ACTIONS.SKIP_QUESTION,
            HELLY_ACTIONS.FINISH_INTERVIEW,
          ],
          actionRouterService: this.actionRouterService,
          gatekeeperService: this.gatekeeperService,
          logger: this.logger,
        }),
      );
    }

    if (input.session.state === "interviewing_manager") {
      return this.runIfInScope(stage === FLOW_STAGES.INTERVIEW_ANSWER, () =>
        runTypedRoute({
          enabled: this.flags.enableTypedInterviewAnswerRouter,
          logPrefix: "typed_interview_answer",
          userId: input.session.userId,
          source: input.source,
          runtimeState: input.session.state,
          userMessage: input.userMessage,
          expectedCanonicalState: HELLY_STATES.HM_INTERVIEW_IN_PROGRESS,
          resolveCanonicalState: (runtimeState) =>
            this.resolveCanonicalStateForFlowStage(runtimeState, stage),
          acceptedActions: [
            HELLY_ACTIONS.ANSWER_QUESTION,
            HELLY_ACTIONS.SUBMIT_TEXT,
            HELLY_ACTIONS.SUBMIT_VOICE,
            HELLY_ACTIONS.SKIP_QUESTION,
            HELLY_ACTIONS.FINISH_INTERVIEW,
          ],
          actionRouterService: this.actionRouterService,
          gatekeeperService: this.gatekeeperService,
          logger: this.logger,
        }),
      );
    }

    return {
      attempted: false,
      usedTypedPath: false,
      accepted: false,
      action: null,
      reason: "OUT_OF_SCOPE",
      message: DEFAULT_FALLBACK_MESSAGE,
    };
  }

  async attemptCandidateReview(input: TypedCandidateReviewInput): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({
      session: input.session,
      context: {
        currentQuestionText: input.currentQuestion,
        currentQuestionIndex: input.currentQuestionIndex,
        hasFinalAnswers: input.hasFinalAnswers,
      },
    });
    return this.runIfInScope(input.session.state === "interviewing_candidate", () =>
      runTypedRoute({
        enabled: this.flags.enableTypedCandidateReviewRouter,
        logPrefix: "typed_candidate_review",
        userId: input.session.userId,
        source: "text",
        runtimeState: input.session.state,
        userMessage: input.userMessage,
        expectedCanonicalState: HELLY_STATES.C_SUMMARY_REVIEW,
        resolveCanonicalState: (runtimeState) =>
          this.resolveCanonicalStateForFlowStage(runtimeState, stage),
        acceptedActions: [
          HELLY_ACTIONS.APPROVE,
          HELLY_ACTIONS.EDIT,
          HELLY_ACTIONS.SUBMIT_TEXT,
        ],
        actionRouterService: this.actionRouterService,
        gatekeeperService: this.gatekeeperService,
        logger: this.logger,
      }),
    );
  }

  async attemptManagerReview(input: TypedManagerReviewInput): Promise<TypedFlowCoordinatorResult> {
    const stage = resolveFlowStage({
      session: input.session,
      context: {
        currentQuestionText: input.currentQuestion,
        currentQuestionIndex: input.currentQuestionIndex,
        hasFinalAnswers: input.hasFinalAnswers,
      },
    });
    return this.runIfInScope(input.session.state === "interviewing_manager", () =>
      runTypedRoute({
        enabled: this.flags.enableTypedManagerReviewRouter,
        logPrefix: "typed_manager_review",
        userId: input.session.userId,
        source: "text",
        runtimeState: input.session.state,
        userMessage: input.userMessage,
        expectedCanonicalState: HELLY_STATES.HM_JD_REVIEW,
        resolveCanonicalState: (runtimeState) =>
          this.resolveCanonicalStateForFlowStage(runtimeState, stage),
        acceptedActions: [
          HELLY_ACTIONS.APPROVE,
          HELLY_ACTIONS.EDIT,
          HELLY_ACTIONS.SUBMIT_TEXT,
        ],
        actionRouterService: this.actionRouterService,
        gatekeeperService: this.gatekeeperService,
        logger: this.logger,
      }),
    );
  }

  private async runIfInScope(
    inScope: boolean,
    execute: () => Promise<RunTypedRouteResult>,
  ): Promise<TypedFlowCoordinatorResult> {
    if (!inScope) {
      return {
        attempted: false,
        usedTypedPath: false,
        accepted: false,
        action: null,
        reason: "OUT_OF_SCOPE",
        message: DEFAULT_FALLBACK_MESSAGE,
      };
    }
    const result = await execute();
    return {
      attempted: true,
      ...result,
    };
  }

  private resolveCanonicalStateForFlowStage(
    runtimeState: string,
    stage: FlowStage,
  ) {
    const canonicalState = mapRuntimeStateToHellyState(runtimeState);
    if (!canonicalState) {
      return null;
    }
    if (
      stage === FLOW_STAGES.CONTACT_IDENTITY &&
      canonicalState === HELLY_STATES.WAIT_ROLE
    ) {
      return HELLY_STATES.WAIT_CONTACT;
    }
    if (
      stage === FLOW_STAGES.CANDIDATE_REVIEW &&
      canonicalState === HELLY_STATES.C_INTERVIEW_IN_PROGRESS
    ) {
      return HELLY_STATES.C_SUMMARY_REVIEW;
    }
    if (
      stage === FLOW_STAGES.MANAGER_REVIEW &&
      canonicalState === HELLY_STATES.HM_INTERVIEW_IN_PROGRESS
    ) {
      return HELLY_STATES.HM_JD_REVIEW;
    }
    return canonicalState;
  }
}
