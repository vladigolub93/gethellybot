# HELLY v1 Engineering Backlog

Initial Epic and Task Backlog for Architecture-First Delivery

Version: 1.0  
Date: 2026-03-07

## 1. Purpose

This document turns the implementation plan into an actionable initial backlog.

It is designed to be used as the basis for:

- issue creation
- sprint planning
- Cursor/Codex task execution
- dependency-aware implementation order

Task IDs in this document are proposed IDs, not system-generated IDs.

## 2. Priority Levels

- `P0`: critical path, blocks architecture or core flow
- `P1`: important for MVP completion
- `P2`: post-core hardening or quality multiplier

## 3. Epic Index

| Epic ID | Epic Name | Priority |
| --- | --- | --- |
| `E-01` | Project Foundation | `P0` |
| `E-02` | Identity and Consent | `P0` |
| `E-03` | Telegram Ingestion and Messaging | `P0` |
| `E-04` | File and Artifact Management | `P0` |
| `E-05` | Candidate Onboarding | `P0` |
| `E-06` | Vacancy Onboarding | `P0` |
| `E-07` | AI Parsing Layer | `P0` |
| `E-08` | Matching Engine | `P1` |
| `E-09` | Interview Engine | `P1` |
| `E-10` | Evaluation and Manager Review | `P1` |
| `E-11` | Notifications, Waves, and Scheduling | `P1` |
| `E-12` | Deletion and Data Lifecycle | `P1` |
| `E-13` | Observability and AI Eval | `P1` |
| `E-14` | Security and Launch Hardening | `P2` |

## 4. Epic Details

## 4.1 `E-01` Project Foundation

Goal:

- establish codebase, runtime, migration, and worker foundations

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-01-T01` | scaffold backend service structure | `P0` | none |
| `E-01-T02` | scaffold worker runtime and queue integration | `P0` | `E-01-T01` |
| `E-01-T03` | configure app settings and environment loading | `P0` | `E-01-T01` |
| `E-01-T04` | add migration framework and first empty migration | `P0` | `E-01-T01` |
| `E-01-T05` | define shared domain/result/error patterns | `P1` | `E-01-T01` |
| `E-01-T06` | set up test harness and CI basics | `P0` | `E-01-T01` |

Definition of done:

- service boots
- worker boots
- tests run
- migrations run locally

## 4.2 `E-02` Identity and Consent

Goal:

- create durable user identity and consent base

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-02-T01` | implement `users` schema and repository | `P0` | `E-01-T04` |
| `E-02-T02` | implement `user_consents` schema and repository | `P0` | `E-02-T01` |
| `E-02-T03` | build user resolution by Telegram identity | `P0` | `E-02-T01` |
| `E-02-T04` | implement consent capture flow and audit write | `P0` | `E-02-T02`, `E-03-T03` |
| `E-02-T05` | add role flag update logic | `P1` | `E-02-T03` |

## 4.3 `E-03` Telegram Ingestion and Messaging

Goal:

- make Telegram updates reliable and idempotent

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-03-T01` | implement webhook endpoint or polling ingress | `P0` | `E-01-T01` |
| `E-03-T02` | implement `raw_messages` schema | `P0` | `E-01-T04` |
| `E-03-T03` | persist raw inbound update before business processing | `P0` | `E-03-T01`, `E-03-T02` |
| `E-03-T04` | add dedupe on Telegram update ID | `P0` | `E-03-T03` |
| `E-03-T05` | implement outbound Telegram gateway abstraction | `P0` | `E-01-T01` |
| `E-03-T06` | implement outbound message persistence and correlation IDs | `P1` | `E-03-T05`, `E-03-T02` |
| `E-03-T07` | add reply markup helpers for role selection and confirmations | `P1` | `E-03-T05` |

## 4.4 `E-04` File and Artifact Management

Goal:

- register, store, and retrieve user artifacts safely

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-04-T01` | implement `files` schema | `P0` | `E-01-T04` |
| `E-04-T02` | create object storage abstraction | `P0` | `E-01-T01` |
| `E-04-T03` | implement Telegram file download flow | `P0` | `E-03-T05`, `E-04-T02` |
| `E-04-T04` | register uploaded artifacts with metadata and hashes | `P0` | `E-04-T01`, `E-04-T03` |
| `E-04-T05` | support text-only pseudo-artifacts for pasted input | `P1` | `E-04-T01` |

