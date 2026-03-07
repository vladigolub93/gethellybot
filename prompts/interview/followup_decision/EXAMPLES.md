# Example

Input:

```json
{
  "question": "Can you walk me through a project where you used FastAPI in production?",
  "candidate_answer": "I built a FastAPI service for payments and owned the rollout.",
  "follow_up_already_used": false
}
```

Output:

```json
{
  "answer_quality": "strong",
  "ask_followup": true,
  "followup_reason": "deepen",
  "followup_question": "What was the most important technical decision you personally made in that rollout?"
}
```
