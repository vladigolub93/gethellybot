# Double Reply Sources and Fixes

This document tracks where duplicate replies could happen and how they were fixed.

## 1) Multiple sends in one update path (StateRouter)

Source:
- `/src/router/state.router.ts`, flows that sent 2+ messages in a single update:
  - `/start` restart flow
  - skip contact flow
  - contact saved flow
  - role selection by text flow
  - interview completion + follow-up
  - mandatory fields completion + actions message
  - document intake bootstrap chain

Fix:
- Added reply kind support (`primary`, `secondary`) and marked intentional second message as `secondary`.
- Compressed document bootstrap chain into one combined final message.
- Marked long-running status messages (`still processing`, `transcribing`) as `secondary`.
- Avoided extra follow-up send when moving directly to mandatory fields.

## 2) Callback role selection sending onboarding + next prompt

Source:
- `/src/router/callback.router.ts` role callbacks sent onboarding and prompt as two regular sends.

Fix:
- Added `kind` support to callback sender and marked second prompt as `secondary`.

## 3) Cross-user notifications blocked by per-update guard

Source:
- `/src/telegram/telegram.client.ts` reply guard originally applied to every outgoing message in the same update context.
- This could block valid notifications sent to other chats during decision callbacks.

Fix:
- Guard now applies only when `chatId` matches the update initiator user id.
- Cross-user notifications are not blocked by initiator reply limits.

## 4) Repeat loop on identical text

Source:
- Repeated same reply string could be sent within a short interval from router fallback branches.

Fix:
- Added state memory fields:
  - `lastBotMessageHash`, `lastBotMessageAt` (session memory)
- If same text is about to be sent within 60s, replace with state-aware fallback.
- Added structured warn log `repeat_loop_prevented`.

## 5) Dispatcher consistency

Source:
- Reply guard context had to be initialized exactly once per update after idempotency check.

Fix:
- `/src/router/dispatch/llm-gate.dispatcher.ts` now does:
  1. idempotency check
  2. `beginUpdateContext(updateId, telegramUserId)`
  3. route dispatch

## Resulting rule

- At most one `primary` reply per update.
- One optional `secondary` reply only when intentionally marked.
- Duplicate primary sends are blocked and logged as `reply_guard_blocked`.
