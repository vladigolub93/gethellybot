Message: "Approve summary"
Expected: explicit approval, action `approve_summary`

Message: "Why do I need to approve this first?"
Expected: help question, no correction action

Message: "The role should be Senior Data Engineer, not Backend Engineer."
Expected: correction request, action `request_summary_change`
