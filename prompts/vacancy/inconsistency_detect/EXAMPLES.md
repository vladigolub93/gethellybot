# Example

Input:

```json
{
  "jd_text": "We need a senior backend engineer. Core stack includes Java, Node, and Python equally. Full remote but daily office presence is required.",
  "vacancy_summary": {
    "role_title": "Senior Backend Engineer",
    "seniority_normalized": "senior"
  }
}
```

Output:

```json
{
  "findings": [
    {
      "severity": "medium",
      "category": "stack_conflict",
      "finding": "Multiple unrelated backend core stacks are presented as primary and should be clarified."
    },
    {
      "severity": "high",
      "category": "work_format_conflict",
      "finding": "The vacancy claims both full remote work and daily office presence."
    }
  ]
}
```
