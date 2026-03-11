# Helly Telegram WebApp MVP Task List

## Phase 1. Spec Alignment

1. Replace the generic WebApp SRS with a Helly-specific SRS.
2. Map “applications” to `matches`.
3. Remove assumptions that do not exist in the current schema, especially `company_name`.
4. Replace `Next.js + Tailwind` requirement with a WebApp implementation that fits the current FastAPI repo.

## Phase 2. Backend Foundation

5. Add Telegram WebApp auth request/response models.
6. Add Telegram initData verification service.
7. Add short-lived signed WebApp session token support.
8. Add env-configured admin Telegram user ids.
9. Add role resolution logic based on current Helly data.
10. Add authenticated WebApp dependency for protected endpoints.

## Phase 3. Read-Only Query Layer

11. Add candidate dashboard query service over `matches`, `vacancies`, `interview_sessions`, and `evaluation_results`.
12. Add hiring manager dashboard query service over owned `vacancies` and vacancy `matches`.
13. Add admin dashboard query service without ownership filters.
14. Add presentation helpers for salary, budget, statuses, and timestamps.
15. Add explicit access-control guards for candidate, manager, admin, and unknown.

## Phase 4. WebApp API

16. Add `/webapp/api/auth/telegram`.
17. Add `/webapp/api/session`.
18. Add candidate opportunity list/detail endpoints.
19. Add hiring manager vacancy list/detail and match detail endpoints.
20. Add admin vacancy list/detail and match detail endpoints.

## Phase 5. Frontend Shell

21. Add static WebApp shell served by FastAPI.
22. Add Telegram WebApp SDK bootstrap.
23. Add auth bootstrap flow from `initData`.
24. Add SPA navigation with Telegram BackButton integration.
25. Add mobile-first dark UI with card-based layout.

## Phase 6. Role Screens

26. Add unknown access-blocked screen.
27. Add candidate home and match detail screens.
28. Add hiring manager vacancy list, vacancy pipeline, and match detail screens.
29. Add admin vacancy list and match detail screens.
30. Add empty-state and error-state screens.

## Phase 7. Validation

31. Add unit tests for Telegram WebApp auth verification.
32. Add unit tests for session token issue/verify.
33. Add API tests for role-based access control.
34. Add UI smoke test coverage where practical.
35. Validate local static asset serving and API integration.

## Delivery Order

Current implementation order:

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6
7. Phase 7

## Definition of Done

The WebApp MVP is done when:

- the app opens inside Telegram
- auth works from real Telegram initData
- the correct role dashboard loads
- all screens are read-only
- data comes from existing Helly tables
- the feature is deployable through the current FastAPI service

