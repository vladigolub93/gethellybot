# Example

Current summary:

```json
{
  "status": "draft",
  "headline": "Python engineer with 5 years of experience.",
  "experience_excerpt": "Built Python APIs and internal tools.",
  "years_experience": 5,
  "skills": ["python", "postgresql"]
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
  "candidate_edit_notes": "It is 6 years, and I also worked with FastAPI and Redis."
}
```
