# HELLY v1 Direct Contact Matching Flow

Version: 1.0  
Date: 2026-03-11

## Purpose

This document replaces the active interview-first funnel with a simpler direct-contact funnel.

The old AI interview runtime remains in the codebase as a dormant path for a future premium feature, but it is no longer part of the primary product flow.

## Active Product Decision

Helly should no longer require an in-chat AI interview before contact sharing.

The primary flow is now:

1. Helly finds a candidate-vacancy match.
2. Helly shows the match to both sides in Telegram.
3. The candidate can approve or skip the vacancy.
4. The manager can approve or skip the candidate.
5. As soon as both sides approve the same match, Helly immediately shares contact details with both sides.

No interview questions, interview sessions, evaluation summaries, or post-interview manager review are required in the active flow.

## Core Product Rules

### Candidate Side

When Helly finds matching vacancies for a candidate:

1. Helly sends up to `3` vacancy cards at a time.
2. Under each vacancy card the candidate can choose:
   - `Apply`
   - `Skip`
3. If the candidate applies:
   - the vacancy moves into manager review if it is not already there
   - the manager sees the candidate profile
4. If the manager has already approved that match:
   - the candidate should see a stronger CTA like `Connect` / `Share contacts`
   - if the candidate accepts, Helly shares contacts immediately
5. If the candidate skips:
   - the match closes
   - the same vacancy must not be shown again to the same candidate

### Manager Side

When Helly finds matching candidates for a vacancy:

1. Helly sends up to `3` candidate cards at a time.
2. Under each candidate card the manager can choose:
   - `Connect`
   - `Skip`
3. If the manager approves a candidate:
   - if the candidate already applied, Helly shares contacts immediately
   - otherwise the candidate receives a manager-approved vacancy card and can accept or skip
4. If the manager skips:
   - the match closes
   - the same candidate must not be shown again for the same vacancy

## State Model

The active match lifecycle is now:

- `shortlisted`
- `manager_decision_pending`
- `candidate_decision_pending`
- `candidate_applied`
- `manager_interview_requested`
- `approved`
- `manager_skipped`
- `candidate_skipped`
- `filtered_out`
- `expired`

Important interpretation:

- `manager_interview_requested` is repurposed as a legacy internal status meaning:
  - manager approved the candidate
  - candidate decision is now pending
  - no interview should be created

The following statuses remain legacy/dormant and should not be produced by the active runtime:

- `invited`
- `interview_queued`
- `accepted`
- `interview_completed`
- `candidate_declined_interview`
- `manager_review`
- `rejected`
- `auto_rejected`

## Contact Sharing Rule

Contact sharing must happen exactly once per approved match.

When both sides approve:

1. mark match `approved`
2. create an introduction event
3. send manager contact details to the candidate
4. send candidate contact details to the manager

## Uniqueness Rule

For a given `candidate_profile_id + vacancy_id` pair:

- once the pair has entered any real flow state other than `filtered_out`
- it must not be surfaced again as a new candidate/vacancy suggestion

This includes:

- candidate skipped
- manager skipped
- candidate applied
- manager approved
- approved

## Batch and Cap Rules

The existing batching rules remain active:

- candidate vacancy batch size: `3`
- manager candidate batch size: `3`
- candidate max active opportunities: `10`
- vacancy max active candidate pipeline: `10`

Under this direct-contact flow, these caps now refer to pending mutual-approval opportunities, not interview sessions.

## Conversational Rules

Candidate and manager agents should talk about:

- matching
- review
- connect / contact sharing
- waiting for more profiles / roles

They should not describe the current active flow as an interview funnel.

## Implementation Notes

The interview subsystem is intentionally not deleted.

It should remain available behind a disabled path for future premium work:

- voice call interview
- phone-based interview
- WebApp-based interview

But the active product flow must not depend on:

- interview session creation
- interview question planning
- interview answer collection
- evaluation generation
- post-interview manager approval

## Required Runtime Outcomes

After this redesign:

1. A candidate can reach contact sharing without an interview.
2. A manager can reach contact sharing without an interview.
3. Asking to find more vacancies/candidates must continue to work.
4. Already seen candidate-vacancy pairs must stay unique.
5. User-facing copy must consistently describe direct connection, not interview.
