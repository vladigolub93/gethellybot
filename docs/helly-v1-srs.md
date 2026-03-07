# HELLY v1

AI-Powered Telegram Recruitment Matching Platform  
Software Requirements Specification (SRS)

This document is the master specification for Helly v1 and should be used as the primary reference for future implementation tasks in Cursor/Codex.

## 1. Product Overview

### 1.1 Product Name

Helly

### 1.2 Product Type

Telegram-first AI recruiting platform.

### 1.3 Product Goal

Helly automates early-stage recruiting by:

- collecting structured candidate profiles
- collecting structured job vacancy profiles
- performing AI-based candidate-vacancy matching
- conducting short AI-driven interviews for matched candidates
- delivering only qualified candidates to hiring managers

The platform reduces noise in recruiting and replaces manual resume screening with structured conversational data collection.

## 2. System Roles

### 2.1 Candidate

A user who is looking for a job.

Capabilities:

- upload CV
- approve or edit AI-generated CV summary
- answer mandatory profile questions
- complete video verification
- receive job match invitations
- complete AI interview
- delete profile

Candidates do not browse jobs manually.

Jobs are offered only when the system detects a strong match.

### 2.2 Hiring Manager

A user representing a company hiring for a position.

Capabilities:

- create job vacancies
- provide job description
- answer vacancy clarification questions
- manage multiple vacancies
- receive candidate profiles after interviews
- approve or reject candidates
- delete vacancies

Hiring managers never see candidates until interviews are completed.

## 3. System Principles

### 3.1 Telegram-first design

All user interaction occurs inside Telegram.

Supported input types:

- text
- document
- voice message
- video message
- video note
- contact
- location

Every message must be stored in raw form.

### 3.2 Conversational AI

The system must behave like a conversational assistant.

All messages pass through an LLM layer that:

- understands intent
- extracts structured data
- generates human-like responses
- supports small talk

### 3.3 State Machine Control

Despite conversational interaction, the system must enforce a strict flow.

The backend state machine controls:

- step progression
- allowed actions
- validation rules

The LLM cannot change system state directly.

## 4. Candidate Flow

### 4.1 Candidate Start

User starts bot.

System requests:

Share contact

After contact is shared, user chooses role:

Candidate or Hiring Manager.

### 4.2 CV Upload

Candidate uploads CV.

Supported formats:

- PDF
- DOCX
- TXT
- pasted text
- voice description of experience

System:

1. extracts text
2. runs CV analysis prompt
3. generates structured summary

### 4.3 CV Summary Approval

Candidate sees generated summary.

Options:

Approve summary  
Edit summary

If editing is requested:

Candidate provides corrections.

LLM merges corrections into summary.

Maximum correction loops: 3.

### 4.4 Mandatory Candidate Questions

Candidate answers mandatory questions:

Salary expectations  
Current location  
Preferred work format:

- remote
- hybrid
- office

Answers can be provided via:

- text
- voice
- video

Answers are processed by LLM parser.

If information is incomplete, the system may ask one follow-up question.

### 4.5 Video Verification

Candidate records a short video message.

The system provides a unique phrase to say.

Purpose:

Confirm the candidate is a real person.

Verification video is stored and later sent to hiring managers.

### 4.6 Candidate Ready State

Candidate profile becomes READY.

Candidate enters matching pool.

## 5. Hiring Manager Flow

### 5.1 Vacancy Creation

Hiring manager provides job description.

Supported formats:

- text
- document
- voice
- video

System extracts structured data.

### 5.2 Job Description Analysis

AI analyzes job description.

Outputs:

- role title
- tech stack
- seniority
- project description
- required skills
- potential inconsistencies

Example inconsistency:

Listing multiple unrelated stacks (Java, Node, Python simultaneously).

### 5.3 Vacancy Clarification Questions

System asks mandatory questions:

Budget range  
Countries allowed for hiring  
Work format (remote/hybrid/office)  
Team size  
Project description  
Primary tech stack

Answers processed by LLM parser.

### 5.4 Vacancy Activation

After required information is collected:

Vacancy becomes OPEN.

Multiple vacancies per manager are allowed.

## 6. Matching Engine

Matching is performed in several stages.

### 6.1 Hard Filters

Candidates must pass:

Location compatibility  
Work format compatibility  
Salary compatibility  
Seniority compatibility

Candidates failing hard filters are excluded.

### 6.2 Embedding Similarity

Profiles are converted into embeddings.

Vector search retrieves top candidates.

Typical retrieval size:

Top 50 candidates.

### 6.3 Deterministic Scoring

Candidates receive score based on:

Skill overlap  
Years of experience  
Tech stack match

Top 10 candidates selected.

### 6.4 LLM Reranking

LLM analyzes top candidates.

Outputs ranked shortlist.

Typical shortlist size:

3-6 candidates.

## 7. Interview Invitations

Selected candidates receive interview invitation.

Candidate options:

Accept interview  
Skip opportunity

## 8. AI Interview

Interview consists of:

5-7 questions related to vacancy.

Answers may be provided via:

text  
voice  
video

### 8.1 Follow-Up Questions

If answer lacks important information:

System may generate one follow-up question.

Maximum follow-up per question: 1.

Follow-up to follow-up is not allowed.

## 9. Interview Waves

To avoid waiting for unresponsive candidates:

System invites candidates in waves.

Example:

Invite 3 candidates.

If fewer than 2 complete interview:

Invite more candidates.

## 10. Interview Evaluation

After interview completion:

AI evaluates:

Candidate CV  
Candidate answers  
Job requirements

Outputs:

Final score  
Strengths  
Risks  
Recommendation

Candidates below threshold are rejected automatically.

## 11. Manager Candidate Review

Manager receives candidate package:

CV  
Candidate summary  
Verification video  
Interview summary  
Evaluation report

Manager options:

Approve candidate  
Reject candidate

## 12. Candidate Introduction

If approved:

Helly introduces candidate and manager in Telegram.

A new chat is created or both users are connected.

## 13. Deletion Flows

### Candidate deletion

Candidate may delete profile.

Requires confirmation.

Deletion triggers:

Cancel interviews  
Remove from matching pool

### Vacancy deletion

Manager may delete vacancy.

Requires confirmation.

Deletion triggers:

Cancel matching  
Cancel interviews

## 14. Non Functional Requirements

### Reliability

System must process Telegram updates idempotently.

Duplicate updates must not break flow.

### Scalability

System must support:

10k candidates  
1000 vacancies

Matching must run asynchronously.

### Performance

Typical response time:

1-3 seconds for normal messages.

Matching jobs may run asynchronously.

### Logging

All important events must be logged:

state transitions  
matching events  
interview results

## 15. Data Model (High Level)

Entities:

User  
CandidateProfile  
CandidateVerification  
Vacancy  
VacancyProfile  
Match  
InterviewSession  
InterviewAnswer  
EvaluationResult  
File  
RawMessage  
StateTransitionLog

## 16. LLM Usage

LLM is used for:

conversation understanding  
response generation  
CV analysis  
JD analysis  
answer parsing  
follow-up generation  
candidate reranking  
interview evaluation

## 17. Security

Sensitive data stored securely.

User consent required before profile creation.

Files stored securely.

## 18. Future Extensions

Potential features:

- company profiles
- multi-stage interviews
- calendar integration
- ATS integrations
- analytics dashboard

End of SRS
