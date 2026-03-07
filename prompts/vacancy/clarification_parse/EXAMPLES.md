# Example

Input:

```text
Budget: $7000-$9000 per month. Countries: Poland and Germany. Remote.
Team size: 6. Project: B2B payments platform. Stack: Python, FastAPI, PostgreSQL.
```

Output:

```json
{
  "role_title": null,
  "seniority_normalized": null,
  "budget_min": 7000,
  "budget_max": 9000,
  "budget_currency": "USD",
  "budget_period": "month",
  "countries_allowed_json": ["PL", "DE"],
  "work_format": "remote",
  "team_size": 6,
  "project_description": "B2B payments platform.",
  "primary_tech_stack_json": ["python", "fastapi", "postgresql"]
}
```
