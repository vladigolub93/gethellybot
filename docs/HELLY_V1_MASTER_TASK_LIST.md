# HELLY v1 Master Task List

End-to-End Execution List from Zero to Production

Version: 1.0  
Date: 2026-03-07

## 1. Purpose

This document is the single ordered execution list for Helly v1.

It translates the architecture and backlog documents into one linear implementation sequence from:

- repository bootstrap
- local development setup
- backend implementation
- staging readiness
- production deployment
- post-launch stabilization

This is the primary execution document to use while building the project.

Canonical next-phase note:

- the current implementation phase should follow `HELLY_V1_AGENT_OWNED_STAGE_REBUILD_PLAN.md`
- this master list remains valid as the full-program checklist, but stage-agent rebuild work now has priority over further hardening of the old shared-controller approach

## 2. How to Use This List

Rules:

- tasks are ordered by dependency, not by theme alone
- do not skip foundational tasks and jump into AI flows
- if a task changes architecture, update the architecture docs first
- if a task changes persistence or flow logic, update the relevant design doc in the same change

Legend:

- `P0`: critical path
- `P1`: important for MVP
- `P2`: hardening or post-MVP support

Status is intentionally omitted here. This file is meant to be updated during execution later if needed.

## 3. Phase 0: Project Initialization

### 0.1 Repository and Documentation Baseline

1. `P0` Confirm that the repository contains only the new Helly baseline docs and housekeeping files.
2. `P0` Commit and push the consolidated architecture file.
3. `P0` Freeze the documentation set as the current source of truth.
4. `P1` Add a lightweight changelog or architecture decision log if needed later.

### 0.2 Delivery Guardrails

5. `P0` Decide the backend language and framework baseline for implementation.
6. `P0` Confirm the queue strategy for v1:
   - Railway Redis-backed queue
   - or Postgres-backed queue
7. `P0` Confirm webhook-first production mode for Telegram.
8. `P0` Confirm Supabase project split:
   - staging
   - production
9. `P1` Confirm naming conventions for services, buckets, environments, and branches.

## 4. Phase 1: Backend Skeleton

### 1.1 Repository Structure

10. `P0` Create the new backend folder structure aligned with the architecture.
11. `P0` Create `apps/api`, `apps/worker`, and optional `apps/scheduler`.
12. `P0` Create shared `src/` module boundaries.
13. `P0` Create `prompts/`, `migrations/`, `tests/`, and `scripts/` directories.
14. `P1` Add a root `Makefile` or equivalent task runner commands.

### 1.2 Tooling and Runtime

15. `P0` Initialize the Python project and dependency management.
16. `P0` Add FastAPI application bootstrap.
17. `P0` Add worker bootstrap.
18. `P0` Add scheduler bootstrap if needed.
19. `P0` Add environment config loader.
20. `P0` Add structured logger.
21. `P0` Add pytest and test config.
22. `P1` Add formatting and linting config.

### 1.3 Railway Readiness

23. `P0` Make the API service runnable with a single start command.
24. `P0` Make the worker service runnable with a single start command.
25. `P1` Make the scheduler service runnable with a single start command.
26. `P0` Add health endpoint for Railway.
27. `P1` Add readiness checks for database connectivity.

## 5. Phase 2: Database and Storage Foundation

### 2.1 Supabase Database Setup

28. `P0` Configure SQLAlchemy/Alembic against Supabase Postgres.
29. `P0` Create baseline migration setup.
30. `P0` Add support for `pgvector`.
31. `P0` Validate local migration workflow against Supabase-compatible Postgres.

### 2.2 Core Tables

32. `P0` Create `users`.
33. `P0` Create `user_consents`.
34. `P0` Create `files`.
35. `P0` Create `raw_messages`.
36. `P0` Create `state_transition_logs`.
37. `P0` Create `job_execution_logs`.
38. `P0` Create `notifications`.
39. `P0` Create `outbox_events`.

### 2.3 Supabase Storage

