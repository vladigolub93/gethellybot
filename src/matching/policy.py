from __future__ import annotations

MATCH_BATCH_SIZE = 3
MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY = 10
MAX_ACTIVE_APPLICATIONS_PER_CANDIDATE = 10
MAX_ACTIVE_INTERVIEWS_PER_CANDIDATE = 1

MATCH_STATUS_FILTERED_OUT = "filtered_out"
MATCH_STATUS_SHORTLISTED = "shortlisted"
MATCH_STATUS_MANAGER_DECISION_PENDING = "manager_decision_pending"
MATCH_STATUS_CANDIDATE_DECISION_PENDING = "candidate_decision_pending"
MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED = "manager_interview_requested"
MATCH_STATUS_MANAGER_SKIPPED = "manager_skipped"
MATCH_STATUS_CANDIDATE_APPLIED = "candidate_applied"
MATCH_STATUS_CANDIDATE_SKIPPED = "candidate_skipped"
MATCH_STATUS_INTERVIEW_QUEUED = "interview_queued"
MATCH_STATUS_INVITED = "invited"
MATCH_STATUS_ACCEPTED = "accepted"
MATCH_STATUS_INTERVIEW_COMPLETED = "interview_completed"
MATCH_STATUS_CANDIDATE_DECLINED_INTERVIEW = "candidate_declined_interview"
MATCH_STATUS_MANAGER_REVIEW = "manager_review"
MATCH_STATUS_APPROVED = "approved"
MATCH_STATUS_REJECTED = "rejected"
MATCH_STATUS_AUTO_REJECTED = "auto_rejected"
MATCH_STATUS_EXPIRED = "expired"
MATCH_STATUS_SKIPPED = "skipped"

VACANCY_INTERVIEW_PIPELINE_STATUSES = frozenset(
    {
        MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED,
        MATCH_STATUS_CANDIDATE_DECISION_PENDING,
        MATCH_STATUS_INTERVIEW_QUEUED,
        MATCH_STATUS_INVITED,
        MATCH_STATUS_ACCEPTED,
        MATCH_STATUS_INTERVIEW_COMPLETED,
        MATCH_STATUS_MANAGER_REVIEW,
    }
)

CANDIDATE_ACTIVE_APPLICATION_STATUSES = frozenset(
    {
        MATCH_STATUS_CANDIDATE_APPLIED,
        MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED,
        MATCH_STATUS_CANDIDATE_DECISION_PENDING,
        MATCH_STATUS_INTERVIEW_QUEUED,
        MATCH_STATUS_INVITED,
        MATCH_STATUS_ACCEPTED,
        MATCH_STATUS_INTERVIEW_COMPLETED,
        MATCH_STATUS_MANAGER_REVIEW,
    }
)

PRE_INTERVIEW_MANAGER_REVIEW_STATUSES = frozenset(
    {
        MATCH_STATUS_MANAGER_DECISION_PENDING,
        MATCH_STATUS_CANDIDATE_APPLIED,
    }
)

PRE_INTERVIEW_CANDIDATE_REVIEW_STATUSES = frozenset(
    {
        MATCH_STATUS_CANDIDATE_DECISION_PENDING,
    }
)

ACTIVE_MATCH_STATUSES = frozenset(
    set(
        {
            MATCH_STATUS_SHORTLISTED,
            MATCH_STATUS_MANAGER_DECISION_PENDING,
            MATCH_STATUS_INVITED,
            MATCH_STATUS_ACCEPTED,
            MATCH_STATUS_INTERVIEW_COMPLETED,
            MATCH_STATUS_MANAGER_REVIEW,
        }
    )
    | set(PRE_INTERVIEW_MANAGER_REVIEW_STATUSES)
    | set(PRE_INTERVIEW_CANDIDATE_REVIEW_STATUSES)
    | set(VACANCY_INTERVIEW_PIPELINE_STATUSES)
    | {MATCH_STATUS_CANDIDATE_APPLIED}
)

LEGACY_ACTIVE_MATCH_STATUSES = ACTIVE_MATCH_STATUSES


def available_vacancy_interview_slots(
    active_count: int,
    *,
    max_active: int = MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY,
) -> int:
    return max(max_active - max(active_count, 0), 0)


def next_manager_review_batch_size(
    active_count: int,
    *,
    batch_size: int = MATCH_BATCH_SIZE,
    max_active: int = MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY,
) -> int:
    return min(batch_size, available_vacancy_interview_slots(active_count, max_active=max_active))


def available_candidate_application_slots(
    active_count: int,
    *,
    max_active: int = MAX_ACTIVE_APPLICATIONS_PER_CANDIDATE,
) -> int:
    return max(max_active - max(active_count, 0), 0)


def next_candidate_vacancy_batch_size(
    active_count: int,
    *,
    batch_size: int = MATCH_BATCH_SIZE,
    max_active: int = MAX_ACTIVE_APPLICATIONS_PER_CANDIDATE,
) -> int:
    return min(batch_size, available_candidate_application_slots(active_count, max_active=max_active))


def should_queue_interview(*, active_interview_count: int) -> bool:
    return active_interview_count >= MAX_ACTIVE_INTERVIEWS_PER_CANDIDATE
