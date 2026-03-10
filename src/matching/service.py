from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.llm.service import safe_rerank_candidates
from src.matching.filters import evaluate_hard_filters
from src.matching.scoring import (
    compute_deterministic_score,
    compute_embedding_score,
    compute_vector_similarity,
    has_embedding_values,
)


class MatchingService:
    FINAL_SHORTLIST_LIMIT = 6
    DETERMINISTIC_POOL_LIMIT = 10
    VECTOR_RETRIEVAL_LIMIT = 50

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
        vacancy_embedding = getattr(vacancy_version, "semantic_embedding", None)

        if trigger_candidate_profile_id is not None:
            candidate_profiles = []
            candidate = self.candidates.get_by_id(trigger_candidate_profile_id)
            if candidate is not None and candidate.state == "READY" and candidate.deleted_at is None:
                candidate_profiles.append(candidate)
            preloaded_candidates = None
        else:
            preloaded_candidates = None
            if has_embedding_values(vacancy_embedding):
                preloaded_candidates = self.candidates.list_top_similar_ready_profiles(
                    embedding=list(vacancy_embedding),
                    limit=self.VECTOR_RETRIEVAL_LIMIT,
                )
                candidate_profiles = [item["candidate"] for item in preloaded_candidates]
            else:
                candidate_profiles = self.candidates.get_ready_profiles()

        run = self.matching.create_run(
            vacancy_id=vacancy.id,
            trigger_type=trigger_type,
            trigger_candidate_profile_id=trigger_candidate_profile_id,
            payload_json={
                "mode": "vector_plus_deterministic_plus_llm_rerank"
                if preloaded_candidates is not None
                else "deterministic_plus_llm_rerank"
            },
        )

        scored = []
        hard_filtered_count = 0
        vacancy_skills = vacancy.primary_tech_stack_json or []
        preloaded_by_candidate_id = {
            item["candidate"].id: item
            for item in (preloaded_candidates or [])
        }

        for candidate in candidate_profiles:
            preloaded = preloaded_by_candidate_id.get(candidate.id)
            candidate_version = (
                preloaded["candidate_version"]
                if preloaded is not None
                else self.candidates.get_current_version(candidate)
            )
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
            if preloaded is not None:
                embedding_score = preloaded["embedding_score"]
            else:
                embedding_score = compute_vector_similarity(
                    getattr(candidate_version, "semantic_embedding", None),
                    vacancy_embedding,
                )
                if embedding_score is None:
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

        deterministic_pool = scored[: self.DETERMINISTIC_POOL_LIMIT]
        non_shortlisted = scored[self.DETERMINISTIC_POOL_LIMIT :]
        rerank_input = [
            {
                "candidate_ref": str(item["candidate"].id),
                "candidate_profile_id": item["candidate"].id,
                "candidate_profile_version_id": item["candidate_version"].id,
                "candidate_summary": item["candidate_version"].summary_json or {},
                "embedding_score": item["embedding_score"],
                "deterministic_score": item["deterministic_score"],
                "score_breakdown": item["score_breakdown"],
            }
            for item in deterministic_pool
        ]
        rerank_result = safe_rerank_candidates(
            self.session,
            vacancy=vacancy,
            shortlisted_candidates=rerank_input,
        )
        reranked_candidates = rerank_result.payload.get("ranked_candidates") or []
        rerank_map = {item["candidate_ref"]: item for item in reranked_candidates}
        reranked_pool = sorted(
            deterministic_pool,
            key=lambda item: rerank_map.get(str(item["candidate"].id), {}).get(
                "rank",
                self.DETERMINISTIC_POOL_LIMIT + 1,
            ),
        )
        final_shortlist = reranked_pool[: self.FINAL_SHORTLIST_LIMIT]
        llm_filtered = reranked_pool[self.FINAL_SHORTLIST_LIMIT :]

        for rank, item in enumerate(final_shortlist, start=1):
            rerank_item = rerank_map.get(str(item["candidate"].id), {})
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
                llm_rank_score=rerank_item.get("fit_score"),
                llm_rank_position=rank,
                rationale_json={
                    "stage": "llm_rerank_shortlist",
                    "score_breakdown": item["score_breakdown"],
                    "llm_rationale": rerank_item.get("rationale"),
                },
            )

        for item in llm_filtered:
            rerank_item = rerank_map.get(str(item["candidate"].id), {})
            self.matching.create_match(
                matching_run_id=run.id,
                vacancy_id=vacancy.id,
                vacancy_version_id=vacancy_version.id,
                candidate_profile_id=item["candidate"].id,
                candidate_profile_version_id=item["candidate_version"].id,
                status="filtered_out",
                hard_filter_passed=True,
                filter_reason_codes_json=["below_llm_rerank_cutoff"],
                embedding_score=item["embedding_score"],
                deterministic_score=item["deterministic_score"],
                llm_rank_score=rerank_item.get("fit_score"),
                llm_rank_position=rerank_item.get("rank"),
                rationale_json={
                    "stage": "llm_rerank",
                    "score_breakdown": item["score_breakdown"],
                    "llm_rationale": rerank_item.get("rationale"),
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
            shortlisted_count=len(final_shortlist),
            payload_json={
                "mode": "vector_plus_deterministic_plus_llm_rerank"
                if preloaded_candidates is not None
                else "deterministic_plus_llm_rerank",
                "candidate_pool_count": len(candidate_profiles),
                "hard_filtered_count": hard_filtered_count,
                "vector_retrieval_used": preloaded_candidates is not None,
                "vector_retrieval_limit": self.VECTOR_RETRIEVAL_LIMIT if preloaded_candidates is not None else None,
                "deterministic_pool_count": len(deterministic_pool),
                "shortlisted_count": len(final_shortlist),
                "llm_prompt_version": rerank_result.prompt_version,
            },
        )
        return {
            "matching_run_id": str(run.id),
            "vacancy_id": str(vacancy.id),
            "candidate_pool_count": len(candidate_profiles),
            "hard_filtered_count": hard_filtered_count,
            "shortlisted_count": len(final_shortlist),
        }
