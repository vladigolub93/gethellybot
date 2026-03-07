# Example

Input:

```text
We are hiring a Senior Python Engineer to build backend services for a B2B payments platform.
Stack: Python, FastAPI, PostgreSQL, Redis, AWS.
The team is product-focused and works remotely across Europe.
```

Output:

```json
{
  "status": "draft",
  "source_type": "pasted_text",
  "role_title": "Senior Python Engineer",
  "seniority_normalized": "senior",
  "primary_tech_stack": ["python", "fastapi", "postgresql", "redis", "aws"],
  "project_description_excerpt": "Build backend services for a remote B2B payments platform with a product-focused team across Europe.",
  "inconsistency_issues": []
}
```
