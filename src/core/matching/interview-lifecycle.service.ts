import { MATCHING_INVARIANTS } from "./matching-invariants";
import { INTERVIEW_STATUSES, InterviewStatus } from "./interview-statuses";

export type InterviewLifecycleAction =
  | "START_INTERVIEW"
  | "MARK_IN_PROGRESS"
  | "COMPLETE_INTERVIEW";

const INTERVIEW_TRANSITIONS: Record<
  InterviewLifecycleAction,
  {
    from: InterviewStatus[];
    to: InterviewStatus;
  }
> = {
  START_INTERVIEW: {
    from: [INTERVIEW_STATUSES.INVITED],
    to: INTERVIEW_STATUSES.STARTED,
  },
  MARK_IN_PROGRESS: {
    from: [INTERVIEW_STATUSES.STARTED],
    to: INTERVIEW_STATUSES.IN_PROGRESS,
  },
  COMPLETE_INTERVIEW: {
    from: [INTERVIEW_STATUSES.STARTED, INTERVIEW_STATUSES.IN_PROGRESS],
    to: INTERVIEW_STATUSES.COMPLETED,
  },
};

export class InterviewLifecycleTransitionError extends Error {
  constructor(
    public readonly action: InterviewLifecycleAction,
    public readonly from: InterviewStatus,
    public readonly allowedFrom: InterviewStatus[],
  ) {
    super(
      `Invalid interview transition for ${action}: ${from} -> expected one of [${allowedFrom.join(", ")}]`,
    );
  }
}

/**
 * Canonical interview lifecycle domain service.
 *
 * Pure domain logic only:
 * - no DB
 * - no router
 * - no runtime state writes
 */
export class InterviewLifecycleService {
  startInterview(currentStatus: InterviewStatus): InterviewStatus {
    return this.transitionOrThrow("START_INTERVIEW", currentStatus);
  }

  markInProgress(currentStatus: InterviewStatus): InterviewStatus {
    return this.transitionOrThrow("MARK_IN_PROGRESS", currentStatus);
  }

  completeInterview(currentStatus: InterviewStatus): InterviewStatus {
    return this.transitionOrThrow("COMPLETE_INTERVIEW", currentStatus);
  }

  tryTransition(
    action: InterviewLifecycleAction,
    currentStatus: InterviewStatus,
  ): InterviewStatus | null {
    const rule = INTERVIEW_TRANSITIONS[action];
    return rule.from.includes(currentStatus) ? rule.to : null;
  }

  getTransitionTable(): Readonly<typeof INTERVIEW_TRANSITIONS> {
    return INTERVIEW_TRANSITIONS;
  }

  private transitionOrThrow(
    action: InterviewLifecycleAction,
    currentStatus: InterviewStatus,
  ): InterviewStatus {
    const rule = INTERVIEW_TRANSITIONS[action];
    if (!rule.from.includes(currentStatus)) {
      throw new InterviewLifecycleTransitionError(action, currentStatus, rule.from);
    }

    if (!MATCHING_INVARIANTS.REQUIRE_LIFECYCLE_CONSISTENCY) {
      return rule.to;
    }
    return rule.to;
  }
}

export { INTERVIEW_TRANSITIONS };
