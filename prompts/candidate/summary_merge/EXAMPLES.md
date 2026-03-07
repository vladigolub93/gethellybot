# Example

Current summary:

```json
{
  "status": "draft",
  "headline": "Python engineer with 5 years of experience.",
  "experience_excerpt": "Built Python APIs and internal tools.",
  "years_experience": 5,
  "skills": ["python", "postgresql"],
  "approval_summary_text": "You are a Python Engineer with 5 years of experience building backend APIs and internal tools. You have hands-on experience with Python and PostgreSQL and have worked on backend systems that support internal operations. You have contributed to product and platform work where reliable API delivery was important."
}
```

Candidate correction:

```text
Edit summary: It is 6 years, and I also worked with FastAPI and Redis.
```

Output:

```json
{
  "status": "draft",
  "headline": "Python engineer with 6 years of backend experience.",
  "experience_excerpt": "Built Python APIs and internal backend tools, including work with FastAPI, PostgreSQL, and Redis.",
  "years_experience": 6,
  "skills": ["python", "fastapi", "postgresql", "redis"],
  "approval_summary_text": "You are a Python Backend Engineer with 6 years of experience building APIs and internal backend tools. You have strong hands-on experience with Python, FastAPI, PostgreSQL, and Redis. You have worked on internal systems and backend product functionality that support day-to-day business operations.",
  "candidate_edit_notes": "It is 6 years, and I also worked with FastAPI and Redis."
}
```
