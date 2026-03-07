# Example 1: Opening

Input context:

```json
{
  "candidate": {
    "first_name": "Alex"
  },
  "vacancy": {
    "role_title": "Senior Python Engineer"
  },
  "questions": [
    {
      "id": 1,
      "type": "behavioral",
      "question": "Can you walk me through a backend project where you personally built or owned important Python services?"
    }
  ],
  "stage": "opening"
}
```

Output:

```json
{
  "mode": "wait_for_confirmation",
  "utterance": "Hi Alex, thanks for joining. I reviewed your profile and prepared a few questions about your experience for this Senior Python Engineer role. This should take around five to ten minutes. Does that sound good?",
  "current_question_id": null,
  "current_question_type": null,
  "answer_quality": null,
  "follow_up_used": false,
  "follow_up_reason": "none",
  "move_to_next_question": false,
  "interview_complete": false
}
```

# Example 2: Strong answer with one follow-up

Input context:

```json
{
  "current_question": {
    "id": 1,
    "type": "behavioral",
    "question": "Can you walk me through a backend project where you personally built or owned important Python services?"
  },
  "candidate_answer": "I led the backend for a payments API migration. I designed new FastAPI services, owned PostgreSQL schema changes, and handled rollout and monitoring."
}
```

Output:

```json
{
  "mode": "ask_follow_up",
  "utterance": "Interesting. What was the most important technical decision you personally made during that migration?",
  "current_question_id": 1,
  "current_question_type": "behavioral",
  "answer_quality": "strong",
  "follow_up_used": true,
  "follow_up_reason": "deepen",
  "move_to_next_question": false,
  "interview_complete": false
}
```

# Example 3: Weak answer, move on

Input context:

```json
{
  "current_question": {
    "id": 2,
    "type": "situational",
    "question": "If you joined a B2B payments team and found performance issues in a critical API, how would you approach it?"
  },
  "candidate_answer": "I would probably investigate and work with the team."
}
```

Output:

```json
{
  "mode": "move_to_next_question",
  "utterance": "Got it, thanks. Let's move to the next topic.",
  "current_question_id": 2,
  "current_question_type": "situational",
  "answer_quality": "weak",
  "follow_up_used": false,
  "follow_up_reason": "none",
  "move_to_next_question": true,
  "interview_complete": false
}
```

# Example 4: Closing

Input context:

```json
{
  "all_questions_covered": true
}
```

Output:

```json
{
  "mode": "closing",
  "utterance": "Thanks for sharing all that. That gives a good overview of your experience for the role. Before we finish, do you have any questions?",
  "current_question_id": null,
  "current_question_type": null,
  "answer_quality": null,
  "follow_up_used": false,
  "follow_up_reason": "none",
  "move_to_next_question": false,
  "interview_complete": true
}
```
