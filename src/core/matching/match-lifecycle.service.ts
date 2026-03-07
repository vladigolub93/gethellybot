import { MATCHING_INVARIANTS } from "./matching-invariants";
import { MATCH_STATUSES, MatchStatus } from "./match-statuses";

export type MatchLifecycleAction =
  | "CREATE_MATCH"
  | "INVITE_CANDIDATE"
  | "CANDIDATE_ACCEPTS_MATCH"
  | "CANDIDATE_DECLINES_MATCH"
  | "START_INTERVIEW"
  | "COMPLETE_INTERVIEW"
  | "SEND_TO_MANAGER"
  | "MANAGER_APPROVES_CANDIDATE"
  | "MANAGER_REJECTS_CANDIDATE";

const MATCH_TRANSITIONS: Record<
  MatchLifecycleAction,
  {
    from: MatchStatus[];
    to: MatchStatus;
  }
> = {
  CREATE_MATCH: {
    from: [MATCH_STATUSES.PROPOSED],
    to: MATCH_STATUSES.PROPOSED,
  },
  INVITE_CANDIDATE: {
    from: [MATCH_STATUSES.PROPOSED],
    to: MATCH_STATUSES.INVITED,
  },
  CANDIDATE_ACCEPTS_MATCH: {
    from: [MATCH_STATUSES.INVITED],
    to: MATCH_STATUSES.INTERVIEW_STARTED,
  },
  CANDIDATE_DECLINES_MATCH: {
    from: [MATCH_STATUSES.INVITED],
    to: MATCH_STATUSES.DECLINED,
  },
  START_INTERVIEW: {
    from: [MATCH_STATUSES.INVITED],
    to: MATCH_STATUSES.INTERVIEW_STARTED,
  },
  COMPLETE_INTERVIEW: {
    from: [MATCH_STATUSES.INTERVIEW_STARTED],
    to: MATCH_STATUSES.INTERVIEW_COMPLETED,
  },
  SEND_TO_MANAGER: {
    from: [MATCH_STATUSES.INTERVIEW_COMPLETED],
    to: MATCH_STATUSES.SENT_TO_MANAGER,
  },
  MANAGER_APPROVES_CANDIDATE: {
    from: [MATCH_STATUSES.SENT_TO_MANAGER],
    to: MATCH_STATUSES.APPROVED,
  },
  MANAGER_REJECTS_CANDIDATE: {
    from: [MATCH_STATUSES.SENT_TO_MANAGER],
    to: MATCH_STATUSES.REJECTED,
  },
};

export class MatchLifecycleTransitionError extends Error {
  constructor(
    public readonly action: MatchLifecycleAction,
    public readonly from: MatchStatus,
    public readonly allowedFrom: MatchStatus[],
  ) {
    super(
      `Invalid match transition for ${action}: ${from} -> expected one of [${allowedFrom.join(", ")}]`,
    );
  }
}

/**
 * Canonical match lifecycle domain service.
 *
 * Pure domain logic only:
 * - no DB
 * - no router
 * - no runtime state writes
 */
export class MatchLifecycleService {
  createMatch(currentStatus: MatchStatus): MatchStatus {
    return this.transitionOrThrow("CREATE_MATCH", currentStatus);
  }

  inviteCandidate(currentStatus: MatchStatus): MatchStatus {
    return this.transitionOrThrow("INVITE_CANDIDATE", currentStatus);
  }

  candidateAcceptsMatch(currentStatus: MatchStatus): MatchStatus {
    return this.transitionOrThrow("CANDIDATE_ACCEPTS_MATCH", currentStatus);
  }

  candidateDeclinesMatch(currentStatus: MatchStatus): MatchStatus {
    return this.transitionOrThrow("CANDIDATE_DECLINES_MATCH", currentStatus);
  }

  startInterview(currentStatus: MatchStatus): MatchStatus {
    return this.transitionOrThrow("START_INTERVIEW", currentStatus);
  }

  completeInterview(currentStatus: MatchStatus): MatchStatus {
    return this.transitionOrThrow("COMPLETE_INTERVIEW", currentStatus);
  }

  sendToManager(currentStatus: MatchStatus): MatchStatus {
    return this.transitionOrThrow("SEND_TO_MANAGER", currentStatus);
  }

  managerApprovesCandidate(currentStatus: MatchStatus): MatchStatus {
    return this.transitionOrThrow("MANAGER_APPROVES_CANDIDATE", currentStatus);
  }

  managerRejectsCandidate(currentStatus: MatchStatus): MatchStatus {
    return this.transitionOrThrow("MANAGER_REJECTS_CANDIDATE", currentStatus);
  }

  tryTransition(
    action: MatchLifecycleAction,
    currentStatus: MatchStatus,
  ): MatchStatus | null {
    const rule = MATCH_TRANSITIONS[action];
    return rule.from.includes(currentStatus) ? rule.to : null;
  }

  getTransitionTable(): Readonly<typeof MATCH_TRANSITIONS> {
    return MATCH_TRANSITIONS;
  }

  private transitionOrThrow(
    action: MatchLifecycleAction,
    currentStatus: MatchStatus,
  ): MatchStatus {
    const rule = MATCH_TRANSITIONS[action];
    if (!rule.from.includes(currentStatus)) {
      throw new MatchLifecycleTransitionError(action, currentStatus, rule.from);
    }
    this.assertInvariants(action, currentStatus, rule.to);
    return rule.to;
  }

  private assertInvariants(
    action: MatchLifecycleAction,
    from: MatchStatus,
    to: MatchStatus,
  ): void {
    if (!MATCHING_INVARIANTS.REQUIRE_LIFECYCLE_CONSISTENCY) {
      return;
    }

    if (
      action === "SEND_TO_MANAGER" &&
      from !== MATCH_STATUSES.INTERVIEW_COMPLETED
    ) {
      throw new MatchLifecycleTransitionError(action, from, [MATCH_STATUSES.INTERVIEW_COMPLETED]);
    }

    if (
      MATCHING_INVARIANTS.EVALUATION_REQUIRES_COMPLETED_INTERVIEW &&
      to === MATCH_STATUSES.SENT_TO_MANAGER &&
      from !== MATCH_STATUSES.INTERVIEW_COMPLETED
    ) {
      throw new MatchLifecycleTransitionError(action, from, [MATCH_STATUSES.INTERVIEW_COMPLETED]);
    }
  }
}

export { MATCH_TRANSITIONS };
