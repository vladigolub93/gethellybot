# Example

Input:

```json
{
  "question": "Can you describe a backend service you built?",
  "candidate_answer": "I built a FastAPI service for payment reconciliation, owned PostgreSQL schema changes, and handled deployment."
}
```

Output:

```json
{
  "answer_summary": "Candidate described building a FastAPI payment reconciliation service and owning database changes and deployment.",
  "technologies": ["fastapi", "postgresql"],
  "systems_or_projects": ["payment reconciliation service"],
  "ownership_level": "strong",
  "is_concrete": true,
  "possible_profile_conflict": false
}
```
