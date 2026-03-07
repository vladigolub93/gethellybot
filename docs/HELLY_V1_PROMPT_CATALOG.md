# HELLY v1 Prompt Catalog

AI Capability Inventory and Contract Design

Version: 1.0  
Date: 2026-03-07

## 1. Purpose

This document defines the prompt and AI capability architecture for Helly v1.

It exists to stop prompt logic from becoming an untracked set of scattered strings in application code.

For every AI capability, this document defines:

- business purpose
- input contract
- output contract
- model policy
- validation rules
- fallback behavior
- evaluation ownership

## 2. Core Prompting Principles

## 2.1 One Capability, One Prompt Asset Family

Each discrete AI job should have its own prompt asset family.

Examples:

- candidate CV extraction
- vacancy JD extraction
- interview question planning
- candidate reranking
- evaluation

Do not merge unrelated behaviors into one giant prompt.

## 2.2 Structured Output Is Mandatory for Business Writes

If the result will mutate state or stored business data, the output must be schema-bound and validated.

## 2.3 Prompt Versioning Is Mandatory

Every AI response stored in business records should reference:

- capability name
- prompt version
- model name

## 2.4 Recovery Messaging Is Separate from Extraction

User-facing fallback messages should not be mixed into structured extraction prompts.

## 2.5 Human-Like Tone, System-Like Discipline

Helly may sound conversational, but the prompt layer must remain strict about:

- required fields
- allowed enums
- ambiguity handling
- no unsupported inference beyond policy

## 3. Recommended Prompt Repository Layout

```text
prompts/
  candidate/
    cv_extract/
      SYSTEM.md
      SCHEMA.json
      EXAMPLES.md
      TEST_CASES.yaml
      CHANGELOG.md
    summary_merge/
      SYSTEM.md
      SCHEMA.json
      EXAMPLES.md
      TEST_CASES.yaml
      CHANGELOG.md
    mandatory_field_parse/
      SYSTEM.md
      SCHEMA.json
      EXAMPLES.md
      TEST_CASES.yaml
      CHANGELOG.md
  vacancy/
    jd_extract/
    clarification_parse/
    inconsistency_detect/
  interview/
    question_plan/
    followup_decision/
    answer_parse/
  matching/
    rerank/
  evaluation/
    candidate_evaluate/
  messaging/
    recovery/
    small_talk/
    role_selection/
```

## 4. Standard Prompt Asset Files

## 4.1 `SYSTEM.md`

Contains:

- role instructions
- scope
- behavioral constraints
- output rules

## 4.2 `SCHEMA.json`

Contains the exact machine-validated output schema.

## 4.3 `EXAMPLES.md`

Contains:

- few-shot examples
- edge cases
- failure examples

## 4.4 `TEST_CASES.yaml`

Contains:

- representative inputs
- expected fields
- known edge-case assertions

## 4.5 `CHANGELOG.md`

Contains:

- version history
- reason for prompt changes
- quality impact notes

## 5. Capability Catalog

## 5.1 `candidate_cv_extract`

Purpose:

- convert candidate CV, pasted experience text, or voice-transcribed experience into a structured candidate summary draft

Primary inputs:

- extracted text from CV or equivalent source
- transcript text if voice/video
- optional locale/language context

Output contract:

- normalized target role
- seniority estimate
- years of experience estimate
- primary skills
- tech stack
- domain experience
- recent roles
- education if present
- languages if present
- unresolved ambiguities

Validation rules:

- output must be valid JSON schema
- seniority must be within allowed enum set
- skills must be arrays, not comma strings
- unresolved fields must be explicitly marked instead of hallucinated

Fallback behavior:

- if extraction confidence is too low, mark draft incomplete and ask for clarification or resubmission

Recommended model policy:

- low temperature
- extraction-oriented model

Evaluation owner:

- AI extraction benchmark dataset

## 5.2 `candidate_summary_merge`

Purpose:

- merge user corrections into existing candidate summary draft without losing validated information unnecessarily

Primary inputs:

- existing summary JSON
- user correction text/transcript
- optionally explicit field-level correction hints

Output contract:

- revised summary JSON
- changed fields list
- unresolved conflicts list

Validation rules:

- only supported fields may be updated
- correction should not invent unsupported claims
- output must preserve required schema completeness

Fallback behavior:

- if user correction is too ambiguous, return conflict markers and request clarification

## 5.3 `candidate_mandatory_field_parse`

Purpose:

