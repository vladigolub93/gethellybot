from __future__ import annotations

import re
from typing import Iterable, Optional


_SKILL_ALIAS_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("python", ("python",)),
    ("java", ("java",)),
    ("javascript", ("javascript",)),
    ("typescript", ("typescript",)),
    ("node.js", ("node.js", "nodejs", "node")),
    ("react", ("react",)),
    ("react native", ("react native",)),
    ("next.js", ("next.js", "nextjs")),
    ("vue", ("vue", "vue.js")),
    ("nuxt.js", ("nuxt.js", "nuxtjs")),
    ("angular", ("angular", "angularjs")),
    ("svelte", ("svelte",)),
    ("redux", ("redux",)),
    ("html", ("html", "html5")),
    ("css", ("css", "css3")),
    ("sass", ("sass", "scss")),
    ("tailwind css", ("tailwind css", "tailwind")),
    ("webpack", ("webpack",)),
    ("vite", ("vite",)),
    ("storybook", ("storybook",)),
    ("npm", ("npm",)),
    ("yarn", ("yarn",)),
    ("pnpm", ("pnpm",)),
    ("django", ("django",)),
    ("fastapi", ("fastapi",)),
    ("flask", ("flask",)),
    ("aiohttp", ("aiohttp",)),
    ("celery", ("celery",)),
    ("express", ("express", "express.js", "expressjs")),
    ("nestjs", ("nestjs", "nest.js", "nest")),
    ("koa", ("koa",)),
    ("socket.io", ("socket.io", "socketio")),
    ("graphql", ("graphql",)),
    ("rest api", ("rest api", "restful api", "rest apis", "restful apis")),
    ("grpc", ("grpc",)),
    ("websockets", ("websocket", "websockets")),
    ("php", ("php",)),
    ("laravel", ("laravel",)),
    ("symfony", ("symfony",)),
    ("ruby", ("ruby",)),
    ("ruby on rails", ("ruby on rails", "rails")),
    ("elixir", ("elixir",)),
    ("phoenix", ("phoenix",)),
    ("scala", ("scala",)),
    ("spark", ("apache spark", "spark")),
    ("go", ("golang", "go")),
    ("gin", ("gin", "gin-gonic")),
    ("rust", ("rust",)),
    ("actix", ("actix", "actix-web")),
    ("kotlin", ("kotlin",)),
    ("swift", ("swift",)),
    ("objective-c", ("objective-c", "objective c")),
    ("android", ("android",)),
    ("ios", ("ios",)),
    ("c++", ("c++",)),
    ("c#", ("c#", "c sharp")),
    (".net", (".net", "dotnet", "asp.net", "asp.net core", ".net core")),
    ("postgresql", ("postgresql", "postgres")),
    ("mysql", ("mysql",)),
    ("sql server", ("sql server", "mssql", "ms sql")),
    ("oracle", ("oracle", "oracle db")),
    ("sqlite", ("sqlite", "sqlite3")),
    ("mongodb", ("mongodb", "mongo db", "mongo")),
    ("redis", ("redis",)),
    ("elasticsearch", ("elasticsearch", "elastic search", "elastic")),
    ("opensearch", ("opensearch", "open search")),
    ("cassandra", ("cassandra",)),
    ("dynamodb", ("dynamodb", "dynamo db")),
    ("firebase", ("firebase",)),
    ("supabase", ("supabase",)),
    ("aws", ("aws", "amazon web services")),
    ("gcp", ("gcp", "google cloud", "google cloud platform")),
    ("azure", ("azure", "microsoft azure")),
    ("cloudflare", ("cloudflare",)),
    ("docker", ("docker",)),
    ("kubernetes", ("kubernetes", "k8s")),
    ("helm", ("helm",)),
    ("terraform", ("terraform",)),
    ("ansible", ("ansible",)),
    ("linux", ("linux",)),
    ("nginx", ("nginx",)),
    ("apache", ("apache", "apache http server")),
    ("prometheus", ("prometheus",)),
    ("grafana", ("grafana",)),
    ("rabbitmq", ("rabbitmq", "rabbit mq")),
    ("kafka", ("kafka", "apache kafka")),
    ("sqs", ("sqs", "amazon sqs")),
    ("pytest", ("pytest",)),
    ("jest", ("jest",)),
    ("cypress", ("cypress",)),
    ("selenium", ("selenium",)),
    ("playwright", ("playwright",)),
    ("junit", ("junit",)),
    ("pandas", ("pandas",)),
    ("numpy", ("numpy",)),
    ("scikit-learn", ("scikit-learn", "sklearn")),
    ("tensorflow", ("tensorflow",)),
    ("pytorch", ("pytorch",)),
    ("git", ("git",)),
    ("github actions", ("github actions",)),
    ("gitlab ci", ("gitlab ci", "gitlab-ci")),
    ("jenkins", ("jenkins",)),
    ("circleci", ("circleci", "circle ci")),
    ("travis ci", ("travis ci", "travis-ci")),
)

