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
- implemented so far: `CV_PENDING`, `SUMMARY_REVIEW`, `QUESTIONS_PENDING`, `VERIFICATION_PENDING`, `READY`

### Step 4. Vacancy State Policies

Goal:

- make manager onboarding states helpful without breaking flow

Priority states:

- `JD_PENDING`
- `CLARIFICATION_QA`
- `OPEN`

Status:

- in progress
- implemented so far: `JD_PENDING` runtime is mapped to `INTAKE_PENDING`, `CLARIFICATION_QA`, and `OPEN`

### Step 5. Interview and Review State Policies

Goal:

- support invite, active interview, manager review, and deletion confirmation states

Priority states:

- `INTERVIEW_INVITED`
- `INTERVIEW_IN_PROGRESS`
- `MANAGER_REVIEW`
- `DELETE_CONFIRMATION`

Status:

- in progress
- implemented so far: `INTERVIEW_INVITED`, `INTERVIEW_IN_PROGRESS`, `MANAGER_REVIEW`, `DELETE_CONFIRMATION`

### Step 6. Action Validation Layer

Goal:

- validate all AI-proposed actions against current state guards before any mutation

Deliverables:

- proposed-action validator
- no-op fallback when proposal is invalid
- structured logging for rejected proposals

Status:

- completed

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

Status:

- in progress
- controller-level regression coverage is in place for all major state families
- telegram routing regression coverage is now in place for key help-first interception cases across candidate intake, candidate questions, candidate ready, verification, manager intake, interview invite, and manager review
- routing coverage now also protects summary review help vs real correction input, delete-confirmation help flows, and manager-approve passthrough behavior
- routing coverage now also protects interview accept/skip passthrough, candidate/vacancy delete-confirm passthrough, and generic recovery fallback for users outside any active role flow
- routing coverage now also protects valid business-action passthrough for summary approval, questions answering, verification video submission, manager clarification answers, and manager rejection
- routing coverage now also protects candidate CV intake passthrough, manager JD intake passthrough, active interview answer passthrough, and cancel-delete passthrough for both candidate and vacancy flows
- routing coverage now also protects contact/consent/role gating at flow entry, including `/start`, contact share, and blocked role selection before prerequisites are satisfied
- routing coverage now also protects successful entry transitions for consent grant, contact-with-consent, and role-based onboarding start for both candidate and hiring manager
- routing coverage now also protects mixed-input onboarding paths across candidate and manager flows, including candidate CV intake over voice/document, manager JD intake over voice/video, and non-text recovery fallback outside any active role flow
- routing coverage now also protects post-intake multimodal paths, including interview answers over voice/video, candidate question answers over voice, manager clarification answers over voice, and document-based recovery fallback outside any active role flow
- routing coverage now also protects normalized action aliases and stricter flow-entry gating, including uppercase role selection, `accept` / `skip` interview aliases, and consent rejection before contact is shared
- routing coverage now also protects near-canonical phrasing variants across summary review, manager decisions, and deletion cancellation, including `approve profile`, `edit summary`, `approve`, `reject`, and `don't delete`
- routing coverage now also protects generic deletion aliases and summary-change phrasing, including `confirm delete`, `keep profile`, `keep vacancy`, and `change summary`
- routing coverage now also protects normalization variants such as trimmed whitespace around commands and consent aliases like `agree` / `consent`
- routing coverage now also protects uppercase normalization for core commands across summary approval, interview acceptance, manager decisions, and deletion confirmation
- routing coverage now also protects punctuation-normalized command handling across consent, summary approval, interview acceptance, manager rejection, and deletion confirmation

## 4. Current Next Task

The immediate next task is:

- Step 7:
  - broaden regression coverage and UX hardening
  - lock down the required in-state cases in integration tests
The foundation and first major state-policy slice are now live in runtime.
