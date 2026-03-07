# HELLY v1 State-Aware Conversation Model

Deterministic State Machines with AI-Managed In-State Assistance

Version: 1.0  
Date: 2026-03-07

## 1. Purpose

This document defines how Helly should behave as an intelligent conversational system without handing workflow control to an unconstrained AI agent.

Helly must avoid brittle interactions such as:

- user: `I do not have a CV`
- bot: `Please send your CV`
- user: `What should I do then?`
- bot: `Please send your CV`

The correct design is:

- the backend keeps workflow control
- the AI helps intelligently inside the active state

## 2. Core Rule

Helly must use:

- deterministic backend state machines for authority
- state-aware AI policy for conversation inside the current state

Helly must not use:

- free-form agent autonomy over workflow progression
- prompt-only flow control
- direct LLM state mutation

In short:

- backend owns `state`
- AI owns `understanding and response strategy inside the state`

## 3. Required Runtime Contract

For every active state, the runtime must provide the AI layer with:

- current state
- allowed actions
- blocked actions
- missing required data
- latest user message
- recent relevant context

The AI layer must return a bounded decision object such as:

- interpreted user intent
- whether the message is valid business input, help-seeking, objection, clarification, off-topic, or small talk
- suggested reply
- optional proposed action
- optional structured parse result

The backend must then:

- validate the proposed action against the current state
- either keep the same state and reply
- or execute a valid state transition

## 4. Global Rules

### 4.1 The AI May Stay in the Same State

The correct result for many user messages is:

- helpful reply
- no state change

This is required for:

- help requests
- clarification questions
- objections
- unsupported but recoverable input

### 4.2 The AI Must Offer Allowed Alternatives

If the same state supports multiple valid ways to complete the requirement, the AI should explain them.

Example in `CV_PENDING`:

- upload a CV
- paste experience as text
- send a voice description
- export LinkedIn as PDF and upload it

### 4.3 The AI Must Not Skip Mandatory Requirements

The AI may help the user complete a requirement differently, but it may not remove the requirement.

### 4.4 The AI Must Be State-Specific

Helly should not rely on one generic assistant prompt for every situation.

It should use:

- one global controller
- one policy family per major state
- specialized conductors where needed, such as interview turns

## 5. State Policy by Flow

## 5.1 Entry States

### `CONTACT_REQUIRED`

Goal:

- obtain a valid Telegram contact object

In-state AI behavior:

- explain why contact is required
- explain how to use the contact button
- answer whether a plain text phone number is enough
- redirect unsupported input back to contact sharing

### `CONSENT_REQUIRED`

Goal:

- obtain explicit consent

In-state AI behavior:

- explain why consent is needed
- explain what data is stored
- answer privacy and deletion questions

### `ROLE_SELECTION`

Goal:

- choose `Candidate` or `Hiring Manager`

In-state AI behavior:

- explain the difference between roles
- recommend the appropriate role based on user intent

## 5.2 Candidate States

### `CV_PENDING`

Goal:

- obtain usable candidate experience input

Allowed completion actions:

- upload CV document
- paste experience as text
- send voice description

In-state AI behavior:

- explain acceptable input formats
- explain what to do if the user has no CV
- suggest LinkedIn PDF export as an option
- suggest typing a short work summary
- suggest voice dictation instead of document upload

### `CV_PROCESSING`

Goal:

- wait for parsing/transcription/extraction to complete

In-state AI behavior:

- explain what the system is processing
- explain whether the user should wait or resend

### `SUMMARY_REVIEW`

Goal:

- approve the summary or collect one correction round

Required review question:

`Does this summary look correct, or would you like to change anything?`

In-state AI behavior:

- explain that the summary is based on the parsed CV text
- ask what exactly is wrong
- support one correction round
- show the revised final version before approval

### `QUESTIONS_PENDING`

Goal:

- collect salary, location, and work format

In-state AI behavior:

- explain why each field matters for matching
- help normalize vague salary or work format answers
- ask one follow-up when required data is missing

### `VERIFICATION_PENDING`

Goal:

- obtain verification video with the required phrase

In-state AI behavior:

- explain why verification is needed
- explain how to record the video
- explain what to say

### `READY`

Goal:

- keep the candidate eligible for matching

In-state AI behavior:

- explain what happens next
- answer update and deletion questions
- explain that Helly offers jobs only when strong matches are found

## 5.3 Hiring Manager States

### `JD_PENDING`

Goal:

- obtain a usable job description source

In-state AI behavior:

- explain acceptable formats
- suggest text, voice, or internal role brief if there is no formal JD
- explain which details help matching most

### `JD_PROCESSING`

Goal:

- wait for extraction to complete

In-state AI behavior:

- explain what Helly is extracting
- explain that clarification questions will follow

### `CLARIFICATION_QA`

Goal:

- resolve required vacancy fields

In-state AI behavior:

- explain why a field is required
- normalize vague answers
- ask focused follow-up when a field remains unresolved

### `OPEN`

Goal:

- keep the vacancy active for matching and review

In-state AI behavior:

- explain what Helly is doing next
- explain why candidates are shown only after interviews

## 5.4 Interview and Review States

### `INTERVIEW_INVITED`

Goal:

- get clear `accept` or `skip`

In-state AI behavior:

- explain what the interview is
- explain duration and supported answer formats

### `INTERVIEW_ACTIVE`

Goal:

- complete the current interview session

In-state AI behavior:

- ask one main question at a time
- optionally ask one follow-up
- redirect politely if the user goes off-topic
- resume from the correct question after interruption

### `MANAGER_REVIEW`

Goal:

- get approve or reject decision

In-state AI behavior:

- explain what the scores mean
- restate strengths and risks in plain language

### `DELETE_CONFIRMATION`

Goal:

- confirm destructive action safely

In-state AI behavior:

- explain consequences of deletion
- explain what will be cancelled
- require explicit confirmation

## 6. Recommended Prompt Architecture

The runtime should use:

- one global `bot_controller`
- one `state_policy` family per major state
- specialized capabilities for extraction, parsing, interviewing, reranking, and evaluation

Suggested state policy families:

- `entry/contact_required`
- `entry/consent_required`
- `entry/role_selection`
- `candidate/cv_pending_policy`
- `candidate/cv_processing_policy`
- `candidate/summary_review_policy`
- `candidate/questions_pending_policy`
- `candidate/verification_pending_policy`
- `candidate/ready_policy`
- `vacancy/jd_pending_policy`
- `vacancy/jd_processing_policy`
- `vacancy/clarification_policy`
- `vacancy/open_policy`
- `interview/invited_policy`
- `interview/active_policy`
- `review/manager_review_policy`
- `review/delete_confirmation_policy`

## 7. Required Backend Validation Rule

Every AI-produced conversational decision must be checked against:

- active state
- allowed actions for that state
- domain validators

If the AI proposes an invalid action:

- keep the current state
- send recovery/help response
- do not mutate business data

## 8. Intended Implementation Direction

Helly should evolve from:

- rigid step handlers with fixed canned replies

to:

- deterministic state machines
- state policy registry
- state-aware AI controller
- safe proposed-action validation
- richer in-state assistance for every major step