## 4.5 `E-05` Candidate Onboarding

Goal:

- deliver candidate profile creation to `READY`

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-05-T01` | implement `candidate_profiles` schema | `P0` | `E-01-T04` |
| `E-05-T02` | implement `candidate_profile_versions` schema | `P0` | `E-05-T01` |
| `E-05-T03` | implement candidate state machine service | `P0` | `E-05-T01`, `E-13-T01` |
| `E-05-T04` | implement candidate role selection entrypoint | `P0` | `E-02-T05`, `E-03-T07` |
| `E-05-T05` | implement CV/text/voice submission handling | `P0` | `E-04-T04`, `E-05-T03` |
| `E-05-T06` | implement summary review and approve flow | `P0` | `E-07-T03`, `E-05-T02` |
| `E-05-T07` | implement summary correction loop | `P1` | `E-05-T06`, `E-07-T04` |
| `E-05-T08` | implement mandatory Q&A flow | `P0` | `E-07-T05`, `E-05-T03` |
| `E-05-T09` | implement `candidate_verifications` schema | `P0` | `E-01-T04` |
| `E-05-T10` | implement verification phrase generation and video upload flow | `P0` | `E-05-T09`, `E-04-T04` |
| `E-05-T11` | implement `READY` eligibility validator | `P0` | `E-05-T06`, `E-05-T08`, `E-05-T10` |

## 4.6 `E-06` Vacancy Onboarding

Goal:

- deliver vacancy creation to `OPEN`

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-06-T01` | implement `vacancies` schema | `P0` | `E-01-T04` |
| `E-06-T02` | implement `vacancy_versions` schema | `P0` | `E-06-T01` |
| `E-06-T03` | implement vacancy state machine service | `P0` | `E-06-T01`, `E-13-T01` |
| `E-06-T04` | implement manager role selection and vacancy creation entrypoint | `P0` | `E-02-T05`, `E-03-T07` |
| `E-06-T05` | implement JD/text/voice/video submission handling | `P0` | `E-04-T04`, `E-06-T03` |
| `E-06-T06` | implement vacancy clarification flow | `P0` | `E-07-T06`, `E-06-T03` |
| `E-06-T07` | implement vacancy open validator | `P0` | `E-06-T06`, `E-06-T02` |

## 4.7 `E-07` AI Parsing Layer

Goal:

