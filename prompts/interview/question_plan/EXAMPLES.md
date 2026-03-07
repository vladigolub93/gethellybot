# Example

Input context:

```json
{
  "candidate": {
    "first_name": "Alex",
    "last_name": "M",
    "cv_text": "Senior Python engineer with 6 years of experience building backend services for B2B SaaS. Worked with FastAPI, PostgreSQL, Redis, Docker, AWS. Led API integrations and internal platform work."
  },
  "vacancy": {
    "role_title": "Senior Python Engineer",
    "primary_tech_stack_json": ["python", "fastapi", "postgresql"],
    "project_description": "B2B payments platform"
  }
}
```

Output:

```json
{
  "questions": [
    {
      "id": 1,
      "type": "behavioral",
      "question": "Can you walk me through a backend project where you personally built or owned important Python services, and explain what decisions were yours?"
    },
    {
      "id": 2,
      "type": "situational",
      "question": "If you joined a B2B payments team and discovered performance issues in a critical API, how would you approach diagnosing and fixing them?"
    },
    {
      "id": 3,
      "type": "role_specific",
      "question": "You mentioned FastAPI and PostgreSQL experience. Can you describe a system where you used them together in production and what you personally implemented?"
    },
    {
      "id": 4,
      "type": "motivation",
      "question": "What are you looking for in your next backend role, and why does this kind of product and team direction make sense for you now?"
    }
  ],
  "fallback_used": false
}
```
