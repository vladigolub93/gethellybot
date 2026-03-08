# HELLY v1 Agent Intent Ownership Matrix

Inventory of Remaining Backend Intent Logic Across Migrated Stages

Version: 1.0  
Date: 2026-03-08

## 1. Purpose

This document inventories where user-message meaning is still decided outside the intended AI stage agent boundary.

It exists to support:

- [HELLY_V1_AGENT_OWNERSHIP_COMPLETION_PLAN.md](./HELLY_V1_AGENT_OWNERSHIP_COMPLETION_PLAN.md)

The goal is to make it explicit, stage by stage, where intent ownership still lives in backend code instead of in the stage agent prompt/runtime.

## 2. Interpretation Rules

### `Current intent owner`

This field identifies which layer currently decides the meaning of the user's message:

- `agent-first`: the stage agent is already the primary meaning owner
- `mixed`: stage agent exists, but backend heuristics still materially classify the message
- `backend-heavy`: stage routing is present, but message meaning is still mainly derived from backend-side logic

### `Target intent owner`

For all user-facing stages in this plan, the target is:

- `agent-first`

### `Backend logic to remove`

This field identifies the concrete deterministic logic that still needs to be removed or demoted so the stage agent fully owns interpretation.

## 3. Matrix

| Stage | Current intent owner | Target intent owner | Remaining backend logic to remove | Primary files |
| --- | --- | --- | --- | --- |
| `CONTACT_REQUIRED` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; actual contact attachment remains a transport-level Telegram event by design | [entry.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/entry.py) |
| `ROLE_SELECTION` | `mixed` | `agent-first` | hard-coded `candidate` / `hiring manager` completion mapping, regex help patterns | [entry.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/entry.py) |
| `CV_PENDING` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; backend now only executes validated `send_cv_text` handoff for text submissions | [candidate.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/candidate.py), [candidate_profile/service.py](/Users/vladigolub/Desktop/gethellybot/src/candidate_profile/service.py) |
| `SUMMARY_REVIEW` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; vacancy-side mirror stage still pending for symmetry | [candidate.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/candidate.py), [candidate_profile/service.py](/Users/vladigolub/Desktop/gethellybot/src/candidate_profile/service.py) |
| `QUESTIONS_PENDING` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; backend still executes parsed payload and voice path by design | [candidate.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/candidate.py), [candidate_profile/service.py](/Users/vladigolub/Desktop/gethellybot/src/candidate_profile/service.py) |
| `VERIFICATION_PENDING` | `mixed` | `agent-first` | deterministic `latest_message_type == video` completion rule, regex help patterns | [candidate.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/candidate.py) |
| `READY` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; backend only executes validated `delete_profile` handoff after agent-owned meaning decision | [candidate.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/candidate.py), [candidate_profile/service.py](/Users/vladigolub/Desktop/gethellybot/src/candidate_profile/service.py) |
| `INTAKE_PENDING` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; backend now only executes validated `send_job_description_text` handoff for text submissions | [manager.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/manager.py), [vacancy/service.py](/Users/vladigolub/Desktop/gethellybot/src/vacancy/service.py) |
| `VACANCY_SUMMARY_REVIEW` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; adjacent clarification stage still pending for same depth of intent ownership | [manager.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/manager.py), [vacancy/service.py](/Users/vladigolub/Desktop/gethellybot/src/vacancy/service.py) |
| `CLARIFICATION_QA` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; backend only executes parsed clarification payload after agent-owned meaning decision | [manager.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/manager.py), [vacancy/service.py](/Users/vladigolub/Desktop/gethellybot/src/vacancy/service.py) |
| `OPEN` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; backend only executes validated `delete_vacancy` handoff after agent-owned meaning decision | [manager.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/manager.py), [vacancy/service.py](/Users/vladigolub/Desktop/gethellybot/src/vacancy/service.py) |
| `INTERVIEW_INVITED` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; backend now executes validated invitation actions directly instead of owning message meaning | [candidate.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/candidate.py), [interview/service.py](/Users/vladigolub/Desktop/gethellybot/src/interview/service.py) |
| `INTERVIEW_IN_PROGRESS` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; voice/video answer execution still uses backend media path by design | [candidate.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/candidate.py), [interview/service.py](/Users/vladigolub/Desktop/gethellybot/src/interview/service.py) |
| `MANAGER_REVIEW` | `mixed` | `agent-first` | regex help patterns, deterministic approve/reject aliases | [manager.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/manager.py) |
| `DELETE_CONFIRMATION` | `agent-first (mostly completed)` | `agent-first` | live validation still needed; backend now executes validated delete actions instead of owning meaning | [deletion.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/deletion.py), [candidate_profile/service.py](/Users/vladigolub/Desktop/gethellybot/src/candidate_profile/service.py), [vacancy/service.py](/Users/vladigolub/Desktop/gethellybot/src/vacancy/service.py) |

## 4. Highest-Risk Stages

These stages should be fixed first because they most directly convert free-form text into wrong actions:

1. `SUMMARY_REVIEW`
2. `VACANCY_SUMMARY_REVIEW`
3. `INTERVIEW_IN_PROGRESS`
4. `QUESTIONS_PENDING`
5. `DELETE_CONFIRMATION`

## 5. Stage Families Still Using Deterministic Intent Nodes

### Entry

- [src/graph/stages/entry.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/entry.py)

Current pattern:

- regex help classification
- deterministic completion detection
- non-help fallback to `unknown`

### Candidate

- [src/graph/stages/candidate.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/candidate.py)

Current pattern:

- regex help classification per stage
- deterministic command alias mapping
- fallback to generic stage-completion intent in some stages

### Manager

- [src/graph/stages/manager.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/manager.py)

Current pattern:

- regex help classification per stage
- deterministic command alias mapping
- fallback non-empty text -> summary correction in `VACANCY_SUMMARY_REVIEW`

### Deletion

- [src/graph/stages/deletion.py](/Users/vladigolub/Desktop/gethellybot/src/graph/stages/deletion.py)

Current pattern:

- regex help classification
- deterministic confirm/cancel alias mapping

## 6. Domain Services Still Interpreting Raw User Text

The following services still do more than execute validated actions:

### Candidate

- [src/candidate_profile/service.py](/Users/vladigolub/Desktop/gethellybot/src/candidate_profile/service.py)

Remaining interpretation examples:

- summary review command parsing
- deletion confirm/cancel parsing

### Vacancy

- [src/vacancy/service.py](/Users/vladigolub/Desktop/gethellybot/src/vacancy/service.py)

Remaining interpretation examples:

- vacancy summary review command parsing
- vacancy deletion confirm/cancel parsing

### Interview

- [src/interview/service.py](/Users/vladigolub/Desktop/gethellybot/src/interview/service.py)

Remaining interpretation examples:

- invitation accept/skip parsing before execution

## 7. Recommended Removal Order

Strict order:

1. `SUMMARY_REVIEW`
2. `VACANCY_SUMMARY_REVIEW`
3. `INTERVIEW_IN_PROGRESS`
4. `QUESTIONS_PENDING`
5. `DELETE_CONFIRMATION`
6. `ROLE_SELECTION`
7. `MANAGER_REVIEW`

## 8. Definition of Done

This matrix is considered complete when:

- every user-facing stage has a clear current-vs-target ownership status
- all remaining deterministic meaning logic is mapped to concrete files
- there is a documented removal order for execution
