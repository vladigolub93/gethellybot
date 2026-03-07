# HELLY v1 State-Aware Conversation Execution Plan

Execution Plan for Deterministic State Machines with AI-Managed In-State Assistance

Version: 1.0  
Date: 2026-03-07

## 1. Purpose

This document turns the new state-aware conversation model into an execution sequence for implementation.

It is narrower than the full product roadmap. It focuses only on replacing rigid step handlers with a safe, state-aware AI assistance layer.

## 2. Target Outcome

Helly should be able to:

- keep deterministic workflow control
- answer help and clarification questions inside the active state
- suggest alternative valid ways to complete the same requirement
- avoid repeating the same rigid prompt when the user is blocked or confused

## 3. Execution Order

### Step 1. Define Runtime Contract

Goal:

- define one shared contract for in-state AI assistance

Deliverables:

- state policy context object
- state-aware decision schema
- allowed-action registry
- state guidance registry

Status:

- completed

### Step 2. Upgrade Global Bot Controller

Goal:

- make `bot_controller` reason over current state, state goal, allowed actions, missing requirements, and state guidance

Deliverables:

- prompt/schema v2
- runtime parser mapping
- baseline fallback aligned to the same contract

Status:

- completed

### Step 3. Candidate State Policies

Goal:

- make candidate onboarding states helpful without breaking flow

Priority states:

- `CV_PENDING`
- `SUMMARY_REVIEW`
- `QUESTIONS_PENDING`
- `VERIFICATION_PENDING`
- `READY`

Status:

- in progress
- implemented so far: `CV_PENDING`, `SUMMARY_REVIEW`, `QUESTIONS_PENDING`, `VERIFICATION_PENDING`
- remaining priority state: `READY`

### Step 4. Vacancy State Policies

Goal:

- make manager onboarding states helpful without breaking flow

Priority states:

- `JD_PENDING`
- `CLARIFICATION_QA`
- `OPEN`

Status:

- in progress
- implemented so far: `JD_PENDING` runtime is mapped to `INTAKE_PENDING`, and `CLARIFICATION_QA`
- remaining priority state: `OPEN`

### Step 5. Interview and Review State Policies

Goal:

- support invite, active interview, manager review, and deletion confirmation states

Priority states:

- `INTERVIEW_INVITED`
- `INTERVIEW_IN_PROGRESS`
- `MANAGER_REVIEW`
- `DELETE_CONFIRMATION`

### Step 6. Action Validation Layer

Goal:

- validate all AI-proposed actions against current state guards before any mutation

Deliverables:

- proposed-action validator
- no-op fallback when proposal is invalid
- structured logging for rejected proposals

### Step 7. Regression and UX Hardening

Goal:

- lock the behavior down with integration coverage

Required regression cases:

- `I do not have a CV`
- `Why do you need this?`
- `What should I do next?`
- `I cannot record video now`
- `I do not have a formal JD`
- `Can I just paste the job details here?`

## 4. Current Next Task

The immediate next task is:

- Step 3 and Step 4 continuation:
  - add policy coverage for `READY` and `OPEN`
  - then move to invite/interview/review states
The foundation and first major state-policy slice are now live in runtime.