40. `P0` Implement `FileStorage` abstraction.
41. `P0` Implement Supabase Storage adapter.
42. `P0` Define private bucket strategy.
43. `P1` Add signed URL or controlled retrieval support.
44. `P1` Add content hashing and duplicate artifact handling.

## 6. Phase 3: Telegram Transport Layer

### 3.1 Telegram Ingress

45. `P0` Implement Telegram webhook endpoint.
46. `P0` Normalize inbound Telegram updates.
47. `P0` Persist every inbound update to `raw_messages`.
48. `P0` Add dedupe by Telegram update ID.
49. `P0` Add correlation ID propagation from ingress.

### 3.2 Telegram Egress

50. `P0` Implement `TelegramGateway`.
51. `P0` Implement outbound send logic.
52. `P0` Persist outbound message records where relevant.
53. `P1` Add keyboard helpers for role selection and confirmations.
54. `P1` Add retry-safe outbound notification dispatch behavior.

## 7. Phase 4: Identity and Consent

### 4.1 User Resolution

55. `P0` Resolve or create user by Telegram identity.
56. `P0` Store contact details when shared.
57. `P0` Update display name and username snapshots.

### 4.2 Consent

58. `P0` Implement consent capture messaging.
59. `P0` Persist consent events in `user_consents`.
60. `P0` Block onboarding without consent.

### 4.3 Role Selection

61. `P0` Implement role selection UI.
62. `P0` Store role flags on user.
63. `P0` route candidate users into candidate flow.
64. `P0` route manager users into vacancy flow.

## 8. Phase 5: State Machine Framework

### 5.1 Shared State Infrastructure

65. `P0` Implement state transition helper utilities.
66. `P0` Implement guard evaluation layer.
67. `P0` Implement `state_transition_logs` writer.
68. `P0` Prevent direct ad hoc state mutation outside domain services.

### 5.2 Aggregate State Machines

69. `P0` Implement candidate profile state machine skeleton.
70. `P0` Implement vacancy state machine skeleton.
71. `P0` Implement match lifecycle state machine skeleton.
72. `P0` Implement interview session state machine skeleton.
73. `P1` Implement notification state machine handling.

### 5.3 State-Aware Conversation Layer

73A. `P0` Define the runtime contract for state-aware AI assistance:
   - current state
   - allowed actions
   - missing required data
   - latest user message
   - recent state-local context
73B. `P0` Implement bounded AI decision schema for in-state assistance.
73C. `P0` Implement backend validation of AI-proposed actions before any state transition.
73D. `P0` Implement state policy families for candidate onboarding states.
73E. `P0` Implement state policy families for vacancy onboarding states.
73F. `P1` Implement state policy families for interview, manager review, and deletion states.
73G. `P1` Add integration tests for off-happy-path messages inside major states.
73H. `P0` Adopt `LangGraph` as the target orchestration runtime for user-facing workflow execution.
73I. `P0` Define the canonical LangGraph state contract for Helly stage agents.
73J. `P0` Implement graph selection from persisted DB state.
73K. `P0` Implement reusable graph nodes for context loading, KB grounding, intent detection, parse, action proposal, validation, and side effects.
73L. `P0` Migrate `CONTACT_REQUIRED`, `CONSENT_REQUIRED`, and `ROLE_SELECTION` into LangGraph stage agents.
73M. `P0` Migrate candidate onboarding stages into LangGraph stage agents.
73N. `P0` Migrate vacancy onboarding stages into LangGraph stage agents.
73O. `P1` Migrate interview invite and interview session handling into LangGraph stage agents.
73P. `P1` Migrate manager review and deletion confirmation into LangGraph stage agents.
73Q. `P1` Keep backend state machines authoritative and validate every agent-proposed action.
73R. `P1` Replace old ad-hoc Telegram routing branches with thin transport glue once graph paths are stable.
73S. `P0` Convert stage agents from help-oriented overlays into full stage owners that collect all data needed for next-state transition.
73T. `P0` Ensure every user-facing stage has its own prompt family, KB grounding rules, completion criteria, and structured output schema.
73U. `P0` Move stage completion logic out of scattered Telegram/domain handlers and into stage-agent execution contracts.
73V. `P1` Retire the shared controller as the primary runtime path once all major stage agents are graph-owned.

