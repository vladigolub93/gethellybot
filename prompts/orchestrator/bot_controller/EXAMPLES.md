# Example

Input context:

```json
{
  "state": "CV_PENDING",
  "allowed_actions": ["send_cv_text", "send_cv_document", "send_cv_voice"],
  "latest_user_message": "hi, what do I do now?"
}
```

Output:

```json
{
  "intent": "clarification_request",
  "tone": "friendly",
  "should_answer_directly": true,
  "should_use_recovery": false,
  "response_text": "Please send your CV as text, a document, or a short voice description of your experience.",
  "reason_code": "current_step_guidance"
}
```
