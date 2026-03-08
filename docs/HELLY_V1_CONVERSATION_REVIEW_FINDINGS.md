## Helly v1 Conversation Review Findings

Last updated: 2026-03-08

This document captures the highest-signal conversational issues found in real or live-like Telegram flows after the LangGraph stage-agent migration.

Sources reviewed:
- real candidate conversation: `telegram_user_id=768517770`
- live-like manager conversation: `telegram_user_id=990000004` with pending notifications included

### Top Findings

1. Candidate onboarding start still sounds form-like.
   Example:
   `Got it — let’s start your candidate profile. Please send your CV, or just describe your work experience here.`
   Fix area:
   runtime microcopy
   Status:
   fixed in current polish pass

2. CV_PENDING LinkedIn help can become too long and list-like.
   Example:
   `Да, можно 🙂 ... - вставить опыт работы текстом - отправить голосовое сообщение ...`
   Fix area:
   state-assistance prompt tuning
   Status:
   pending targeted prompt polish

3. Summary-review correction acknowledgement sounds transactional.
   Example:
   `Got it — updating your summary with your correction now.`
   Fix area:
   runtime microcopy
   Status:
   fixed in current polish pass

4. Final summary review phrasing sounds robotic.
   Example:
   `Here is your updated summary. This is the final version for approval.`
   Fix area:
   runtime microcopy / choreography
   Status:
   fixed in current polish pass

5. Candidate summary approved transition is still too administrative.
   Example:
   `Perfect. Next I need your salary expectations, location, and preferred format...`
   Fix area:
   runtime microcopy
   Status:
   fixed in current polish pass

6. Manager vacancy summary approved transition is still too checklist-like.
   Example:
   `Awesome! Please send the basics: budget, allowed countries, work format, team size, project context, and main stack.`
   Fix area:
   runtime microcopy
   Status:
   fixed in current polish pass

7. Some summary-review turns still over-index on "final version" language.
   This is functionally correct, but the wording sounds like a document workflow instead of a recruiter chat.
   Fix area:
   runtime microcopy / prompt tone
   Status:
   fixed in current polish pass

8. Candidate delete intent inside active candidate stages is still not gracefully handled.
   Example:
   during `QUESTIONS_PENDING`, delete requests were redirected back to filling fields instead of moving toward deletion confirmation.
   Fix area:
   stage-agent intent coverage + routing
   Status:
   pending product fix

9. Historical role-selection help showed repeated prompt-like replies.
   Example:
   repeated `Choose your role: Candidate or Hiring Manager.`
   Fix area:
   prompt dedupe / live verification
   Status:
   monitor in next live run

10. Some manager vacancy-review turns still sound like ATS UI copy rather than a sharp operator.
    Example:
    `Quick check. I turned the vacancy into a short summary below.`
    Fix area:
    prompt tone / runtime choreography
    Status:
    partially improved, validate in next live run

### Fix Mapping

- Prompt fixes:
  - CV_PENDING LinkedIn/help wording
  - manager vacancy summary review tone
  - anti-repeat / answer-the-last-concern behavior

- Runtime microcopy fixes:
  - candidate onboarding start
  - summary correction acknowledgement
  - final summary review messaging
  - candidate summary approved transition
  - vacancy summary approved transition

- Stage-agent / routing fixes:
  - delete intent during active candidate stages
  - possibly delete intent during active manager stages if live review shows the same issue

### Next Validation Pass

After current fixes land, re-check:
- real candidate onboarding turns
- real candidate summary review turns
- manager vacancy summary review turns
- delete intent during `QUESTIONS_PENDING`