## 9. Phase 6: Candidate Onboarding

### 6.1 Candidate Persistence

74. `P0` Create `candidate_profiles`.
75. `P0` Create `candidate_profile_versions`.
76. `P0` Create `candidate_verifications`.

### 6.2 Candidate Intake Entry

77. `P0` Implement candidate flow entry after role selection.
78. `P0` Implement request for CV or equivalent experience input.
79. `P0` Accept document uploads.
80. `P0` Accept pasted text.
81. `P0` Accept voice description.

### 6.3 Candidate Parsing

82. `P0` Implement document parsing abstraction.
83. `P0` Implement speech transcription abstraction.
84. `P0` Store extracted text and transcripts.
85. `P0` Create `candidate_cv_extract` prompt asset.
86. `P0` Implement candidate summary extraction capability.

### 6.4 Candidate Summary Review

87. `P0` Present generated candidate summary to the user.
88. `P0` Implement summary approve action.
89. `P1` Implement summary correction loop.
90. `P1` Create `candidate_summary_merge` prompt asset.
91. `P1` Enforce maximum correction loop count.
92. `P1` Formalize candidate CV persistence contract:
   - parse CV into canonical `cv_text`
   - persist parsed `cv_text` as first-class candidate profile data
   - run summary analysis only from persisted `cv_text`
   - persist analysis result as first-class candidate summary data
   - enforce one review question:
     `Does this summary look correct, or would you like to change anything?`
   - allow exactly one candidate correction round
   - show final revised summary and require approval before continuing

### 6.5 Mandatory Candidate Questions

92A. `P1` Replace rigid summary-review commands with natural-language correction handling inside `SUMMARY_REVIEW`.
93. `P0` Implement salary question.
94. `P0` Implement location question.
95. `P0` Implement work format question.
96. `P0` Create `candidate_mandatory_field_parse` prompt asset.
97. `P0` Normalize candidate answers into structured fields.
98. `P1` Implement one follow-up per unresolved field.

### 6.6 Verification

99. `P0` Generate verification phrase.
100. `P0` Request verification video.
101. `P0` Store verification video in Supabase Storage.
102. `P0` Link verification attempt to profile.

### 6.7 Candidate Ready State

103. `P0` Implement `READY` eligibility validator.
104. `P0` Transition candidate to `READY` only when all conditions pass.
105. `P0` Emit event or outbox record for matching trigger.

## 10. Phase 7: Vacancy Onboarding

### 7.1 Vacancy Persistence

106. `P0` Create `vacancies`.
107. `P0` Create `vacancy_versions`.

### 7.2 Vacancy Intake Entry

108. `P0` Implement vacancy creation entrypoint.
109. `P0` Request JD or equivalent job description input.
110. `P0` Accept text JD.
111. `P0` Accept document JD.
112. `P0` Accept voice/video JD input.

### 7.3 Vacancy Parsing

113. `P0` Create `vacancy_jd_extract` prompt asset.
114. `P0` Implement JD extraction capability.
115. `P1` Create `vacancy_inconsistency_detect` prompt asset.
116. `P1` Implement inconsistency detection.

### 7.4 Vacancy Clarification

117. `P0` Ask for budget range.
118. `P0` Ask for countries allowed.
119. `P0` Ask for work format.
120. `P0` Ask for team size.
121. `P0` Ask for project description.
122. `P0` Ask for primary tech stack.
123. `P0` Create `vacancy_clarification_parse` prompt asset.
124. `P0` Parse clarification answers into normalized fields.
125. `P1` Implement one follow-up per unresolved field.

### 7.5 Vacancy Open State

126. `P0` Implement vacancy `OPEN` validator.
127. `P0` Transition vacancy to `OPEN` only after all requirements pass.
128. `P0` Emit outbox events for embedding refresh and matching.

