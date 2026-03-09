from src.llm.service import (
    LLMResult,
    _clean_summary_text,
    extract_candidate_summary_with_llm,
    extract_vacancy_summary_with_llm,
)


def test_clean_summary_text_prefers_sentence_boundary() -> None:
    text = (
        "You are Dmytro Zotieiev, a senior full-stack engineer with strong product and platform experience. "
        "You work across React, React Native, Next.js, Node.js, TypeScript, GraphQL, PostgreSQL, Redis, and AWS on real-time systems. "
        "You have shipped products in fintech, media, and SaaS with a strong focus on performance and architecture. "
        "You also worked on analytics systems and distributed workloads that should not appear in the trimmed result."
    )

    cleaned = _clean_summary_text(text, limit=360)

    assert cleaned is not None
    assert cleaned.endswith(".")
    assert "should not appear in the trimmed result" not in cleaned
    assert "architecture." in cleaned


def test_extract_candidate_summary_uses_safe_summary_cleaning(monkeypatch) -> None:
    long_summary = (
        "You are Dmytro Zotieiev, a Senior Full-Stack and Mobile Developer with about 6 years of experience building scalable web and mobile products. "
        "You work primarily with React, React Native, Next.js, Node.js, TypeScript, Redux, Express, GraphQL, PostgreSQL, MongoDB, Redis, AWS, and CI/CD, with strong experience in real-time systems, performance optimization, and scalable architecture. "
        "You have worked across AI, ecommerce, fintech, telecom, SaaS, media, and high-load consumer platforms, including analytics systems and distributed data pipelines. "
        "This extra sentence is intentionally very long and should be trimmed safely at a sentence boundary instead of being cut in the middle of a word like analy"
    )

    monkeypatch.setattr(
        "src.llm.service._client.parse",
        lambda **_kwargs: LLMResult(
            payload={
                "headline": "Senior Full-Stack Engineer",
                "experience_excerpt": "Relevant experience excerpt",
                "skills": ["react", "node.js"],
                "approval_summary_text": long_summary,
            },
            model_name="gpt-5.4",
            prompt_version="candidate_cv_extract_llm_v2",
        ),
    )

    result = extract_candidate_summary_with_llm("raw cv text", "document_upload")
    summary_text = result.payload["approval_summary_text"]

    assert summary_text.endswith(".")
    assert "like analy" not in summary_text
    assert "distributed data pipelines." in summary_text


def test_extract_vacancy_summary_uses_safe_summary_cleaning(monkeypatch) -> None:
    long_summary = (
        "This vacancy is for a Senior Python Engineer building backend services for a fintech platform. "
        "The main stack includes Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes, and AWS, with a focus on reliability, APIs, and event-driven services. "
        "The role sits in a product team working on a customer-facing platform with meaningful scale, ownership, and delivery responsibility. "
        "This extra sentence should be cut safely if it pushes the summary over the limit without leaving a broken trailing fragment like architec"
    )

    monkeypatch.setattr(
        "src.llm.service._client.parse",
        lambda **_kwargs: LLMResult(
            payload={
                "role_title": "Senior Python Engineer",
                "primary_tech_stack": ["python", "fastapi", "postgresql"],
                "project_description_excerpt": "Relevant vacancy excerpt",
                "approval_summary_text": long_summary,
                "inconsistency_issues": [],
            },
            model_name="gpt-5.4",
            prompt_version="vacancy_jd_extract_llm_v1",
        ),
    )

    result = extract_vacancy_summary_with_llm("raw jd text", "document_upload")
    summary_text = result.payload["summary"]["approval_summary_text"]

    assert summary_text.endswith(".")
    assert "like architec" not in summary_text
    assert "delivery responsibility." in summary_text
