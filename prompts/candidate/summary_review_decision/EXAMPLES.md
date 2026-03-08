Message: "Approve summary"
Expected: explicit approval, action `approve_summary`

Message: "How long will this take?"
Expected: help question, no correction action

Message: "The summary is wrong. I work mostly with Go, not Python."
Expected: correction request, action `request_summary_change`
