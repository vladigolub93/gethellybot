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
  "response_mode": "answer",
  "keep_current_state": true,
  "proposed_action": null,
  "response_text": "Please send your CV as text, a document, or a short voice description of your experience.",
  "reason_code": "current_step_guidance"
}
```