- create reusable AI service boundaries and first-wave prompts

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-07-T01` | implement `LLMClient` abstraction and prompt loader | `P0` | `E-01-T01` |
| `E-07-T02` | implement speech transcription abstraction | `P0` | `E-01-T01` |
| `E-07-T03` | implement `candidate_cv_extract` capability | `P0` | `E-07-T01`, `E-07-T02` |
| `E-07-T04` | implement `candidate_summary_merge` capability | `P1` | `E-07-T01` |
| `E-07-T05` | implement `candidate_mandatory_field_parse` capability | `P0` | `E-07-T01` |
| `E-07-T06` | implement `vacancy_jd_extract` capability | `P0` | `E-07-T01`, `E-07-T02` |
| `E-07-T07` | implement `vacancy_clarification_parse` capability | `P0` | `E-07-T01` |
| `E-07-T08` | implement provider-independent schema validation wrapper | `P0` | `E-07-T01` |
| `E-07-T09` | implement AI trace persistence hooks | `P1` | `E-13-T03`, `E-07-T01` |

## 4.8 `E-08` Matching Engine

Goal:

- generate ranked candidate shortlists

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-08-T01` | implement normalized matching profile builders | `P0` | `E-05-T11`, `E-06-T07` |
| `E-08-T02` | implement embedding generation and refresh jobs | `P0` | `E-08-T01`, `E-07-T01` |
| `E-08-T03` | add vector storage support | `P0` | `E-01-T04` |
| `E-08-T04` | implement hard-filter rules engine | `P0` | `E-08-T01` |
| `E-08-T05` | implement `matching_runs` and `matches` schema | `P0` | `E-01-T04` |
| `E-08-T06` | implement deterministic scoring engine | `P0` | `E-08-T04`, `E-08-T05` |
| `E-08-T07` | implement `candidate_rerank` capability | `P1` | `E-07-T01`, `E-08-T06` |
| `E-08-T08` | implement match persistence with version snapshot refs | `P0` | `E-08-T05`, `E-08-T06` |
| `E-08-T09` | trigger matching on vacancy open and candidate ready | `P1` | `E-08-T08`, `E-11-T01` |

## 4.9 `E-09` Interview Engine

Goal:

- run structured AI interviews inside Telegram

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-09-T01` | implement `interview_sessions`, `interview_questions`, `interview_answers` schema | `P0` | `E-01-T04` |
| `E-09-T02` | implement interview session state machine | `P0` | `E-09-T01`, `E-13-T01` |
| `E-09-T03` | implement `interview_question_plan` capability | `P0` | `E-07-T01`, `E-08-T08` |
| `E-09-T04` | implement invitation accept/skip flow | `P0` | `E-11-T03`, `E-09-T02` |
| `E-09-T05` | implement question progression and current pointer logic | `P0` | `E-09-T02`, `E-09-T03` |
| `E-09-T06` | implement answer capture for text/voice/video | `P0` | `E-04-T04`, `E-07-T02`, `E-09-T05` |
| `E-09-T07` | implement `interview_followup_decision` capability | `P1` | `E-07-T01`, `E-09-T06` |
| `E-09-T08` | enforce one-follow-up-per-question rule | `P0` | `E-09-T07`, `E-09-T05` |
| `E-09-T09` | implement session completion and evaluation trigger | `P0` | `E-09-T05`, `E-10-T02` |

## 4.10 `E-10` Evaluation and Manager Review

Goal:

- evaluate candidates and route them to manager review

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-10-T01` | implement `evaluation_results` schema | `P0` | `E-01-T04` |
| `E-10-T02` | implement `candidate_evaluate` capability | `P0` | `E-07-T01`, `E-09-T01` |
| `E-10-T03` | implement threshold policy engine | `P0` | `E-10-T02` |
| `E-10-T04` | implement manager candidate package builder | `P0` | `E-10-T01`, `E-05-T10`, `E-09-T09` |
| `E-10-T05` | implement manager approve/reject actions | `P0` | `E-10-T04`, `E-03-T07` |
| `E-10-T06` | implement introduction strategy interface and first strategy | `P1` | `E-10-T05` |

## 4.11 `E-11` Notifications, Waves, and Scheduling

Goal:

- make async delivery and invitation waves reliable

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-11-T01` | implement `notifications` and `outbox_events` schema | `P0` | `E-01-T04` |
| `E-11-T02` | implement notification dispatcher worker | `P0` | `E-03-T05`, `E-11-T01` |
| `E-11-T03` | implement invite creation and expiration logic | `P0` | `E-08-T08`, `E-11-T02` |
| `E-11-T04` | implement `invite_waves` schema and wave policy service | `P0` | `E-01-T04` |
| `E-11-T05` | implement wave scheduler | `P1` | `E-11-T03`, `E-11-T04` |
| `E-11-T06` | implement reminders for invites and interviews | `P1` | `E-11-T02`, `E-09-T02` |

## 4.12 `E-12` Deletion and Data Lifecycle

Goal:

- make deletion flows safe, auditable, and operationally complete

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-12-T01` | implement candidate deletion flow | `P1` | `E-05-T11`, `E-09-T02`, `E-11-T02` |
| `E-12-T02` | implement vacancy deletion flow | `P1` | `E-06-T07`, `E-11-T05` |
| `E-12-T03` | implement file access restriction and retention markers | `P1` | `E-04-T02`, `E-14-T02` |
| `E-12-T04` | implement cleanup jobs for deleted entities | `P2` | `E-12-T01`, `E-12-T02` |

