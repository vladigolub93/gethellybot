# Changelog

## v1

- adapted from external recruiter-style interview agent prompt into Helly-specific production format
- changed from demo interview to real vacancy-aware first-round interview
- added Telegram-first brevity and turn-taking rules
- encoded answer-quality logic: strong, mixed, weak
- encoded follow-up decision policy: deepen, clarify, verify, or move on
- enforced maximum one follow-up per topic
- defined a structured turn output contract for future runtime orchestration