- parse salary, location, and work format from candidate answers

Primary inputs:

- answer text or transcript
- target field name
- locale/currency hints if available

Output contract:

- field name
- normalized value
- confidence
- needs_followup boolean
- followup_reason

Validation rules:

- work format must map to `remote`, `hybrid`, or `office`
- salary must normalize into structured range if possible
- location must separate text from normalized country if derivable

Fallback behavior:

- return `needs_followup = true` with explicit missing reason

## 5.4 `vacancy_jd_extract`

Purpose:

- turn JD text/transcript into a structured vacancy draft

Primary inputs:

- extracted JD text
- transcript text if voice/video source

Output contract:

- role title
- seniority
- primary stack
- secondary stack
- responsibilities
- required skills
- nice-to-have skills
- project description
- implicit budget clues if any
- unresolved fields

Validation rules:

- required and nice-to-have should be separated
- stack values should be arrays
- ungrounded inferred budget must not be treated as confirmed budget

Fallback behavior:

- produce partial draft with unresolved flags rather than overfilling

## 5.5 `vacancy_clarification_parse`

Purpose:

- parse manager answers to mandatory vacancy clarification questions

Primary inputs:

- field target
- answer text/transcript
- existing vacancy draft

Output contract:

- field name
- normalized value
- confidence
- needs_followup boolean
- followup_reason

Validation rules:

- countries must normalize to ISO codes where possible
- work format must map to enum
- team size must normalize to integer or range
- budget should capture min/max/currency/period if present

## 5.6 `vacancy_inconsistency_detect`

Purpose:

- identify potential ambiguity or contradictions in a vacancy description

Primary inputs:

- vacancy draft JSON
- extracted source text

Output contract:

- list of inconsistency findings
- severity per finding
- suggested clarification topics

Validation rules:

- findings must be evidence-backed from source text or normalized fields
- this capability must not mutate vacancy state directly

Fallback behavior:

- empty findings list is acceptable

## 5.7 `interview_question_plan`

Purpose:

- generate the initial 5 to 7 interview questions for a candidate-vacancy pair

Primary inputs:

- vacancy normalized profile
- candidate approved summary
- match scoring gaps
- maximum question count

Output contract:

- ordered question list
- question goals
- linked concern or skill gap per question

Validation rules:

- question count must be within configured range
- questions should avoid repeating already settled facts
- questions must be vacancy-relevant

Fallback behavior:

- use deterministic fallback template set if generation fails repeatedly

Recommended model policy:

- medium reasoning strength
- low to medium temperature

## 5.8 `interview_followup_decision`

Purpose:

- decide whether one follow-up is justified for a given answer

Primary inputs:

- current question
- answer text/transcript
- vacancy requirements
- candidate gap context

Output contract:

- ask_followup boolean
- followup_question text if needed
- rationale
- missing_information list

Validation rules:

- must not ask follow-up if one was already used
- must not ask follow-up that simply rephrases the same question without narrowing the gap

## 5.9 `interview_answer_parse`

Purpose:

- transform free-form answer into structured evaluation-ready signals

Primary inputs:

- answer text/transcript
- source question

Output contract:

- concise parsed answer summary
- evidence snippets
- claimed years/skills/tools if present
- ambiguity flags

Validation rules:

- claims must stay grounded in answer text
- schema must not force unsupported fields

## 5.10 `candidate_rerank`

Purpose:

- rerank already shortlisted candidate matches after deterministic scoring

Primary inputs:

- vacancy normalized profile
- candidate approved summary
- deterministic score breakdown
- hard-filter status and notes

Output contract:

- rank position
- score
- strengths
- concerns
- hiring-fit summary

Validation rules:

- reranker may only rank among candidates already passed through deterministic filtering
- output must not override hard-filter failures

## 5.11 `candidate_evaluate`

Purpose:

- produce final interview-based evaluation for a candidate-vacancy match

Primary inputs:

- candidate approved summary
- vacancy normalized profile
- interview questions
- interview answers
- parsed answer summaries

Output contract:

- final score
- recommendation
- strengths
- risks
- missing requirements
- manager-facing summary

Validation rules:

- output recommendation must be one of allowed enums
- all claims should be attributable to source material
- thresholding is not decided by prompt alone; application policy applies after output

Recommended model policy:

- stronger reasoning model
- low temperature

## 5.12 `response_copywriter`

Purpose:

- generate concise user-facing natural language while preserving deterministic business outcome

Primary inputs:

