export interface InterviewAnswerEvaluation {
  should_accept: boolean;
  should_request_reanswer: boolean;
  ai_assisted_likelihood: "low" | "medium" | "high";
  ai_assisted_confidence: number;
  signals: string[];
  missing_elements: string[];
  message_to_user: string;
}
