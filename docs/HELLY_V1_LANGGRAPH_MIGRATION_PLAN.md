# HELLY v1 LangGraph Migration Plan

Execution Plan for Migrating Helly to LangGraph Stage Agents

Version: 1.0  
Date: 2026-03-07

## 1. Purpose

This document turns the LangGraph stage-agent architecture decision into an execution sequence.

It does not replace the full implementation roadmap.

It focuses only on:

- introducing LangGraph
- migrating stage orchestration
- preserving backend state authority

## 2. Migration Goal

Helly should move from:

- Telegram routing
- shared controller
- shared state-assistance layer

to:

- LangGraph stage router
- one bounded stage agent per major workflow stage
- backend validation bridge

## 3. Constraints

During migration:

- Postgres state machines remain authoritative
- repositories and domain services remain reusable
- no agent may mutate state directly
- all side effects still go through backend services
- migration should happen stage-family by stage-family

## 4. Execution Order

### Step 1. LangGraph Foundation

Deliver:

- `langgraph` dependency
- `src/graph/` module boundary
- shared Helly graph state contract
- graph bootstrap and runner

Status:

- in progress
- implemented:
  - dependency baseline
  - `src/graph/` foundation package
  - canonical `HellyGraphState`
  - stage registry
  - foundation stage graph bootstrap
  - router skeleton
  - runtime compiler with sequential fallback when `langgraph` is not importable in the local environment

### Step 2. Backend Validation Bridge

Deliver:

- adapter from graph action proposal to backend validator
- standard validated action result contract
- common no-op and rejection handling

Status:

- in progress
- implemented:
  - graph-to-backend action validation adapter
  - normalized validation result contract
  - graph node integration for action validation

### Step 3. Entry Stage Agents

Migrate:

- `CONTACT_REQUIRED`
- `CONSENT_REQUIRED`
- `ROLE_SELECTION`

Exit:

- `/start` and early onboarding no longer depend on old branchy Telegram handlers for decisioning

Status:

- in progress
- implemented:
  - entry-stage graph service
  - graph-driven reply path for `CONTACT_REQUIRED`
  - graph-driven reply path for `CONSENT_REQUIRED`
  - graph-driven reply path for `ROLE_SELECTION`
  - Telegram identity assistance now tries the entry stage graph before falling back to the old controller

### Step 4. Candidate Onboarding Agents

Migrate:

- `CV_PENDING`
- `SUMMARY_REVIEW`
- `QUESTIONS_PENDING`
- `VERIFICATION_PENDING`
- `READY`

Exit:

- candidate journey is graph-driven from CV request through ready state

Status:

- in progress
- implemented:
  - first candidate-stage graph slice for `CV_PENDING`
  - graph-driven help handling for `CV_PENDING`
  - graph-driven help handling for `SUMMARY_REVIEW`
  - graph-driven help handling for `QUESTIONS_PENDING`
  - graph-driven help handling for `VERIFICATION_PENDING`
  - non-help candidate experience input still falls through to the existing backend intake path
  - non-help summary approval/edit input still falls through to the existing backend summary-review path
  - non-help mandatory-question answers still fall through to the existing backend question parser path
  - non-help verification submission still falls through to the existing backend video-verification path

### Step 5. Hiring Manager Onboarding Agents

Migrate:

- `INTAKE_PENDING`
- `CLARIFICATION_QA`
- `OPEN`

Exit:

- manager vacancy onboarding is graph-driven

### Step 6. Interview and Review Agents

Migrate:

- `INTERVIEW_INVITED`
- `INTERVIEW_IN_PROGRESS`
- `MANAGER_REVIEW`
- `DELETE_CONFIRMATION`

Exit:

- invitation, interview, review, and deletion confirmation all run through bounded stage agents

### Step 7. Routing Simplification

Deliver:

- remove old duplicated help interception branches
- keep Telegram layer as transport and normalization glue
- centralize stage execution entrypoint through LangGraph

### Step 8. Regression and Production Hardening

Deliver:

- graph-path integration tests
- migration parity tests against old behavior
- production smoke tests for candidate and manager flows

## 5. Definition of Done

The migration is complete when:

- all major user-facing stages execute through LangGraph
- old state-aware routing/controller logic is no longer the main orchestration layer
- backend state transitions remain validated and auditable
- Telegram transport is reduced to ingress/egress plumbing
