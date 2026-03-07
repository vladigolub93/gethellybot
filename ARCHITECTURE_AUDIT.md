# Architecture Audit, Boardy-like Conversational Gate

## Scope
- Inbound update entry points.
- Reply paths that can bypass LLM routing.
- Interview progression safety.
- Fallback loop risks.

## Current Entry Points
1. `/telegram/webhook` in `/Users/vladigolub/Desktop/telegrambot/src/telegram/webhook.controller.ts`.
2. Normalization in `/Users/vladigolub/Desktop/telegrambot/src/telegram/update-normalizer.ts`.
3. Main stateful flow in `/Users/vladigolub/Desktop/telegrambot/src/router/state.router.ts`.

## Bypass Map
1. `/Users/vladigolub/Desktop/telegrambot/src/router/state.router.ts`, `ensureInterviewContext`.
- State: interviewing states when context cannot be restored.
- Sample input: any message after restart with broken in-memory interview.
- Reply: "I could not restore your interview context. Please use /start and upload your file or text again."
- Why bypass: safety message sent before classifier.
- Planned fix: keep as deterministic safety guard, but run through LLM gate first and log as `handler_selected=context_recovery_guard`.

2. `/Users/vladigolub/Desktop/telegrambot/src/router/state.router.ts`, rate-limit branch.
- State: any.
- Sample input: burst over threshold.
- Reply: "Too many messages at once. Please wait a few seconds and try again."
- Why bypass: anti-spam deterministic response.
- Planned fix: keep deterministic, mark explicit in logs as `handler_selected=rate_limit_guard`.

3. `/Users/vladigolub/Desktop/telegrambot/src/router/state.router.ts`, classifier fail fallback.
- State: any.
- Sample input: router JSON parse error.
- Reply: state-safe fallback.
- Why bypass: LLM failure fallback.
- Planned fix: already protected by `callJsonPromptSafe`, keep deterministic fallback and avoid loops with state-aware rewrite.

4. `/Users/vladigolub/Desktop/telegrambot/src/router/message.router.ts`, many direct text replies.
- State: multiple.
- Sample input: legacy `MessageRouter.route` path.
- Reply: various canned responses.
- Why bypass: legacy router has local deterministic branches.
- Planned fix: demote this router as legacy, use `StateRouter` via LLM gate dispatcher as the single active path.

5. `/Users/vladigolub/Desktop/telegrambot/src/router/callback.router.ts`, callback replies.
- State: callback flows.
- Sample input: inline callback.
- Reply: deterministic acknowledgement.
- Why bypass: callback actions are deterministic, not conversational free text.
- Planned fix: keep deterministic execution, callbacks are action events, not natural language messages.

## Implemented Fixes In This Pass
1. Added unified inbound dispatcher:
- `/Users/vladigolub/Desktop/telegrambot/src/router/dispatch/llm-gate.dispatcher.ts`
- All webhook updates now go through `handleIncomingUpdate`.

2. Webhook refactor:
- `/Users/vladigolub/Desktop/telegrambot/src/telegram/webhook.controller.ts` now calls dispatcher only.

3. Duplicate and loop hardening:
- Document/voice duplicate ack removed.
- Extraction states (`extracting_resume`, `extracting_job`) added.
- State-aware anti-loop fallback added.

4. Reply source instrumentation:
- Added `sendUserMessage` wrapper in Telegram client with `source` logging.
- `StateRouter` reply path uses wrapper.

5. One-liner reliability:
- Added deterministic fallback one-liners if LLM one-liner prompt fails.

## Planned Next Tightening
1. Migrate remaining modules to `sendUserMessage` wrapper:
- `callback.router.ts`, `message.router.ts`, `notifications/*`, `decisions/contact-exchange.service.ts`.

2. Add `reply_sent` and `handler_selected` logging for every outbound send in all modules.

3. Remove or archive legacy `MessageRouter` once all active routes use `StateRouter` only.