- state-driven intent
- domain metadata
- approved wording policy

Output contract:

- short response text only

Validation rules:

- cannot change business decision
- cannot promise unsupported actions

This capability is optional in early implementation. Template-driven messaging is acceptable initially.

## 6. Messaging Prompt Families

Messaging prompt families should be separate from data extraction.

Recommended families:

- `messaging/recovery`
- `messaging/small_talk`
- `messaging/role_selection`
- `messaging/deletion_confirmation`
- `messaging/interview_invitation_copy`

These prompts should never return business-state JSON.

## 7. Model Routing Policy

## 7.1 Extraction Tasks

Tasks:

- CV extraction
- JD extraction
- clarification parsing
- answer parsing

Policy:

- favor cheaper, lower-variance models if quality is sufficient
- keep temperature near zero

## 7.2 Reasoning Tasks

Tasks:

- reranking
- interview plan
- evaluation

Policy:

- use stronger reasoning-capable models
- keep temperature low enough for consistency

## 7.3 Speech Processing

Transcription may use a dedicated speech provider. Transcript text then feeds downstream prompts.

## 8. Validation Pipeline

Every capability that produces structured output should pass:

1. raw provider response capture
2. schema validation
3. domain validation
4. state-context validation
5. persistence or fallback

Example:

If `candidate_mandatory_field_parse` returns `work_format = onsite`, schema may pass if string-based, but domain validation must reject it and request normalization or follow-up.

## 9. Fallback Strategy

Fallback levels:

1. retry same capability once if provider error is transient
2. retry with fallback model if configured
3. return partial/needs-followup output if schema allows
4. escalate to user recovery or operator review path

Do not silently discard failed AI outputs.

## 10. Prompt Metadata to Store

For every business-critical AI call, store:

- capability name
- prompt version
- model name
- provider name
- input reference IDs
- output validation result
- latency
- token usage if available

Do not always store full prompt bodies in DB if repository versioning already preserves them; storing version reference is usually enough.

## 11. Evaluation Plan by Capability

| Capability | Evaluation Type | Minimum Dataset Focus |
| --- | --- | --- |
| `candidate_cv_extract` | structured extraction accuracy | varied CV layouts, multilingual edge cases, sparse CVs |
| `candidate_summary_merge` | merge correctness | conflicting edits, short corrections, ambiguous corrections |
| `candidate_mandatory_field_parse` | normalization accuracy | salary formats, locations, work-format phrases |
| `vacancy_jd_extract` | structured extraction accuracy | sparse JDs, overloaded stacks, nonstandard wording |
| `vacancy_clarification_parse` | field parse accuracy | budget ranges, countries, team size, mixed formats |
| `vacancy_inconsistency_detect` | precision-focused eval | true contradictions vs harmless variety |
| `interview_question_plan` | qualitative + rubric eval | relevance, redundancy, coverage, gap targeting |
| `interview_followup_decision` | policy adherence eval | follow-up necessity and one-follow-up limit |
| `interview_answer_parse` | grounded parsing accuracy | vague vs concrete answers, voice transcript noise |
| `candidate_rerank` | ranking quality | compare against recruiter-labeled order |
| `candidate_evaluate` | recommendation agreement | compare to curated evaluation gold set |

## 12. Prompt Change Management

Any prompt change that affects business data should require:

- version bump
- changelog entry
- regression check against test cases
- note of expected impact

If a prompt changes output shape, `SCHEMA.json` must change in the same revision.

## 13. Anti-Patterns to Avoid

Do not:

- embed long prompts inline in service code
- combine extraction and user-facing chat in one capability
- rely on prompt wording without schema enforcement
- let prompts decide workflow progression
- change prompts without benchmark re-runs

## 14. First-Wave Implementation Priority

Prompts to implement first:

1. `candidate_cv_extract`
2. `candidate_summary_merge`
3. `candidate_mandatory_field_parse`
4. `vacancy_jd_extract`
5. `vacancy_clarification_parse`
6. `interview_question_plan`
7. `interview_followup_decision`
8. `candidate_rerank`
9. `candidate_evaluate`

Later:

- `vacancy_inconsistency_detect`
- `interview_answer_parse`
- `response_copywriter`

## 15. Final Position

Prompt quality in Helly matters, but prompt organization matters just as much.

If prompt assets are versioned, validated, benchmarked, and isolated by capability, Helly can evolve safely. If prompts become ad hoc strings in business code, quality will decay and debugging will become extremely expensive.
