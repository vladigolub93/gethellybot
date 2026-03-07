# Helly Documentation Index

This folder contains the working documentation set for Helly v1.

## Core Product Specification

- [HELLY_V1_SRS.md](./HELLY_V1_SRS.md): master software requirements specification for product, functional, technical, and non-functional requirements.

## Architecture Inputs

- [HELLY_V1_REFERENCE_RESEARCH.md](./HELLY_V1_REFERENCE_RESEARCH.md): detailed study of the `patchy631/ai-engineering-hub` repository and a decision matrix for what Helly should reuse, adapt, or ignore.
- [HELLY_V1_ARCHITECTURE_BLUEPRINT.md](./HELLY_V1_ARCHITECTURE_BLUEPRINT.md): target backend architecture, module boundaries, data flows, AI orchestration model, infrastructure baseline, and quality controls.
- [HELLY_V1_INFRA_DECISIONS.md](./HELLY_V1_INFRA_DECISIONS.md): fixed infrastructure choices for v1, including Supabase, Railway, Telegram, and OpenAI integration assumptions.
- [HELLY_V1_RAILWAY_DEPLOYMENT.md](./HELLY_V1_RAILWAY_DEPLOYMENT.md): Railway deployment shape, service layout, env contract, webhook setup, and smoke-test checklist.
- [HELLY_V1_PROJECT_ARCHITECTURE.md](./HELLY_V1_PROJECT_ARCHITECTURE.md): consolidated project architecture file that combines product, technical, infrastructure, and implementation decisions into one execution-oriented view.

## Detailed Design

- [HELLY_V1_DATA_MODEL_AND_ERD.md](./HELLY_V1_DATA_MODEL_AND_ERD.md): physical data model, entity relationships, suggested PostgreSQL schema, indexes, and retention strategy.
- [HELLY_V1_STATE_MACHINES.md](./HELLY_V1_STATE_MACHINES.md): detailed state definitions, transition matrices, guards, side effects, and failure handling rules.
- [HELLY_V1_PROMPT_CATALOG.md](./HELLY_V1_PROMPT_CATALOG.md): AI capability inventory, prompt asset structure, schema contracts, model policy, and evaluation requirements.

## Delivery Planning

- [HELLY_V1_IMPLEMENTATION_PLAN.md](./HELLY_V1_IMPLEMENTATION_PLAN.md): phased implementation roadmap, epics, milestones, dependency order, suggested ticket breakdown, and definition-of-done guidance.
- [HELLY_V1_ENGINEERING_BACKLOG.md](./HELLY_V1_ENGINEERING_BACKLOG.md): initial implementation backlog with epic IDs, task IDs, priorities, dependencies, and acceptance guidance.
- [HELLY_V1_MASTER_TASK_LIST.md](./HELLY_V1_MASTER_TASK_LIST.md): single ordered execution list from project bootstrap through staging, production launch, and post-launch stabilization.

## Recommended Reading Order

1. Read `HELLY_V1_SRS.md` for product truth.
2. Read `HELLY_V1_REFERENCE_RESEARCH.md` to understand reusable external patterns and avoid copying the wrong examples.
3. Read `HELLY_V1_ARCHITECTURE_BLUEPRINT.md` to establish implementation architecture.
4. Read `HELLY_V1_DATA_MODEL_AND_ERD.md`, `HELLY_V1_STATE_MACHINES.md`, and `HELLY_V1_PROMPT_CATALOG.md` for implementation-grade design.
5. Read `HELLY_V1_IMPLEMENTATION_PLAN.md`, `HELLY_V1_ENGINEERING_BACKLOG.md`, and `HELLY_V1_MASTER_TASK_LIST.md` to convert architecture into delivery sequencing and task execution.