## 11. Phase 8: AI Infrastructure and Prompt System

### 8.1 Prompt Runtime

128A. `P0` Implement prompt asset loader.
129. `P0` Implement prompt version resolution.
130. `P0` Implement JSON schema validation layer for AI outputs.
131. `P0` Implement AI trace metadata capture.

### 8.2 OpenAI Integration

132. `P0` Implement `LLMClient` with OpenAI adapter.
133. `P0` Implement model routing for extraction vs reasoning tasks.
134. `P1` Implement fallback model strategy hooks.

### 8.3 AI Observability

135. `P0` Store prompt version and model name with business-critical outputs.
136. `P1` Store token usage and latency where available.
137. `P1` Add AI error categorization.

## 12. Phase 9: Matching Engine

### 9.1 Matching Persistence

138. `P0` Create `matching_runs`.
139. `P0` Create `invite_waves`.
140. `P0` Create `matches`.

### 9.2 Embeddings

141. `P0` Implement candidate embedding refresh.
142. `P0` Implement vacancy embedding refresh.
143. `P0` Persist embeddings in `pgvector`.
144. `P1` Add vector index strategy if needed.

### 9.3 Hard Filters

145. `P0` Implement location compatibility filter.
146. `P0` Implement salary compatibility filter.
147. `P0` Implement work format compatibility filter.
148. `P0` Implement seniority compatibility filter.
149. `P0` Store hard-filter reason codes.

### 9.4 Deterministic Scoring

150. `P0` Implement skill overlap scoring.
151. `P0` Implement experience fit scoring.
152. `P0` Implement tech stack match scoring.
153. `P0` Implement deterministic breakdown persistence.

### 9.5 Reranking

154. `P1` Create `candidate_rerank` prompt asset.
155. `P1` Implement reranking capability.
156. `P1` Persist reranking explanation and rank position.

### 9.6 Matching Triggers

157. `P0` Trigger matching when vacancy opens.
158. `P0` Trigger matching when candidate becomes ready.
159. `P1` Trigger rematch on material profile changes.

## 13. Phase 10: Invitation Waves and Notifications

### 10.1 Notifications

160. `P0` Implement durable notification intents.
161. `P0` Implement notification dispatcher worker.
162. `P0` Implement send retry logic.

### 10.2 Invite Waves

163. `P0` Implement first wave creation.
163A. `P0` Link invite waves to `matching_runs` and persist invited match IDs per wave.
164. `P0` Implement invite count limits.
165. `P0` Implement invitation expiration timestamps.
166. `P1` Implement wave expansion policy when completion threshold is not reached.
166A. `P1` Schedule evaluation of active invite waves and enqueue expansion waves via background jobs.
166B. `P1` Stop wave expansion when shortlist is exhausted and avoid creating empty invite waves.
166C. `P1` Add configurable reminder/expiration tuning and escalation-aware wave policy beyond the baseline scheduler.

### 10.3 Candidate Invite UX

167. `P0` Send interview invitation message.
168. `P0` Implement `accept interview`.
169. `P0` Implement `skip opportunity`.
170. `P1` Implement invitation reminder messages.
170A. `P1` Add richer reminder variants and escalation rules for unresponsive invited candidates.

## 14. Phase 11: Interview Engine

### 11.1 Interview Persistence

171. `P0` Create `interview_sessions`.
172. `P0` Create `interview_questions`.
173. `P0` Create `interview_answers`.

### 11.2 Question Planning

174. `P0` Create `interview_question_plan` prompt asset.
175. `P0` Implement question plan generation.
176. `P0` Persist ordered question plan.

### 11.3 Session Lifecycle

177. `P0` Create interview session when invite is accepted.
178. `P0` Ask first question.
179. `P0` Track current question pointer.
180. `P0` Resume session from last unanswered question.

### 11.4 Answer Capture

181. `P0` Accept text interview answers.
182. `P0` Accept voice interview answers.
183. `P0` Accept video interview answers.
184. `P0` Store raw answer artifacts and transcripts.

