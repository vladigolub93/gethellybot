# Helly Documentation Index

This folder contains the working documentation set for Helly v1.

## Core Product Specification

- [HELLY_V1_SRS.md](./HELLY_V1_SRS.md): master software requirements specification for product, functional, technical, and non-functional requirements.

## Architecture Inputs

- [HELLY_V1_REFERENCE_RESEARCH.md](./HELLY_V1_REFERENCE_RESEARCH.md): detailed study of the `patchy631/ai-engineering-hub` repository and a decision matrix for what Helly should reuse, adapt, or ignore.
- [HELLY_V1_ARCHITECTURE_BLUEPRINT.md](./HELLY_V1_ARCHITECTURE_BLUEPRINT.md): target backend architecture, module boundaries, data flows, AI orchestration model, infrastructure baseline, and quality controls.
- [HELLY_V1_INFRA_DECISIONS.md](./HELLY_V1_INFRA_DECISIONS.md): fixed infrastructure choices for v1, including Supabase, Railway, Telegram, and OpenAI integration assumptions.
- [HELLY_V1_RAILWAY_DEPLOYMENT.md](./HELLY_V1_RAILWAY_DEPLOYMENT.md): Railway deployment shape, service layout, env contract, webhook setup, and smoke-test checklist.
- [HELLY_V1_LIVE_SMOKE_RUNBOOK.md](./HELLY_V1_LIVE_SMOKE_RUNBOOK.md): live Telegram smoke scenarios with validation commands for candidate, manager, interview, and deletion paths.
- [HELLY_V1_PROJECT_ARCHITECTURE.md](./HELLY_V1_PROJECT_ARCHITECTURE.md): consolidated project architecture file that combines product, technical, infrastructure, and implementation decisions into one execution-oriented view.

## Detailed Design

- [HELLY_V1_DATA_MODEL_AND_ERD.md](./HELLY_V1_DATA_MODEL_AND_ERD.md): physical data model, entity relationships, suggested PostgreSQL schema, indexes, and retention strategy.
- [HELLY_V1_STATE_MACHINES.md](./HELLY_V1_STATE_MACHINES.md): detailed state definitions, transition matrices, guards, side effects, and failure handling rules.
- [HELLY_V1_STATE_AWARE_CONVERSATION_MODEL.md](./HELLY_V1_STATE_AWARE_CONVERSATION_MODEL.md): the state-by-state conversational control model that keeps deterministic state machines authoritative while allowing AI to assist intelligently inside every active step.
- [HELLY_V1_LANGGRAPH_STAGE_AGENT_ARCHITECTURE.md](./HELLY_V1_LANGGRAPH_STAGE_AGENT_ARCHITECTURE.md): the new target orchestration model that introduces bounded LangGraph stage agents over the same deterministic backend state machines.
- [HELLY_V1_LANGGRAPH_MIGRATION_PLAN.md](./HELLY_V1_LANGGRAPH_MIGRATION_PLAN.md): execution sequence for migrating the current state-aware controller/routing baseline into LangGraph stage agents.
- [HELLY_V1_AGENT_OWNED_STAGE_ARCHITECTURE.md](./HELLY_V1_AGENT_OWNED_STAGE_ARCHITECTURE.md): canonical target architecture where every major user-facing state is owned by its own LangGraph stage agent with prompt instructions and KB grounding.
- [HELLY_V1_AGENT_OWNED_STAGE_REBUILD_PLAN.md](./HELLY_V1_AGENT_OWNED_STAGE_REBUILD_PLAN.md): full rebuild plan for moving Helly from the current partial migration state to fully agent-owned stage execution.
- [HELLY_V1_AGENT_OWNERSHIP_COMPLETION_PLAN.md](./HELLY_V1_AGENT_OWNERSHIP_COMPLETION_PLAN.md): detailed project-wide plan for removing remaining backend intent ownership so migrated stages become truly agent-owned in meaning, not just in routing.
- [HELLY_V1_AGENT_INTENT_OWNERSHIP_MATRIX.md](./HELLY_V1_AGENT_INTENT_OWNERSHIP_MATRIX.md): stage-by-stage inventory of the remaining backend intent detectors that must be removed for true agent-owned stage behavior.
- [HELLY_V1_ENTRY_AND_VACANCY_REDESIGN_TASK_LIST.md](./HELLY_V1_ENTRY_AND_VACANCY_REDESIGN_TASK_LIST.md): focused detailed task list for the next redesign slice: no-consent entry flow, username-or-contact identity, vacancy summary review, and thin supervisor/router enforcement.
- [HELLY_V1_PROMPT_CATALOG.md](./HELLY_V1_PROMPT_CATALOG.md): AI capability inventory, prompt asset structure, schema contracts, model policy, and evaluation requirements.
- [HELLY_V1_AGENT_KNOWLEDGE_BASE.md](./HELLY_V1_AGENT_KNOWLEDGE_BASE.md): canonical FAQ and product-truth grounding for all user-facing AI agents and state-specific prompts.
- [HELLY_V1_LLM_COVERAGE.md](./HELLY_V1_LLM_COVERAGE.md): full prompt-family coverage matrix showing which LLM capabilities already have assets, which are runtime-wired, and which still need implementation wiring.
- [HELLY_V1_CONVERSATION_QUALITY_PLAN.md](./HELLY_V1_CONVERSATION_QUALITY_PLAN.md): the conversational quality roadmap for making Helly feel more natural, Telegram-native, and human.
- [HELLY_V1_VOICE_AND_TONE_GUIDE.md](./HELLY_V1_VOICE_AND_TONE_GUIDE.md): canonical voice rules for making Helly sound like a sharp, warm recruiter from the IT world.
- [HELLY_V1_CONVERSATION_POLISH_TASK_LIST.md](./HELLY_V1_CONVERSATION_POLISH_TASK_LIST.md): ordered execution list for prompt tuning, message choreography, local conversational memory, and live transcript polish.

