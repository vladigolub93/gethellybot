from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.matching.filters import evaluate_hard_filters
from src.matching.scoring import compute_deterministic_score, compute_embedding_score


class MatchingService:
    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.matching = MatchingRepository(session)

    def execute_for_vacancy(
        self,
        *,
        vacancy_id,
        trigger_type: str,
        trigger_candidate_profile_id=None,
    ) -> dict:
        vacancy = self.vacancies.get_by_id(vacancy_id)
        if vacancy is None:
            raise ValueError("Vacancy not found for matching.")
        vacancy_version = self.vacancies.get_current_version(vacancy)
        if vacancy_version is None:
            raise ValueError("Vacancy current version not found for matching.")

        if trigger_candidate_profile_id is not None:
            candidate_profiles = []
            candidate = self.candidates.get_by_id(trigger_candidate_profile_id)
            if candidate is not None and candidate.state == "READY" and candidate.deleted_at is None:
                candidate_profiles.append(candidate)
        else:
            candidate_profiles = self.candidates.get_ready_profiles()

        run = self.matching.create_run(
            vacancy_id=vacancy.id,
            trigger_type=trigger_type,
            trigger_candidate_profile_id=trigger_candidate_profile_id,
            payload_json={"mode": "baseline_deterministic_matching"},
        )

        scored = []
        hard_filtered_count = 0
        vacancy_skills = vacancy.primary_tech_stack_json or []

        for candidate in candidate_profiles:
            candidate_version = self.candidates.get_current_version(candidate)
            if candidate_version is None:
                continue

            filter_reasons = evaluate_hard_filters(candidate, vacancy)
            if filter_reasons:
                hard_filtered_count += 1
                self.matching.create_match(
                    matching_run_id=run.id,
                    vacancy_id=vacancy.id,
                    vacancy_version_id=vacancy_version.id,
                    candidate_profile_id=candidate.id,
                    candidate_profile_version_id=candidate_version.id,
                    status="filtered_out",
                    hard_filter_passed=False,
                    filter_reason_codes_json=filter_reasons,
                    rationale_json={"stage": "hard_filters"},
                )
                continue

            candidate_summary = candidate_version.summary_json or {}
            candidate_skills = candidate_summary.get("skills") or []
            candidate_years_experience = candidate_summary.get("years_experience")
            embedding_score = compute_embedding_score(candidate_skills, vacancy_skills)
            deterministic_score, score_breakdown = compute_deterministic_score(
                candidate_skills=candidate_skills,
                vacancy_skills=vacancy_skills,
                candidate_years_experience=candidate_years_experience,
                vacancy_seniority=vacancy.seniority_normalized,
                candidate_seniority=candidate.seniority_normalized,
            )
            scored.append(
                {
                    "candidate": candidate,
                    "candidate_version": candidate_version,
                    "embedding_score": embedding_score,
                    "deterministic_score": deterministic_score,
                    "score_breakdown": score_breakdown,
                }
            )

        scored.sort(
            key=lambda item: (item["deterministic_score"], item["embedding_score"]),
            reverse=True,
        )

        shortlisted = scored[:10]
        non_shortlisted = scored[10:]

        for rank, item in enumerate(shortlisted, start=1):
            self.matching.create_match(
                matching_run_id=run.id,
                vacancy_id=vacancy.id,
                vacancy_version_id=vacancy_version.id,
                candidate_profile_id=item["candidate"].id,
                candidate_profile_version_id=item["candidate_version"].id,
                status="shortlisted",
                hard_filter_passed=True,
                filter_reason_codes_json=[],
                embedding_score=item["embedding_score"],
                deterministic_score=item["deterministic_score"],
                llm_rank_position=rank,
                rationale_json={
                    "stage": "deterministic_shortlist",
                    "score_breakdown": item["score_breakdown"],
                },
            )

        for item in non_shortlisted:
            self.matching.create_match(
                matching_run_id=run.id,
                vacancy_id=vacancy.id,
                vacancy_version_id=vacancy_version.id,
                candidate_profile_id=item["candidate"].id,
                candidate_profile_version_id=item["candidate_version"].id,
                status="filtered_out",
                hard_filter_passed=True,
                filter_reason_codes_json=["below_deterministic_cutoff"],
                embedding_score=item["embedding_score"],
                deterministic_score=item["deterministic_score"],
                rationale_json={
                    "stage": "deterministic_scoring",
                    "score_breakdown": item["score_breakdown"],
                },
            )

        self.matching.update_run_counts(
            run,
            candidate_pool_count=len(candidate_profiles),
            hard_filtered_count=hard_filtered_count,
            shortlisted_count=len(shortlisted),
            payload_json={
                "mode": "baseline_deterministic_matching",
                "candidate_pool_count": len(candidate_profiles),
                "hard_filtered_count": hard_filtered_count,
                "shortlisted_count": len(shortlisted),
            },
        )
        return {
            "matching_run_id": str(run.id),
            "vacancy_id": str(vacancy.id),
            "candidate_pool_count": len(candidate_profiles),
            "hard_filtered_count": hard_filtered_count,
            "shortlisted_count": len(shortlisted),
        }