### 11.5 Follow-Up Logic

185. `P1` Create `interview_followup_decision` prompt asset.
186. `P1` Implement follow-up generation logic.
187. `P0` Enforce maximum one follow-up per primary question.
188. `P0` Forbid follow-up to follow-up.

### 11.6 Interview Completion

189. `P0` Detect interview completion.
190. `P0` Transition session to `COMPLETED`.
191. `P0` Trigger evaluation job.
192. `P1` Implement session expiration.
193. `P1` Implement interview reminders.

## 15. Phase 12: Evaluation and Manager Review

### 12.1 Evaluation

194. `P0` Create `evaluation_results`.
195. `P0` Create `candidate_evaluate` prompt asset.
196. `P0` Implement final evaluation capability.
197. `P0` Persist strengths, risks, recommendation, and score.

### 12.2 Threshold Policy

198. `P0` Implement evaluation threshold policy.
199. `P0` Auto-reject below threshold.
200. `P0` Route above-threshold candidates to manager review.

### 12.3 Manager Package

201. `P0` Implement candidate package builder.
202. `P0` Include summary, CV/artifact, verification video, interview summary, evaluation.
203. `P0` Send manager candidate package notification.
203A. `P1` Improve manager package rendering from baseline structured notification content to richer artifact-style delivery.

### 12.4 Manager Actions

204. `P0` Implement `approve candidate`.
205. `P0` Implement `reject candidate`.
206. `P1` Implement candidate-visible outcome messaging if product policy allows.

### 12.5 Introduction

207. `P1` Implement introduction strategy abstraction.
208. `P1` Implement first introduction mode.
209. `P1` Log introduction event and result.
209A. `P1` Add richer introduction modes beyond the initial Telegram handoff.

## 16. Phase 13: Deletion and Lifecycle Controls

### 13.1 Candidate Deletion

210. `P1` Implement candidate deletion confirmation.
211. `P1` Mark profile as deleted.
212. `P1` Remove candidate from active matching.
213. `P1` Cancel pending invites/interviews where required.

### 13.2 Vacancy Deletion

214. `P1` Implement vacancy deletion confirmation.
215. `P1` Mark vacancy as deleted.
216. `P1` Stop future matching and wave generation.
217. `P1` Cancel active flows where required.

### 13.3 Retention and Access

218. `P1` Restrict access to deleted-user artifacts.
219. `P2` Add cleanup jobs for retention windows.

## 17. Phase 14: Test Coverage

### 14.1 Core Unit Tests

220. `P0` Test state transition rules.
221. `P0` Test hard filters.
222. `P0` Test deterministic scoring.
223. `P0` Test deletion side effects.

### 14.2 Integration Tests

224. `P0` Test Telegram update dedupe.
225. `P0` Test candidate onboarding happy path.
226. `P0` Test vacancy onboarding happy path.
227. `P0` Test invite to interview path.
228. `P0` Test evaluation and manager review path.

### 14.3 AI Contract Tests

229. `P0` Test schema adherence for extraction prompts.
230. `P1` Test rerank output schema.
231. `P1` Test evaluation output schema.
232. `P1` Test malformed AI output fallback handling.

### 14.4 End-to-End Tests

233. `P1` Test candidate ready to match to invite to interview to manager review.
234. `P1` Test deletion during active flow.

## 18. Phase 15: Observability and Operations

### 15.1 Logging and Metrics

235. `P0` Add structured request and job logs.
236. `P0` Add correlation IDs everywhere important.
237. `P1` Add funnel metrics for onboarding, matching, interviews, approvals.
238. `P1` Add AI latency and error metrics.

### 15.2 AI Evaluation Assets

239. `P1` Build candidate extraction benchmark dataset.
240. `P1` Build vacancy extraction benchmark dataset.
241. `P1` Build rerank benchmark fixtures.
242. `P1` Build evaluation benchmark fixtures.

### 15.3 Operational Controls

