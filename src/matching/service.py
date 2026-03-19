from __future__ import annotations

from src.candidate_profile.skills_inventory import (
    candidate_version_full_hard_skills,
    extract_full_hard_skills,
    normalize_skill_list,
)
from src.candidate_profile.work_formats import candidate_work_formats, display_work_formats
from src.candidate_profile.states import CANDIDATE_READY_LIKE_STATES
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.llm.service import safe_rerank_candidates
from src.matching.filters import evaluate_hard_filters
from src.matching.scoring import (
    build_gap_signals,
    classify_fit_band,
    compute_deterministic_score,
    compute_embedding_score,
    compute_skill_seed_score,
    compute_vector_similarity,
    fit_band_label,
    has_embedding_values,
)


class MatchingService:
    FINAL_SHORTLIST_LIMIT = 6
    DETERMINISTIC_POOL_LIMIT = 10
    VECTOR_RETRIEVAL_LIMIT = 50
    HYBRID_SKILL_POOL_LIMIT = 50

    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.matching = MatchingRepository(session)

    @staticmethod
    def _recent_feedback_categories(context_json: dict | None, *, key: str) -> list[str]:
        current = dict(context_json or {})
        matching_feedback = dict(current.get("matching_feedback") or {})
        events = list(matching_feedback.get(key) or [])
        seen: set[str] = set()
        categories: list[str] = []
        for item in reversed(events[-4:]):
            for value in item.get("categories") or []:
                normalized = str(value or "").strip().lower()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                categories.append(normalized)
        return categories

    def _build_vacancy_skill_universe(self, vacancy, vacancy_version) -> list[str]:
        vacancy_summary = getattr(vacancy_version, "summary_json", None) or {}
        vacancy_source_text = (
            getattr(vacancy_version, "extracted_text", None)
            or getattr(vacancy_version, "transcript_text", None)
            or ""
        )
        return normalize_skill_list(
            extract_full_hard_skills(
                vacancy_source_text,
                extra_values=[
                    *(vacancy.primary_tech_stack_json or []),
                    *(vacancy_summary.get("primary_tech_stack") or []),
                ],
            )
        )

    def _build_vacancy_domain_text(self, vacancy, vacancy_version) -> str:
        vacancy_summary = getattr(vacancy_version, "summary_json", None) or {}
        parts = [
            getattr(vacancy, "role_title", None),
            getattr(vacancy, "project_description", None),
            vacancy_summary.get("project_description_excerpt"),
            getattr(vacancy_version, "approval_summary_text", None),
            getattr(vacancy_version, "extracted_text", None),
            getattr(vacancy_version, "transcript_text", None),
        ]
        return " ".join(str(part).strip() for part in parts if part).strip()

    def _build_rerank_vacancy_context(self, *, vacancy, vacancy_skills, vacancy_domain_text) -> dict:
        return {
            "role_title": getattr(vacancy, "role_title", None),
            "seniority_normalized": getattr(vacancy, "seniority_normalized", None),
            "primary_tech_stack_json": getattr(vacancy, "primary_tech_stack_json", None),
            "vacancy_skill_universe": vacancy_skills,
            "project_description": getattr(vacancy, "project_description", None),
            "project_context_text": vacancy_domain_text,
            "budget_min": getattr(vacancy, "budget_min", None),
            "budget_max": getattr(vacancy, "budget_max", None),
            "work_format": getattr(vacancy, "work_format", None),
            "office_city": getattr(vacancy, "office_city", None),
            "countries_allowed_json": getattr(vacancy, "countries_allowed_json", None),
            "required_english_level": getattr(vacancy, "required_english_level", None),
            "has_take_home_task": getattr(vacancy, "has_take_home_task", None),
            "take_home_paid": getattr(vacancy, "take_home_paid", None),
            "has_live_coding": getattr(vacancy, "has_live_coding", None),
            "hiring_stages_json": getattr(vacancy, "hiring_stages_json", None),
        }

    def _version_aware_seen_candidate_ids(
        self,
        *,
        vacancy_id,
        vacancy_version_id,
        candidate_versions_by_id,
    ) -> set:
        seen_candidate_ids = set()
        for match in self.matching.list_all_for_vacancy(vacancy_id):
            if match.status == "filtered_out":
                continue
            if match.status in self.matching.ACTIVE_MATCH_STATUSES or match.status == "approved":
                seen_candidate_ids.add(match.candidate_profile_id)
                continue

            current_candidate_version = candidate_versions_by_id.get(match.candidate_profile_id)
            if current_candidate_version is None:
                continue
            if (
                match.vacancy_version_id == vacancy_version_id
                and match.candidate_profile_version_id == current_candidate_version.id
            ):
                seen_candidate_ids.add(match.candidate_profile_id)
        return seen_candidate_ids

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
        vacancy_skills = self._build_vacancy_skill_universe(vacancy, vacancy_version)
        vacancy_domain_text = self._build_vacancy_domain_text(vacancy, vacancy_version)
        rerank_vacancy_context = self._build_rerank_vacancy_context(
            vacancy=vacancy,
            vacancy_skills=vacancy_skills,
            vacancy_domain_text=vacancy_domain_text,
        )
        vacancy_feedback_categories = self._recent_feedback_categories(
            getattr(vacancy, "questions_context_json", None),
            key="manager_feedback_events",
        )

        preloaded_candidates = None
        preloaded_by_candidate_id = {}
        candidate_versions_by_id = {}
        candidate_profiles = []
        hybrid_skill_candidates = []

        if trigger_candidate_profile_id is not None:
            candidate = self.candidates.get_by_id(trigger_candidate_profile_id)
            if (
                candidate is not None
                and candidate.state in CANDIDATE_READY_LIKE_STATES
                and candidate.deleted_at is None
            ):
                candidate_profiles.append(candidate)
                candidate_version = self.candidates.get_current_version(candidate)
                if candidate_version is not None:
                    candidate_versions_by_id[candidate.id] = candidate_version
        else:
            ready_profiles = self.candidates.get_ready_profiles()
            if has_embedding_values(vacancy_embedding):
                preloaded_candidates = self.candidates.list_top_similar_ready_profiles(
                    embedding=list(vacancy_embedding),
                    limit=self.VECTOR_RETRIEVAL_LIMIT,
                )
                for item in preloaded_candidates:
                    candidate = item["candidate"]
                    preloaded_by_candidate_id[candidate.id] = item
                    candidate_versions_by_id[candidate.id] = item["candidate_version"]

            skill_seeded_candidates = []
            for candidate in ready_profiles:
                candidate_version = candidate_versions_by_id.get(candidate.id)
                if candidate_version is None:
                    candidate_version = self.candidates.get_current_version(candidate)
                    if candidate_version is None:
                        continue
                    candidate_versions_by_id[candidate.id] = candidate_version

                candidate_summary = candidate_version.summary_json or {}
                candidate_core_skills = normalize_skill_list(candidate_summary.get("skills") or [])
                candidate_full_skills = candidate_version_full_hard_skills(candidate_version)
                seed_score = compute_skill_seed_score(
                    candidate_core_skills=candidate_core_skills,
                    candidate_full_skills=candidate_full_skills,
                    vacancy_skills=vacancy_skills,
                )
                skill_seeded_candidates.append((seed_score, candidate))

            skill_seeded_candidates.sort(key=lambda item: item[0], reverse=True)
            hybrid_skill_candidates = [
                candidate
                for _, candidate in skill_seeded_candidates[: self.HYBRID_SKILL_POOL_LIMIT]
            ]

            candidate_profiles_by_id = {}
            for item in preloaded_candidates or []:
                candidate_profiles_by_id[item["candidate"].id] = item["candidate"]
            for candidate in hybrid_skill_candidates:
                candidate_profiles_by_id.setdefault(candidate.id, candidate)
            candidate_profiles = list(candidate_profiles_by_id.values())

        seen_candidate_ids = self._version_aware_seen_candidate_ids(
            vacancy_id=vacancy.id,
            vacancy_version_id=vacancy_version.id,
            candidate_versions_by_id=candidate_versions_by_id,
        )
        if seen_candidate_ids:
            candidate_profiles = [
                candidate
                for candidate in candidate_profiles
                if candidate.id not in seen_candidate_ids
            ]

        run_mode = (
            "hybrid_vector_plus_deterministic_plus_llm_rerank"
            if preloaded_candidates is not None
            else "hybrid_deterministic_plus_llm_rerank"
        )
        run = self.matching.create_run(
            vacancy_id=vacancy.id,
            trigger_type=trigger_type,
            trigger_candidate_profile_id=trigger_candidate_profile_id,
            payload_json={"mode": run_mode},
        )

        scored = []
        hard_filtered_count = 0

        for candidate in candidate_profiles:
            preloaded = preloaded_by_candidate_id.get(candidate.id)
            candidate_version = candidate_versions_by_id.get(candidate.id)
            if candidate_version is None:
                candidate_version = (
                    preloaded["candidate_version"]
                    if preloaded is not None
                    else self.candidates.get_current_version(candidate)
                )
                if candidate_version is None:
                    continue
                candidate_versions_by_id[candidate.id] = candidate_version

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
            candidate_core_skills = normalize_skill_list(candidate_summary.get("skills") or [])
            candidate_full_skills = candidate_version_full_hard_skills(candidate_version)
            candidate_years_experience = candidate_summary.get("years_experience")
            candidate_feedback_categories = self._recent_feedback_categories(
                getattr(candidate, "questions_context_json", None),
                key="candidate_feedback_events",
            )
            if preloaded is not None:
                embedding_score = preloaded["embedding_score"]
            else:
                embedding_score = compute_vector_similarity(
                    getattr(candidate_version, "semantic_embedding", None),
                    vacancy_embedding,
                )
                if embedding_score is None:
                    embedding_score = compute_embedding_score(candidate_full_skills, vacancy_skills)
            deterministic_score, score_breakdown = compute_deterministic_score(
                candidate_core_skills=candidate_core_skills,
                candidate_full_skills=candidate_full_skills,
                vacancy_skills=vacancy_skills,
                candidate_years_experience=candidate_years_experience,
                vacancy_seniority=vacancy.seniority_normalized,
                candidate_seniority=candidate.seniority_normalized,
                candidate_target_role=getattr(candidate, "target_role", None),
                vacancy_role_title=getattr(vacancy, "role_title", None),
                candidate_work_format=getattr(candidate, "work_format", None),
                candidate_work_formats_json=candidate_work_formats(candidate),
                vacancy_work_format=getattr(vacancy, "work_format", None),
                candidate_country_code=getattr(candidate, "country_code", None),
                candidate_city=getattr(candidate, "city", None),
                candidate_english_level=getattr(candidate, "english_level", None),
                candidate_preferred_domains=getattr(candidate, "preferred_domains_json", None),
                vacancy_countries_allowed=getattr(vacancy, "countries_allowed_json", None),
                vacancy_office_city=getattr(vacancy, "office_city", None),
                vacancy_required_english_level=getattr(vacancy, "required_english_level", None),
                vacancy_project_description=vacancy_domain_text,
                candidate_show_take_home_task_roles=getattr(candidate, "show_take_home_task_roles", None),
                candidate_show_live_coding_roles=getattr(candidate, "show_live_coding_roles", None),
                vacancy_has_take_home_task=getattr(vacancy, "has_take_home_task", None),
                vacancy_take_home_paid=getattr(vacancy, "take_home_paid", None),
                vacancy_has_live_coding=getattr(vacancy, "has_live_coding", None),
                vacancy_hiring_stages=getattr(vacancy, "hiring_stages_json", None),
                candidate_salary_min=getattr(candidate, "salary_min", None),
                candidate_salary_max=getattr(candidate, "salary_max", None),
                vacancy_budget_min=getattr(vacancy, "budget_min", None),
                vacancy_budget_max=getattr(vacancy, "budget_max", None),
                candidate_feedback_categories=candidate_feedback_categories,
                vacancy_feedback_categories=vacancy_feedback_categories,
            )
            scored.append(
                {
                    "candidate": candidate,
                    "candidate_version": candidate_version,
                    "embedding_score": embedding_score,
                    "deterministic_score": deterministic_score,
                    "score_breakdown": score_breakdown,
                    "candidate_feedback_categories": candidate_feedback_categories,
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
                "candidate_target_role": getattr(item["candidate"], "target_role", None),
                "candidate_english_level": getattr(item["candidate"], "english_level", None),
                "candidate_work_format": display_work_formats(item["candidate"]),
                "candidate_work_formats": candidate_work_formats(item["candidate"]),
                "candidate_country_code": getattr(item["candidate"], "country_code", None),
                "candidate_city": getattr(item["candidate"], "city", None),
                "candidate_preferred_domains": getattr(item["candidate"], "preferred_domains_json", None),
                "candidate_full_hard_skills": candidate_version_full_hard_skills(item["candidate_version"])[:15],
                "candidate_process_preferences": {
                    "show_take_home_task_roles": getattr(item["candidate"], "show_take_home_task_roles", None),
                    "show_live_coding_roles": getattr(item["candidate"], "show_live_coding_roles", None),
                },
                "candidate_feedback_categories": item.get("candidate_feedback_categories") or [],
                "embedding_score": item["embedding_score"],
                "deterministic_score": item["deterministic_score"],
                "score_breakdown": item["score_breakdown"],
            }
            for item in deterministic_pool
        ]
        rerank_result = safe_rerank_candidates(
            self.session,
            vacancy=vacancy,
            vacancy_context=rerank_vacancy_context,
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
            fit_band = classify_fit_band(
                deterministic_score=item["deterministic_score"],
                llm_fit_score=rerank_item.get("fit_score"),
                score_breakdown=item["score_breakdown"],
            )
            gap_signals = build_gap_signals(score_breakdown=item["score_breakdown"])
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
                    "fit_band": fit_band,
                    "fit_band_label": fit_band_label(fit_band),
                    "gap_signals": gap_signals,
                    "score_breakdown": item["score_breakdown"],
                    "llm_fit_score": rerank_item.get("fit_score"),
                    "llm_rationale": rerank_item.get("rationale"),
                    "matched_signals": rerank_item.get("matched_signals") or [],
                    "concerns": rerank_item.get("concerns") or [],
                    "feedback_categories": item["score_breakdown"].get("feedback_categories") or [],
                },
            )

        for item in llm_filtered:
            rerank_item = rerank_map.get(str(item["candidate"].id), {})
            gap_signals = build_gap_signals(score_breakdown=item["score_breakdown"])
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
                    "fit_band": "not_fit",
                    "fit_band_label": fit_band_label("not_fit"),
                    "gap_signals": gap_signals,
                    "score_breakdown": item["score_breakdown"],
                    "llm_fit_score": rerank_item.get("fit_score"),
                    "llm_rationale": rerank_item.get("rationale"),
                    "matched_signals": rerank_item.get("matched_signals") or [],
                    "concerns": rerank_item.get("concerns") or [],
                    "feedback_categories": item["score_breakdown"].get("feedback_categories") or [],
                },
            )

        for item in non_shortlisted:
            gap_signals = build_gap_signals(score_breakdown=item["score_breakdown"])
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
                    "fit_band": "not_fit",
                    "fit_band_label": fit_band_label("not_fit"),
                    "gap_signals": gap_signals,
                    "score_breakdown": item["score_breakdown"],
                    "feedback_categories": item["score_breakdown"].get("feedback_categories") or [],
                },
            )

        self.matching.update_run_counts(
            run,
            candidate_pool_count=len(candidate_profiles),
            hard_filtered_count=hard_filtered_count,
            shortlisted_count=len(final_shortlist),
            payload_json={
                "mode": run_mode,
                "candidate_pool_count": len(candidate_profiles),
                "hard_filtered_count": hard_filtered_count,
                "vector_retrieval_used": preloaded_candidates is not None,
                "vector_retrieval_limit": self.VECTOR_RETRIEVAL_LIMIT
                if preloaded_candidates is not None
                else None,
                "vacancy_skill_count": len(vacancy_skills),
                "hybrid_skill_pool_limit": self.HYBRID_SKILL_POOL_LIMIT,
                "hybrid_skill_pool_count": len(hybrid_skill_candidates),
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
