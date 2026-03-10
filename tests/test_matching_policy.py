from src.matching.policy import (
    CANDIDATE_ACTIVE_APPLICATION_STATUSES,
    LEGACY_ACTIVE_MATCH_STATUSES,
    MATCH_BATCH_SIZE,
    MATCH_STATUS_ACCEPTED,
    MATCH_STATUS_CANDIDATE_APPLIED,
    MATCH_STATUS_CANDIDATE_DECISION_PENDING,
    MATCH_STATUS_INTERVIEW_QUEUED,
    MATCH_STATUS_INVITED,
    MATCH_STATUS_MANAGER_DECISION_PENDING,
    MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED,
    MATCH_STATUS_MANAGER_REVIEW,
    MATCH_STATUS_SHORTLISTED,
    MAX_ACTIVE_APPLICATIONS_PER_CANDIDATE,
    MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY,
    PRE_INTERVIEW_CANDIDATE_REVIEW_STATUSES,
    PRE_INTERVIEW_MANAGER_REVIEW_STATUSES,
    VACANCY_INTERVIEW_PIPELINE_STATUSES,
    available_candidate_application_slots,
    available_vacancy_interview_slots,
    next_candidate_vacancy_batch_size,
    next_manager_review_batch_size,
    should_queue_interview,
)


def test_next_manager_review_batch_size_respects_vacancy_cap() -> None:
    assert next_manager_review_batch_size(0) == MATCH_BATCH_SIZE
    assert next_manager_review_batch_size(8) == 2
    assert next_manager_review_batch_size(MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY) == 0


def test_next_candidate_vacancy_batch_size_respects_candidate_cap() -> None:
    assert next_candidate_vacancy_batch_size(0) == MATCH_BATCH_SIZE
    assert next_candidate_vacancy_batch_size(9) == 1
    assert next_candidate_vacancy_batch_size(MAX_ACTIVE_APPLICATIONS_PER_CANDIDATE) == 0


def test_available_slot_helpers_never_return_negative() -> None:
    assert available_vacancy_interview_slots(99) == 0
    assert available_candidate_application_slots(99) == 0


def test_should_queue_interview_after_one_active_session() -> None:
    assert should_queue_interview(active_interview_count=0) is False
    assert should_queue_interview(active_interview_count=1) is True
    assert should_queue_interview(active_interview_count=2) is True


def test_policy_status_groups_cover_current_and_target_flows() -> None:
    assert MATCH_STATUS_MANAGER_DECISION_PENDING in PRE_INTERVIEW_MANAGER_REVIEW_STATUSES
    assert MATCH_STATUS_CANDIDATE_APPLIED in PRE_INTERVIEW_MANAGER_REVIEW_STATUSES
    assert MATCH_STATUS_CANDIDATE_DECISION_PENDING in PRE_INTERVIEW_CANDIDATE_REVIEW_STATUSES

    assert MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED in VACANCY_INTERVIEW_PIPELINE_STATUSES
    assert MATCH_STATUS_INVITED in VACANCY_INTERVIEW_PIPELINE_STATUSES
    assert MATCH_STATUS_ACCEPTED in VACANCY_INTERVIEW_PIPELINE_STATUSES
    assert MATCH_STATUS_INTERVIEW_QUEUED in VACANCY_INTERVIEW_PIPELINE_STATUSES
    assert MATCH_STATUS_MANAGER_REVIEW in VACANCY_INTERVIEW_PIPELINE_STATUSES

    assert MATCH_STATUS_CANDIDATE_APPLIED in CANDIDATE_ACTIVE_APPLICATION_STATUSES
    assert MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED in CANDIDATE_ACTIVE_APPLICATION_STATUSES
    assert MATCH_STATUS_INVITED in CANDIDATE_ACTIVE_APPLICATION_STATUSES

    assert MATCH_STATUS_SHORTLISTED in LEGACY_ACTIVE_MATCH_STATUSES
    assert MATCH_STATUS_INVITED in LEGACY_ACTIVE_MATCH_STATUSES
    assert MATCH_STATUS_ACCEPTED in LEGACY_ACTIVE_MATCH_STATUSES
    assert MATCH_STATUS_MANAGER_REVIEW in LEGACY_ACTIVE_MATCH_STATUSES
