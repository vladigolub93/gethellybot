# HELLY v1 Synthetic Phase L Results

Version: 1.0  
Date: 2026-03-08

## Purpose

This document records the reproducible synthetic live-runtime checks for the remaining Phase L scenarios.

These checks do not use the public Telegram webhook. They replay synthetic Telegram updates directly through the live Helly runtime against live Supabase data and verify:

- stage-agent ownership stays intact
- help questions do not trigger incorrect side effects
- summary review stages do not misclassify help as edits
- manager vacancy summary flow survives help, correction, and approval

## Validation Mode

- runtime path: live application code
- persistence: live Supabase
- graph signal: local `graph_stage_executed` log emitted during replay
- database safety mode: `DB_USE_NULL_POOL=1`

This is a strong runtime validation layer, but it is still distinct from manual Telegram UI proof.

## Scenario Results

### 1. Candidate `SUMMARY_REVIEW` help question

Synthetic tester:
- `telegram_user_id`: `991100101`

Observed result:
- candidate reached `SUMMARY_REVIEW`
- latest inbound text: `How long will this take?`
- latest notification: `state_aware_help`
- latest transition remained `CV_PROCESSING -> SUMMARY_REVIEW`
- candidate version source type did not become `summary_user_edit`

Conclusion:
- help question stayed inside the stage
- no accidental correction flow was triggered

### 2. Candidate `QUESTIONS_PENDING` clarification question

Synthetic tester:
- `telegram_user_id`: `991100102`

Observed result during synthetic replay:
- candidate reached `QUESTIONS_PENDING`
- latest inbound text: `Gross or net?`
- latest notification: `state_aware_help`
- latest transition remained `SUMMARY_REVIEW -> QUESTIONS_PENDING`

Conclusion:
- clarification question stayed inside the stage
- it was not misclassified as structured salary/location/work-format input

Note:
- later attempts to recycle the same tester hit reset-tool deadlock noise in the shared validation environment
- the product scenario itself was already observed as passing before that tooling collision

### 3. Manager `VACANCY_SUMMARY_REVIEW` help, correction, approve

Synthetic tester:
- `telegram_user_id`: `991100103`

Observed result:
- manager reached `VACANCY_SUMMARY_REVIEW`
- help question `How long will this take?` produced an in-stage help reply
- explicit correction produced a `summary_user_edit` version
- approval moved vacancy to `CLARIFICATION_QA`
- latest notification after approval: `vacancy_summary_approved`

Conclusion:
- help, correction, and approval all worked through the stage-owned flow

## Follow-Up

Remaining desirable validation:
- manual Telegram UI proof for the same three scenarios
- Railway-hosted `graph_stage_executed` verification once local Railway credentials are available

## Overall Assessment

Synthetic Phase L validation is strong enough to say:

- the remaining high-risk stage-ownership scenarios are reproducible through live runtime
- the key misclassification bug class is materially reduced
- the main remaining gap is manual Telegram UI proof, not core runtime architecture