## 4.13 `E-13` Observability and AI Eval

Goal:

- make the system debuggable and quality-measurable

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-13-T01` | implement `state_transition_logs` schema and logging helper | `P0` | `E-01-T04` |
| `E-13-T02` | implement `job_execution_logs` schema and worker logging helper | `P0` | `E-01-T04`, `E-01-T02` |
| `E-13-T03` | add structured application logs and correlation IDs | `P0` | `E-01-T01` |
| `E-13-T04` | add metrics for onboarding, matching, interview, and evaluation funnels | `P1` | `E-13-T03` |
| `E-13-T05` | create benchmark fixture sets for AI capabilities | `P1` | `E-07-T03`, `E-07-T06`, `E-10-T02` |
| `E-13-T06` | add AI regression test runner | `P1` | `E-13-T05` |

## 4.14 `E-14` Security and Launch Hardening

Goal:

- reduce operational risk before production rollout

Tasks:

| Task ID | Task | Priority | Depends On |
| --- | --- | --- | --- |
| `E-14-T01` | implement secrets and config hardening review | `P2` | `E-01-T03` |
| `E-14-T02` | implement signed/private file access strategy | `P1` | `E-04-T02` |
| `E-14-T03` | audit data exposure in manager package and outbound messages | `P1` | `E-10-T04` |
| `E-14-T04` | add dead-letter handling and operator recovery path | `P1` | `E-13-T02`, `E-11-T02` |
| `E-14-T05` | define launch readiness checklist and runbook | `P2` | all major epics |

## 5. Suggested Build Order

Recommended execution order:

1. `E-01`
2. `E-03`
3. `E-02`
4. `E-04`
5. `E-13`
6. `E-07`
7. `E-05`
8. `E-06`
9. `E-08`
10. `E-11`
11. `E-09`
12. `E-10`
13. `E-12`
14. `E-14`

This order front-loads transport, persistence, observability, and AI interfaces before feature breadth.

## 6. First Slice Recommendation

If we want the smallest end-to-end slice before broadening scope, implement:

- `E-01`
- `E-03`
- `E-02`
- `E-04`
- `E-13-T01` to `E-13-T03`
- `E-07-T01` to `E-07-T08`
- `E-05-T01` to `E-05-T11`
- `E-06-T01` to `E-06-T07`

This yields:

- working Telegram ingestion
- user/contact/consent
- candidate ready flow
- vacancy open flow
- usable logs and AI boundaries

## 7. Definition of Done for Backlog Items

A task is not done unless:

- code is implemented
- tests cover normal and invalid paths
- logs or traces are added where relevant
- docs are updated if behavior or schema changed
- idempotency impact is considered for async or Telegram-facing work

## 8. Recommended Task Packaging for Cursor/Codex

Good task sizes:

- one schema plus repository layer
- one domain transition flow
- one AI capability contract plus tests
- one worker job plus persistence

Bad task sizes:

- "implement matching"
- "build Telegram bot"
- "make AI smart"

Tasks should stay narrow enough to preserve architectural correctness and reviewability.

## 9. Final Position

This backlog is intentionally architecture-first.

If the implementation jumps directly to matching, interviews, or "AI behavior" before the storage, state, and logging base is solid, Helly will accumulate expensive rework. This backlog is designed to prevent that.
