# HELLY v1 Reference Research

AI Engineering Hub Study and Relevance Assessment

Version: 1.0  
Date: 2026-03-07

## 1. Purpose

This document captures a detailed study of the public repository [`patchy631/ai-engineering-hub`](https://github.com/patchy631/ai-engineering-hub) and translates that study into concrete architecture decisions for Helly v1.

This is not a summary of the repository for educational purposes. It is a selection document whose only goal is to answer:

- what should Helly reuse as a pattern
- what should Helly explicitly avoid
- what is missing and must be implemented independently

## 2. Executive Conclusion

The repository is useful as a pattern library, not as a direct implementation base.

It contains many isolated demos with uneven production depth, different frameworks, and vendor-specific examples. Helly should not adopt the repository wholesale or choose a single project from it as the product skeleton.

The most valuable parts for Helly are:

- structured conversational control patterns
- document ingestion pipeline patterns
- speech/audio transcription patterns
- evaluation and observability patterns
- context assembly patterns for selective LLM reasoning

The least valuable parts for Helly are:

- generic chatbot UIs
- local-only model demos
- research-agent demos as core business orchestration
- MCP-heavy examples not aligned with Telegram-first product delivery
- generic RAG document chat demos unrelated to recruiting workflows

## 3. Repository Context

Repository studied:

- [`patchy631/ai-engineering-hub`](https://github.com/patchy631/ai-engineering-hub)

Observed repository profile at review time:

- active multi-project repository
- large catalog of demos across RAG, agents, MCP, voice, evaluation, and model comparison
- educational orientation more than product orientation
- significant variation in framework maturity and engineering rigor between subprojects

Implication for Helly:

- use the repository for architecture ideas and implementation patterns
- do not treat any demo as production-ready by default
- isolate reusable concepts from vendor/framework-specific wrappers

## 4. Helly Requirements Lens

To evaluate usefulness, every candidate example was filtered through Helly's actual needs:

- Telegram-first, not web-first
- deterministic state machine control
- LLM used under guardrails
- multimodal candidate and vacancy intake
- asynchronous matching and evaluation jobs
- strong auditability and idempotency
- transactional recruiting workflows rather than open-ended chat

Any repository example that did not improve one of those areas was considered low-value.

## 5. Projects Reviewed as Primary References

The following repository areas were examined directly because they map most closely to Helly concerns:

- [`parlant-conversational-agent`](https://github.com/patchy631/ai-engineering-hub/tree/main/parlant-conversational-agent)
- [`guidelines-vs-traditional-prompt`](https://github.com/patchy631/ai-engineering-hub/tree/main/guidelines-vs-traditional-prompt)
- [`groundX-doc-pipeline`](https://github.com/patchy631/ai-engineering-hub/tree/main/groundX-doc-pipeline)
- [`audio-analysis-toolkit`](https://github.com/patchy631/ai-engineering-hub/tree/main/audio-analysis-toolkit)
- [`eval-and-observability`](https://github.com/patchy631/ai-engineering-hub/tree/main/eval-and-observability)
- [`context-engineering-workflow`](https://github.com/patchy631/ai-engineering-hub/tree/main/context-engineering-workflow)
- [`firecrawl-agent`](https://github.com/patchy631/ai-engineering-hub/tree/main/firecrawl-agent)
- [`agent-with-mcp-memory`](https://github.com/patchy631/ai-engineering-hub/tree/main/agent-with-mcp-memory)
- [`zep-memory-assistant`](https://github.com/patchy631/ai-engineering-hub/tree/main/zep-memory-assistant)
- [`deploy-agentic-rag`](https://github.com/patchy631/ai-engineering-hub/tree/main/deploy-agentic-rag)

## 6. Detailed Findings by Reference

## 6.1 `parlant-conversational-agent`

Primary files:

- [`README.md`](https://github.com/patchy631/ai-engineering-hub/blob/main/parlant-conversational-agent/README.md)
- [`loan_approval.py`](https://github.com/patchy631/ai-engineering-hub/blob/main/parlant-conversational-agent/loan_approval.py)

### What it demonstrates well

- state-based guided conversation rather than free-form prompting
- explicit transitions between chat states
- tool invocation embedded into a controlled journey
- domain glossary and behavior rules
- off-topic and compliance boundary handling

### Why it is relevant to Helly

This is the closest conceptual match in the repository to Helly's onboarding and interview flows. Helly also needs:

- mandatory step enforcement
- recoverable user interaction
- selective tool execution
- deterministic transition rules
- controlled responses in sensitive business flows

### What Helly should reuse as a pattern

- explicit journey/state definitions
- guideline-driven behavior guardrails
- separation between tool execution and natural-language response
- domain term registration and phrasing consistency

### What Helly should not copy directly

- direct dependence on Parlant as the product backbone without validating its fit for Telegram webhook handling, persistence, retries, and our custom state model
- in-memory or framework-managed journey state as the primary source of truth

### Helly decision

Adopt the pattern, not the framework.

We should implement our own database-backed state machines and use this project as a reference for:

- state naming style
- transition discipline
- behavioral guideline design
- domain-specific conversation boundaries

## 6.2 `guidelines-vs-traditional-prompt`

Primary file:

- [`README.md`](https://github.com/patchy631/ai-engineering-hub/blob/main/guidelines-vs-traditional-prompt/README.md)

### What it demonstrates well

- the weakness of large monolithic prompts
- the value of smaller, targeted guidelines
- stronger control over mixed scenarios and constraint handling

### Why it is relevant to Helly

Helly will have many sensitive or stateful situations:

- consent collection
- mandatory candidate fields
- mandatory vacancy fields
- clarification loops
- deletion confirmations
- interview follow-up limits
- manager-facing candidate package generation

These should not be driven by one giant system prompt.

### Helly decision

Adopt the principle fully.

Helly should maintain prompt assets per use case:

- candidate summary extraction
- candidate clarification parsing
- vacancy extraction
- vacancy clarification parsing
- interview question generation
- interview follow-up generation
- evaluation
- reranking
- fallback/recovery messaging

## 6.3 `groundX-doc-pipeline`

Primary files:

- [`README.md`](https://github.com/patchy631/ai-engineering-hub/blob/main/groundX-doc-pipeline/README.md)
- [`groundx_utils.py`](https://github.com/patchy631/ai-engineering-hub/blob/main/groundX-doc-pipeline/groundx_utils.py)

### What it demonstrates well

- document upload and processing workflow
- polling of asynchronous parse jobs
- normalized access to parsed output
- structured extraction over non-trivial document content

### Why it is relevant to Helly

Helly requires CV and JD ingestion from:

- PDF
- DOCX
- TXT
- pasted text
- voice/video descriptions after transcription

The exact provider is negotiable, but the flow is not.

### What Helly should reuse as a pattern

- upload raw artifact first
- create parse job
- persist processing status
- poll or handle asynchronous completion
- store parsed text separately from original file
- store structured extraction separately from raw text

### What Helly should not copy directly

- provider lock-in to GroundX
- Streamlit-oriented UX assumptions
- document-chat architecture layered on top of parsing

### Helly decision

Adopt the pipeline shape. Keep parser provider abstract behind a `DocumentParser` interface.

## 6.4 `audio-analysis-toolkit`

Primary files:

- [`README.md`](https://github.com/patchy631/ai-engineering-hub/blob/main/audio-analysis-toolkit/README.md)
- [`server.py`](https://github.com/patchy631/ai-engineering-hub/blob/main/audio-analysis-toolkit/server.py)

### What it demonstrates well

- speech transcription workflow
- extraction of timestamps and summary data
- normalized post-transcription features
- encapsulation of audio analysis behind a service boundary

### Why it is relevant to Helly

Helly accepts:

- candidate voice answers
- candidate video answers
- manager voice/video vacancy input
- candidate interview responses via voice/video

The first mandatory requirement is not voice synthesis. It is reliable transcription and storage.

### What Helly should reuse as a pattern

- transcription as a first-class pipeline
- transcript plus metadata artifact model
- feature extraction after transcription
- clean service contract for audio processing

### What Helly should not copy directly

- MCP server surface as a required runtime dependency
- sentiment/topic analysis as mandatory first-wave features

### Helly decision

Adopt transcription-first multimodal ingestion. MCP is optional and unnecessary for v1 runtime.

## 6.5 `eval-and-observability`

Primary files:

- [`README.md`](https://github.com/patchy631/ai-engineering-hub/blob/main/eval-and-observability/README.md)
- [`demo.ipynb`](https://github.com/patchy631/ai-engineering-hub/blob/main/eval-and-observability/demo.ipynb)
- [`data_gen.ipynb`](https://github.com/patchy631/ai-engineering-hub/blob/main/eval-and-observability/data_gen.ipynb)

### What it demonstrates well

- Opik-based tracing
- LLM call instrumentation
- RAG evaluation patterns
- dataset-driven evaluation mindset

### Why it is relevant to Helly

Helly has multiple AI subsystems that can drift or silently degrade:

- CV parsing
- vacancy parsing
- answer normalization
- candidate reranking
- interview evaluation
- follow-up generation

Without evals and traces, debugging failure will be anecdotal and slow.

### What Helly should reuse as a pattern

- tracing all important AI calls
- tagging prompt and model versions
- creating small benchmark datasets per AI use case
- evaluation-as-a-pipeline, not as occasional manual checking

### Helly decision

Adopt evaluation and observability as a first-class part of architecture, not a later addition.

## 6.6 `context-engineering-workflow`

Primary files:

- [`README.md`](https://github.com/patchy631/ai-engineering-hub/blob/main/context-engineering-workflow/README.md)
- [`src/workflows/flow.py`](https://github.com/patchy631/ai-engineering-hub/blob/main/context-engineering-workflow/src/workflows/flow.py)
- [`src/workflows/tasks.py`](https://github.com/patchy631/ai-engineering-hub/blob/main/context-engineering-workflow/src/workflows/tasks.py)
- [`src/rag/rag_pipeline.py`](https://github.com/patchy631/ai-engineering-hub/blob/main/context-engineering-workflow/src/rag/rag_pipeline.py)
- [`src/memory/memory.py`](https://github.com/patchy631/ai-engineering-hub/blob/main/context-engineering-workflow/src/memory/memory.py)
- [`config/agents/research_agents.yaml`](https://github.com/patchy631/ai-engineering-hub/blob/main/context-engineering-workflow/config/agents/research_agents.yaml)
- [`config/tasks/research_tasks.yaml`](https://github.com/patchy631/ai-engineering-hub/blob/main/context-engineering-workflow/config/tasks/research_tasks.yaml)

### What it demonstrates well

- gathering context from multiple sources
- evaluating relevance before synthesis
- schema-bound output validation
- separating source retrieval from final answer generation

### Why it is relevant to Helly

Some Helly workflows need multi-source reasoning:

- manager candidate package assembly
- interview evaluation using CV + answers + vacancy profile
- reranking explanations
- future company enrichment or external verification

### What Helly should reuse as a pattern

- multi-source context assembly
- evaluator step before final synthesis
- Pydantic or equivalent schema validation
- configuration-driven task/prompt separation

### What Helly should not copy directly

- CrewAI as the primary orchestration runtime for core business flow
- broad autonomous multi-agent decomposition for transactional logic without backend state validation
- Zep-backed conversation memory as the default state holder

### Helly decision

Adopt the internal pattern selectively:

- source collection
- context filtering
- schema-validated synthesis
- bounded task and stage decomposition
- explicit graph handoff between narrowly scoped agents

Do not adopt the open-ended CrewAI-style execution model for core user journeys.

Adopt instead:

- `LangGraph` as the orchestration runtime
- one bounded stage agent per major Helly workflow stage
- backend-validated transitions over Postgres-backed domain state

## 6.7 `firecrawl-agent`

Primary files:

- [`README.md`](https://github.com/patchy631/ai-engineering-hub/blob/main/firecrawl-agent/README.md)
- [`workflow.py`](https://github.com/patchy631/ai-engineering-hub/blob/main/firecrawl-agent/workflow.py)

### What it demonstrates well

- corrective retrieval workflow
- fallback from local retrieval to web search
- relevance grading

### Why it is only partially relevant

Helly v1 is not a web-research product. Core matching and evaluation should not depend on live web search.

Possible future relevance:

- company enrichment for vacancies
- market data checks
- public profile validation
- external sourcing research

### Helly decision

Keep as a future extension pattern. Do not put web fallback into the v1 critical path.

## 6.8 `agent-with-mcp-memory` and `zep-memory-assistant`

Primary files:

- [`agent-with-mcp-memory/README.md`](https://github.com/patchy631/ai-engineering-hub/blob/main/agent-with-mcp-memory/README.md)
- [`agent-with-mcp-memory/server.py`](https://github.com/patchy631/ai-engineering-hub/blob/main/agent-with-mcp-memory/server.py)
- [`zep-memory-assistant/README.md`](https://github.com/patchy631/ai-engineering-hub/blob/main/zep-memory-assistant/README.md)

### What they demonstrate well

- persistent memory concepts
- external memory layers
- conversational recall over long-lived sessions

### Why they are lower priority for Helly v1

Helly is not primarily a general-purpose assistant. It is a transactional recruiting workflow system with explicit state.

The durable truth for Helly should be:

- relational state
- structured profile fields
- raw messages
- event logs

Memory layers may help later with personalization or long-running recruiter relationships, but they are not central to v1 architecture.

### Helly decision

Do not add a dedicated long-term agent memory subsystem in v1 unless a concrete use case appears that cannot be solved by structured persistence.

## 6.9 `deploy-agentic-rag`

Primary files:

- [`README.md`](https://github.com/patchy631/ai-engineering-hub/blob/main/deploy-agentic-rag/README.md)
- [`server.py`](https://github.com/patchy631/ai-engineering-hub/blob/main/deploy-agentic-rag/server.py)

### What it demonstrates well

- minimum viable service wrapper
- API-serving idea for an AI subsystem

### Why it is not enough for Helly

It lacks:

- stateful workflow discipline
- job orchestration rigor
- idempotency handling
- domain model complexity
- eventing and audit depth

### Helly decision

Not suitable as a backbone. Only useful as a reminder that AI capabilities should be wrapped behind service interfaces.

## 7. Relevance Matrix

| Repository Area | Use for Helly | Decision |
| --- | --- | --- |
| `parlant-conversational-agent` | structured flow control, guidelines, tool transitions | adopt pattern |
| `guidelines-vs-traditional-prompt` | prompt decomposition strategy | adopt principle |
| `groundX-doc-pipeline` | doc ingestion and async parse shape | adopt pattern |
| `audio-analysis-toolkit` | transcription contract and media analysis boundary | adopt pattern |
| `eval-and-observability` | tracing, benchmarks, quality metrics | adopt strongly |
| `context-engineering-workflow` | selective multi-source reasoning | adopt partially |
| `firecrawl-agent` | corrective/web fallback retrieval | defer |
| `agent-with-mcp-memory` | memory concept | optional later |
| `zep-memory-assistant` | long-term conversational memory | optional later |
| `deploy-agentic-rag` | minimal service shell | low value |

## 8. What Helly Must Build Itself

The repository does not provide production-ready solutions for the most important Helly-specific concerns.

These must be designed and implemented directly in Helly:

- Telegram webhook/update ingestion
- update deduplication and idempotency
- role-aware onboarding orchestration
- candidate and vacancy state machines
- raw message storage model
- recruiting domain schemas
- file registry and object storage lifecycle
- hard-filter matching logic
- vectorization and reranking pipeline tuned to recruiting
- interview wave logic
- candidate evaluation policy
- deletion flow semantics
- privacy and retention controls
- operations dashboards and admin tooling if needed

## 9. Architecture Decisions Derived from the Study

## 9.1 Deterministic Core, LLM Edge

The repository examples reinforce that Helly must place deterministic application logic at the center and use LLMs only at controlled boundaries:

- parse
- summarize
- ask
- rerank
- evaluate

The LLM should never own:

- profile completion truth
- workflow progression
- matching eligibility
- invitation concurrency
- deletion side effects

## 9.2 Service Interfaces over Vendor Lock-In

Multiple demos are tightly coupled to a provider or framework. Helly should instead define interfaces:

- `DocumentParser`
- `SpeechTranscriber`
- `LLMClient`
- `EmbeddingClient`
- `FileStorage`
- `EventBusOrQueue`

This gives implementation freedom while preserving a stable architecture.

## 9.3 Prompt Assets as Versioned Artifacts

Prompt logic should live as versioned assets with tests, not embedded inline across business code.

The repository repeatedly shows the benefit of separating:

- task purpose
- instruction set
- schema
- tool access
- guardrails

## 9.4 Evaluation from Day One

The repo's observability examples support a clear decision: Helly should not wait until late-stage polish to measure extraction and evaluation quality.

At minimum, every AI subsystem needs:

- prompt version
- model version
- input snapshot reference
- output snapshot
- validation result
- latency
- cost or token usage where available

## 10. Recommended Reuse Strategy

## 10.1 Reuse Category A: Use Immediately as Design Input

- `parlant-conversational-agent`
- `guidelines-vs-traditional-prompt`
- `groundX-doc-pipeline`
- `audio-analysis-toolkit`
- `eval-and-observability`

These should directly influence Helly's architecture and implementation rules.

## 10.2 Reuse Category B: Borrow Selectively Later

- `context-engineering-workflow`
- `firecrawl-agent`
- `agent-with-mcp-memory`
- `zep-memory-assistant`

These should only be introduced if a concrete product requirement demands them.

## 10.3 Reuse Category C: Ignore for v1

- local chatbot UI demos
- generic RAG "chat with docs" examples
- model comparison projects
- podcast, media generation, and unrelated agent workflows
- fine-tuning demos

## 11. Recommended Helly Documentation Inputs Derived from This Study

The repository study implies Helly should maintain the following internal docs:

- architecture blueprint
- prompt catalog
- state machine definitions
- AI evaluation plan
- event taxonomy
- storage and retention policy
- queue/job catalog
- failure mode catalog

This repository study is therefore an input, not a terminal document.

## 12. Final Recommendation

Helly should use `ai-engineering-hub` as a curated reference shelf, not as a scaffold.

The best extraction from the repository is:

- take conversational control patterns from Parlant-like examples
- take provider-abstracted ingestion patterns from document/audio examples
- take tracing and evaluation discipline from observability examples
- reject the temptation to turn core recruiting workflows into generic agent orchestration

For Helly, correctness, auditability, and state discipline matter more than agent novelty.
