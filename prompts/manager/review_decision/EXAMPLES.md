Input: "What happens if I approve this candidate?"
Output:
{
  "intent": "help",
  "response_text": "If you approve this candidate, Helly will prepare the handoff and introduction.",
  "proposed_action": null,
  "keep_current_state": true,
  "needs_follow_up": true,
  "reason_code": "manager_review_help_question"
}

Input: "Approve candidate"
Output:
{
  "intent": "approve_candidate",
  "response_text": "Understood. I will approve the candidate and prepare the handoff.",
  "proposed_action": "approve_candidate",
  "keep_current_state": true,
  "needs_follow_up": false,
  "reason_code": "manager_review_approve"
}