243. `P1` Add dead-letter handling for failed jobs.
244. `P1` Add manual replay strategy for safe jobs.
245. `P2` Add admin/operator troubleshooting scripts.

## 19. Phase 16: Environment and Deployment

### 16.1 Environment Contracts

246. `P0` Create `.env.example`.
247. `P0` Define all required env vars for API, worker, scheduler.
248. `P0` Separate local, staging, and production config expectations.

### 16.2 Railway Deployment

249. `P0` Add Railway-compatible start commands.
250. `P0` Add Railway service definitions or deployment notes.
251. `P0` Deploy API to staging.
252. `P0` Deploy worker to staging.
253. `P1` Deploy scheduler to staging if needed.

### 16.3 Supabase Setup

254. `P0` Create staging database and storage buckets.
255. `P0` Apply migrations to staging.
256. `P0` Verify storage access from staging runtime.

### 16.4 Telegram Webhook

257. `P0` Configure Telegram webhook to staging URL.
258. `P0` Validate end-to-end webhook delivery.
259. `P1` Add webhook secret validation if used.

## 20. Phase 17: Staging Validation

260. `P0` Run schema and migration smoke check.
261. `P0` Run candidate onboarding in staging.
262. `P0` Run vacancy onboarding in staging.
263. `P0` Run match generation in staging.
264. `P0` Run invitation flow in staging.
265. `P0` Run interview completion in staging.
266. `P0` Run manager review in staging.
267. `P0` Run deletion flows in staging.

### 17.1 Bug Fix Loop

268. `P0` Fix staging blockers.
269. `P0` Re-run broken flows until stable.
270. `P1` Tighten logs, retries, and recovery messaging based on staging behavior.

## 21. Phase 18: Production Launch Preparation

271. `P0` Create production Supabase project.
272. `P0` Create production storage buckets.
273. `P0` Provision Railway production services.
274. `P0` Configure production env vars.
275. `P0` Apply production migrations.
276. `P0` Point Telegram webhook to production.

### 18.1 Launch Checklist

277. `P0` Verify health endpoint.
278. `P0` Verify DB connectivity.
279. `P0` Verify storage access.
280. `P0` Verify OpenAI access.
281. `P0` Verify a complete smoke onboarding path in production.
282. `P0` Verify invite and interview flow in production.
283. `P0` Verify manager review delivery in production.

## 22. Phase 19: Production Stabilization

284. `P1` Monitor failed jobs and notification retries.
285. `P1` Monitor onboarding drop-off points.
286. `P1` Monitor AI extraction failure rate.
287. `P1` Monitor match quality and manager approval rate.
288. `P1` Triage production issues quickly.

### 19.1 First Hardening Pass

289. `P1` Refine prompt quality based on observed failures.
290. `P1` Improve follow-up/recovery messaging.
291. `P1` Improve matching thresholds if necessary.
292. `P2` Optimize vector retrieval and job throughput if load requires it.

## 23. Phase 20: Post-Launch Quality Work

293. `P2` Improve benchmark datasets using real anonymized failure cases if policy allows.
294. `P2` Add richer admin/operator tools.
295. `P2` Add more robust evaluation dashboards.
296. `P2` Prepare v1.x backlog for features deferred from launch.

## 24. Immediate Recommended Starting Point

The next execution slice should start with:

1. tasks `10-31` for project scaffold and runtime
2. tasks `32-44` for DB and storage foundation
3. tasks `45-64` for Telegram, identity, and consent
4. tasks `65-73` for state machine framework

Only after that should implementation move into:

- candidate onboarding
- vacancy onboarding
- AI extraction

## 25. Definition of Done for Each Task

A task is only complete when:

- implementation exists
- tests exist if applicable
- logs/observability are added where appropriate
- docs are updated if behavior changed
- retry/idempotency impact has been considered

## 26. Final Position

This file is the execution path from zero to production.

If we follow it in order, the project should stay aligned with the architecture. If we skip around and start with AI-heavy behavior before the runtime, persistence, and state layers are stable, the project will degrade quickly.
