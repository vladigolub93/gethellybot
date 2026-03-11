# Helly Telegram WebApp SRS

## 1. Purpose

Helly Telegram WebApp is a read-only Telegram Mini App opened from the existing Helly Telegram bot.

The WebApp must run on top of the current Helly production system:

- Python `FastAPI` backend
- existing PostgreSQL database
- existing Telegram bot user base
- existing candidate, vacancy, matching, interview, and evaluation flows
- existing Railway deployment

This document replaces the generic WebApp SRS and aligns the feature with the actual repository, actual schema, and actual funnel already implemented in Helly.

## 2. Product Scope

The MVP WebApp is a mobile-first dashboard for:

- `candidate`
- `hiring_manager`
- `admin`
- `unknown`

The WebApp is strictly read-only in MVP.

The WebApp does not create, edit, approve, reject, or trigger workflow actions. Those actions continue to happen inside the Telegram bot chat.

## 3. Real System Alignment

The original draft SRS assumed a generic recruiting system with `applications` and a separate Next.js app.

The actual Helly system works differently:

- there is no `applications` table
- the main user-facing recruiting unit is `matches`
- candidate intake is stored in `candidate_profiles` and `candidate_profile_versions`
- vacancy intake is stored in `vacancies` and `vacancy_versions`
- interviews are stored in `interview_sessions`, `interview_questions`, and `interview_answers`
- interview outcomes are stored in `evaluation_results`
- final introductions are stored in `introduction_events`
- current deploy/runtime stack is one `FastAPI` service plus worker and scheduler on Railway

Because of that, the WebApp must be implemented as:

- a WebApp frontend served by the existing `FastAPI` API service
- read-only API endpoints inside the existing backend
- role-aware queries over current Helly tables

## 4. Goals

The WebApp must give users visibility into the current recruiting state without making them scroll through Telegram chat history.

Candidate goals:

- see matched vacancies and applied opportunities
- see current opportunity stage
- see interview state
- see vacancy details already known to the system
- see interview summary and evaluation outcome when available

Hiring manager goals:

- see owned vacancies
- see candidate pipeline per vacancy
- see candidate summaries already stored in the system
- see interview summaries and evaluation outputs when available

Admin goals:

- see the same dashboards without ownership restriction

Unknown goals:

- receive a clean blocked-access screen with instructions to continue in Telegram first

## 5. Roles

### 5.1 Candidate

Resolved when:

- `users.is_candidate = true`, or
- there is an active `candidate_profile` for the user and no stronger role override exists

Candidate can:

- list own opportunity cards
- open own opportunity detail view
- view own profile snapshot
- view interview summary / strengths / risks / recommendation / score for own completed interview if present

Candidate cannot:

- view other candidates
- view hiring manager-only vacancy pipelines
- mutate any recruiting state

### 5.2 Hiring Manager

Resolved when:

- `users.is_hiring_manager = true`, or
- there are manager-owned vacancies for the user and no stronger role override exists

Hiring manager can:

- list own vacancies
- open vacancy detail view
- list candidates attached to own vacancy through `matches`
- open candidate-in-context detail view for a specific match
- see interview and evaluation package for that match

Hiring manager cannot:

- view another manager’s vacancies or candidates
- mutate workflow state

### 5.3 Admin

Admin is not a first-class DB role today.

For WebApp MVP, admin access is resolved by Telegram user id from environment configuration:

- `TELEGRAM_WEBAPP_ADMIN_USER_IDS`

Admin can:

- list all vacancies
- list all candidate opportunities / matches
- open any vacancy detail
- open any match detail

Admin remains read-only.

### 5.4 Unknown

Resolved when:

- Telegram user is authenticated but cannot be mapped to candidate, hiring manager, or admin

Unknown user sees a blocked screen:

> You do not have access to the Helly dashboard yet.  
> Continue with Helly in Telegram first.  
> Once Helly identifies your role, this dashboard will unlock.

## 6. Telegram WebApp Integration

The WebApp is launched from a Telegram bot button.

Production URL target for BotFather will be:

- `https://<production-api-domain>/webapp`

The frontend must read Telegram `initData` from the Telegram WebApp SDK and send it to backend authentication.

Backend must:

- verify Telegram WebApp signature
- extract Telegram user identity
- resolve Helly role
- return a short-lived signed session token for subsequent API requests

## 7. Authentication

### 7.1 Auth endpoint

`POST /webapp/api/auth/telegram`

Request:

```json
{
  "initData": "query_id=...&user=...&auth_date=...&hash=..."
}
```

Response:

```json
{
  "sessionToken": "signed-token",
  "session": {
    "telegramUserId": 123456,
    "userId": "uuid-or-null",
    "role": "candidate",
    "displayName": "John Doe"
  }
}
```

### 7.2 Verification rules

Backend must:

- verify signature using Telegram WebApp validation rules and current bot token
- reject invalid or expired payload
- resolve role from actual Helly data
- issue a short-lived signed backend session token

### 7.3 API auth after login

All subsequent WebApp API requests use:

- `Authorization: Bearer <sessionToken>`

No separate cookie/session table is required for MVP.

## 8. Data Model Mapping

### 8.1 Core entities

- `users`
- `candidate_profiles`
- `candidate_profile_versions`
- `vacancies`
- `vacancy_versions`
- `matches`
- `interview_sessions`
- `evaluation_results`
- `introduction_events`

### 8.2 Match-centric model

What the original SRS called “application” is mapped to `matches`.

That means:

