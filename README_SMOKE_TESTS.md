# Smoke Test Matrix

## Candidate flow
1. `/start`, share contact.
2. Send resume as pasted text, ensure intake starts.
3. Forward resume PDF, ensure extraction and interview bootstrap.
4. During interview question, ask timing meta question, ensure no advance.
5. During interview question, ask clarify question, ensure no advance.
6. Answer by voice in RU, ensure transcription and normalization to English.
7. Complete mandatory fields, location, work mode, salary.
8. Trigger matching via text, `find roles`.
9. Show stored matches via `show matches`.
10. Apply flow and mutual approval, then contact exchange.
11. Request deletion, `delete my data`.

## Manager flow
1. `/start`, share contact.
2. Paste JD text, ensure intake starts.
3. Forward JD PDF, ensure extraction and interview bootstrap.
4. During manager interview, ask clarify, ensure no advance.
5. Complete mandatory fields, work format remote, countries, budget.
6. Trigger matching via text, `find candidates`.
7. Show stored matches via `show matches`.
8. Approve candidate after apply, then contact exchange.

## Edge cases
- Send duplicate Telegram update id, ensure webhook exits early with 200.
- Force router JSON parse failure, ensure safe fallback message is sent.
- Trigger per-user burst limit, ensure throttling reply is sent and state does not advance.
- In waiting states send short unrelated text 3 times, ensure clearer guidance with example.
- In interview send non-answer 5 times, ensure voice or skip guidance is sent.
