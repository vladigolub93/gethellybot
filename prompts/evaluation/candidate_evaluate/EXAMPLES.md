# Example

Input context:

```json
{
  "candidate_summary": {
    "years_experience": 6,
    "skills": ["python", "fastapi", "postgresql"]
  },
  "vacancy": {
    "role_title": "Senior Python Engineer",
    "primary_tech_stack_json": ["python", "fastapi", "postgresql"],
    "project_description": "B2B payments platform"
  },
  "answer_texts": [
    "I built payment APIs with Python and FastAPI.",
    "I handled schema design and performance tuning in PostgreSQL.",
    "I led incident response for a production outage."
  ]
}
```

Output:

```json
{
  "final_score": 0.84,
  "strengths": [
    "Strong overlap with the core Python, FastAPI, and PostgreSQL stack.",
    "Interview answers show production ownership and incident handling experience."
  ],
  "risks": [
    "Interview coverage on team leadership and stakeholder communication is still limited."
  ],
  "recommendation": "advance",
  "interview_summary": "The candidate comes across as a backend engineer with clear hands-on experience in Python APIs and production PostgreSQL work. During the interview they described building payment-facing services, handling schema design, and participating in incident response, and their explanations generally sounded specific enough to suggest real implementation ownership.\n\nThe answers were mostly concrete and aligned well with the vacancy stack, although some broader leadership context remained lightly covered. Overall the interview suggests credible relevance for the role, with solid technical fit and enough operational depth to justify moving the candidate forward."
}
```
