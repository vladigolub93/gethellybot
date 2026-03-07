# Example

Input:

```json
{
  "vacancy": {
    "role_title": "Senior Python Engineer",
    "primary_tech_stack_json": ["python", "fastapi", "postgresql"]
  },
  "candidates": [
    {
      "candidate_ref": "cand_1",
      "deterministic_score": 0.81,
      "summary": {
        "skills": ["python", "fastapi", "postgresql", "aws"],
        "years_experience": 6
      }
    },
    {
      "candidate_ref": "cand_2",
      "deterministic_score": 0.79,
      "summary": {
        "skills": ["java", "spring"],
        "years_experience": 7
      }
    }
  ]
}
```

Output:

```json
{
  "ranked_candidates": [
    {
      "candidate_ref": "cand_1",
      "rank": 1,
      "fit_score": 0.9,
      "rationale": "Strong direct overlap with the vacancy stack and relevant seniority for the role."
    },
    {
      "candidate_ref": "cand_2",
      "rank": 2,
      "fit_score": 0.42,
      "rationale": "Shows senior backend experience but has weak direct overlap with the required stack."
    }
  ]
}
```