- candidate dashboard lists matches for the candidate profile
- manager dashboard shows vacancy pipeline through matches
- interview results are displayed in the context of one match

### 8.3 Company name

There is no dedicated company-name field in the current schema.

Candidate and manager cards must therefore use fields that actually exist:

- vacancy role title
- project description
- work format
- budget
- allowed countries

The UI must not invent a company field.

## 9. Dashboard Information Architecture

## 9.1 Candidate dashboard

Home screen: `My Opportunities`

Each card represents one `match`.

Card fields:

- vacancy role title
- match stage
- interview state
- manager decision state
- last updated

Detail screen: `Opportunity Details`

Fields:

- vacancy role title
- budget
- work format
- allowed countries
- tech stack
- project description
- candidate summary snapshot
- interview summary
- evaluation recommendation
- strengths
- risks
- final score

All data is read-only.

## 9.2 Hiring manager dashboard

Home screen: `My Vacancies`

Each card represents one `vacancy`.

Card fields:

- role title
- total matches
- active pipeline count
- completed interview count
- last updated

Detail screen: `Vacancy Pipeline`

Shows candidate cards for matches belonging to that vacancy.

Candidate card fields:

- candidate name
- location
- salary expectation
- match status
- interview state
- short candidate summary

Candidate detail screen: `Candidate for Vacancy`

Fields:

- candidate name
- location
- salary expectation
- work format
- candidate summary
- skills
- interview summary
- strengths
- risks
- recommendation
- final score

## 9.3 Admin dashboard

Admin uses the same building blocks but without ownership filtering.

MVP admin navigation:

- all vacancies
- vacancy detail
- match detail

## 9.4 Unknown dashboard

Single blocked-access screen.

No data is returned.

## 10. Navigation

Navigation is stack-based and uses Telegram BackButton API.

Supported paths:

- candidate: `Home -> Match detail`
- manager: `Home -> Vacancy -> Match detail`
- admin: `Home -> Vacancy -> Match detail`

The frontend must be implemented as a single-page app with in-app navigation state.

## 11. UX and Design

The WebApp must be:

- mobile-first
- single-column
- optimized for Telegram in-app browser
- touch-friendly
- fast to load

Visual direction for MVP:

- dark interface
- Helly branding
- black background
- white text
- violet accent
- vertically stacked cards
- clear status pills
- strong spacing and readable typography

The UI must avoid:

- desktop-style tables
- dense grids
- multi-column layouts
- hidden navigation patterns

## 12. Backend Architecture

The WebApp backend must live in the existing FastAPI API service.

Planned backend modules:

- `src/webapp/auth.py`
- `src/webapp/session.py`
- `src/webapp/service.py`
- `src/webapp/router.py`

The API app must:

- serve static WebApp assets
- expose read-only WebApp API endpoints
- reuse existing DB session dependency

## 13. Frontend Architecture

The MVP frontend must be implemented inside this repository and deployed with the existing FastAPI service.

To stay aligned with the current repo and avoid introducing a second deployment stack, the WebApp frontend will be:

- static SPA assets served by FastAPI
- plain HTML/CSS/JavaScript
- Telegram WebApp SDK integration in browser

This intentionally replaces the original `Next.js + Tailwind` assumption.

Reason:

- current repository has no Node/Next toolchain
- current production deploy is one FastAPI API service
- embedding the WebApp in the current service is the fastest low-risk path to production

## 14. API Surface

All endpoints are read-only unless noted.

### 14.1 Auth

- `POST /webapp/api/auth/telegram`
- `GET /webapp/api/session`

### 14.2 Candidate

- `GET /webapp/api/candidate/opportunities`
- `GET /webapp/api/candidate/opportunities/{match_id}`

### 14.3 Hiring manager

- `GET /webapp/api/hiring-manager/vacancies`
- `GET /webapp/api/hiring-manager/vacancies/{vacancy_id}`
- `GET /webapp/api/hiring-manager/vacancies/{vacancy_id}/matches`
- `GET /webapp/api/hiring-manager/matches/{match_id}`

### 14.4 Admin

- `GET /webapp/api/admin/vacancies`
- `GET /webapp/api/admin/vacancies/{vacancy_id}`
- `GET /webapp/api/admin/matches/{match_id}`

## 15. Access Control

Candidate:

- may access only matches linked to own `candidate_profile`

Hiring manager:

- may access only vacancies where `vacancies.manager_user_id = session.user_id`
- may access only matches attached to owned vacancies

Admin:

- may access everything

Unknown:

- receives no protected data

## 16. Performance

MVP targets:

- initial WebApp shell load under 2 seconds on mobile Telegram
- minimal first-request chain
- avoid chat-history-sized payloads
- return compact card-oriented JSON, not raw database dumps

## 17. Scope Limits

MVP excludes:

- editing
- approving / rejecting
- interview actions
- comments
- notes
- chat
- notifications center
- analytics
- search-heavy admin tooling

## 18. Deployment

The WebApp ships through the existing API deployment.

Production URL target:

- `https://gethellybot-production.up.railway.app/webapp`

BotFather setup after release:

- `setdomain` to production domain
- WebApp button URL to `/webapp`

## 19. Acceptance Criteria

The feature is complete when:

- Telegram WebApp auth works against production bot token
- candidate users can open own opportunity dashboard
- hiring managers can open own vacancy dashboard
- admin users configured in env can open global dashboard
- unknown users see blocked access screen
- the WebApp is served from the existing FastAPI deploy
- the UI works in Telegram mobile browser