_DISPLAY_MAP: dict[str, str] = {
    "aws": "AWS",
    "gcp": "GCP",
    "node.js": "Node.js",
    "next.js": "Next.js",
    "nuxt.js": "Nuxt.js",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "html": "HTML",
    "css": "CSS",
    "tailwind css": "Tailwind CSS",
    "fastapi": "FastAPI",
    "nestjs": "NestJS",
    "socket.io": "Socket.IO",
    "graphql": "GraphQL",
    "rest api": "REST API",
    "grpc": "gRPC",
    "php": "PHP",
    "ruby on rails": "Ruby on Rails",
    "go": "Go",
    "c++": "C++",
    "c#": "C#",
    ".net": ".NET",
    "postgresql": "PostgreSQL",
    "sql server": "SQL Server",
    "mongodb": "MongoDB",
    "elasticsearch": "Elasticsearch",
    "opensearch": "OpenSearch",
    "dynamodb": "DynamoDB",
    "firebase": "Firebase",
    "supabase": "Supabase",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "rabbitmq": "RabbitMQ",
    "kafka": "Kafka",
    "sqs": "SQS",
    "pytest": "Pytest",
    "jest": "Jest",
    "cypress": "Cypress",
    "selenium": "Selenium",
    "playwright": "Playwright",
    "junit": "JUnit",
    "numpy": "NumPy",
    "scikit-learn": "scikit-learn",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "github actions": "GitHub Actions",
    "gitlab ci": "GitLab CI",
    "circleci": "CircleCI",
    "travis ci": "Travis CI",
    "ios": "iOS",
}


def _normalize_text(text: str | None) -> str:
    return " ".join(str(text or "").replace("_", " ").split()).strip().lower()


def _normalize_alias(value: str | None) -> str:
    return _normalize_text(value).strip(" ,.")


_ALIASES_BY_CANONICAL: dict[str, tuple[str, ...]] = {}
_CANONICAL_BY_ALIAS: dict[str, str] = {}
_PATTERNS_BY_CANONICAL: dict[str, tuple[re.Pattern[str], ...]] = {}
for canonical, aliases in _SKILL_ALIAS_GROUPS:
    normalized_canonical = _normalize_alias(canonical)
    normalized_aliases = tuple(
        dict.fromkeys(
            alias
            for alias in (_normalize_alias(item) for item in (canonical, *aliases))
            if alias
        )
    )
    _ALIASES_BY_CANONICAL[normalized_canonical] = normalized_aliases
    for alias in normalized_aliases:
        _CANONICAL_BY_ALIAS[alias] = normalized_canonical
    _PATTERNS_BY_CANONICAL[normalized_canonical] = tuple(
        re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])")
        for alias in normalized_aliases
    )


def normalize_skill_token(value: str | None) -> str:
    normalized = _normalize_alias(value)
    return _CANONICAL_BY_ALIAS.get(normalized, normalized)


def normalize_skill_list(values: Iterable[str] | None, *, limit: Optional[int] = None) -> list[str]:
    seen = set()
    result: list[str] = []
    for raw_value in values or []:
        normalized = normalize_skill_token(raw_value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if limit is not None and len(result) >= limit:
            break
    return result


def display_skill(value: str | None) -> str:
    normalized = normalize_skill_token(value)
    if not normalized:
        return ""
    if normalized in _DISPLAY_MAP:
        return _DISPLAY_MAP[normalized]
    words = normalized.split()
    return " ".join(word.upper() if len(word) <= 3 else word.capitalize() for word in words)


def display_skill_list(values: Iterable[str] | None, *, limit: Optional[int] = None) -> list[str]:
    result: list[str] = []
    for item in normalize_skill_list(values, limit=limit):
        rendered = display_skill(item)
        if rendered:
            result.append(rendered)
    return result


def text_contains_skill(text: str | None, skill: str | None) -> bool:
    normalized_text = _normalize_text(text)
    normalized_skill = normalize_skill_token(skill)
    if not normalized_text or not normalized_skill:
        return False
    patterns = _PATTERNS_BY_CANONICAL.get(normalized_skill)
    if patterns:
        return any(pattern.search(normalized_text) for pattern in patterns)
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized_skill)}(?![a-z0-9])", normalized_text))


def extract_full_hard_skills(
    source_text: str | None,
    *,
    extra_values: Iterable[str] | None = None,
    limit: Optional[int] = None,
) -> list[str]:
    normalized_text = _normalize_text(source_text)
    positions: dict[str, int] = {}

    for canonical, patterns in _PATTERNS_BY_CANONICAL.items():
        earliest: Optional[int] = None
        for pattern in patterns:
            match = pattern.search(normalized_text)
            if match is None:
                continue
            earliest = match.start() if earliest is None else min(earliest, match.start())
        if earliest is not None:
            positions[canonical] = earliest

    ordered = [item[0] for item in sorted(positions.items(), key=lambda item: (item[1], item[0]))]
    seen = set(ordered)
    for extra in normalize_skill_list(extra_values):
        if extra in seen:
            continue
        ordered.append(extra)
        seen.add(extra)

    if limit is not None:
        return ordered[:limit]
    return ordered


def candidate_version_full_hard_skills(version) -> list[str]:
    if version is None:
        return []
    normalization = getattr(version, "normalization_json", None) or {}
    stored = normalize_skill_list(normalization.get("full_hard_skills") or [])
    if stored:
        return stored

    summary = getattr(version, "summary_json", None) or {}
    source_text = getattr(version, "extracted_text", None) or getattr(version, "transcript_text", None) or ""
    return extract_full_hard_skills(
        source_text,
        extra_values=summary.get("skills") or [],
    )