## Delivery Planning

- [HELLY_V1_IMPLEMENTATION_PLAN.md](./HELLY_V1_IMPLEMENTATION_PLAN.md): phased implementation roadmap, epics, milestones, dependency order, suggested ticket breakdown, and definition-of-done guidance.
- [HELLY_V1_STATE_AWARE_EXECUTION_PLAN.md](./HELLY_V1_STATE_AWARE_EXECUTION_PLAN.md): execution plan specifically for rolling out the state-aware AI assistance layer across all major workflow states.
- [HELLY_V1_ENGINEERING_BACKLOG.md](./HELLY_V1_ENGINEERING_BACKLOG.md): initial implementation backlog with epic IDs, task IDs, priorities, dependencies, and acceptance guidance.
- [HELLY_V1_MASTER_TASK_LIST.md](./HELLY_V1_MASTER_TASK_LIST.md): single ordered execution list from project bootstrap through staging, production launch, and post-launch stabilization.
- [HELLY_V1_IMPLEMENTATION_STATUS.md](./HELLY_V1_IMPLEMENTATION_STATUS.md): current implementation audit against the SRS, with `implemented / partial / not implemented` coverage.

## Recommended Reading Order

1. Read `HELLY_V1_SRS.md` for product truth.
2. Read `HELLY_V1_REFERENCE_RESEARCH.md` to understand reusable external patterns and avoid copying the wrong examples.
3. Read `HELLY_V1_ARCHITECTURE_BLUEPRINT.md` to establish implementation architecture.
4. Read `HELLY_V1_DATA_MODEL_AND_ERD.md`, `HELLY_V1_STATE_MACHINES.md`, `HELLY_V1_AGENT_OWNED_STAGE_ARCHITECTURE.md`, `HELLY_V1_AGENT_KNOWLEDGE_BASE.md`, and `HELLY_V1_PROMPT_CATALOG.md` for the current implementation-grade design.
5. Read `HELLY_V1_AGENT_OWNED_STAGE_REBUILD_PLAN.md`, `HELLY_V1_AGENT_OWNERSHIP_COMPLETION_PLAN.md`, `HELLY_V1_IMPLEMENTATION_PLAN.md`, `HELLY_V1_ENGINEERING_BACKLOG.md`, and `HELLY_V1_MASTER_TASK_LIST.md` to convert architecture into delivery sequencing and task execution.
