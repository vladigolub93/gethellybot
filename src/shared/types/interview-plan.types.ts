import { CandidateResumeAnalysisV2 } from "./candidate-analysis.types";

export interface CandidateInterviewQuestionV2 {
  question_id: string;
  question_text: string;
  question_type:
    | "depth_test"
    | "authority_test"
    | "domain_test"
    | "architecture_test"
    | "elimination_test";
  target_validation: string;
  based_on_field: string;
}

export interface CandidateInterviewPlanV2 {
  interview_strategy: {
    primary_risk: string;
    primary_uncertainty: string;
    risk_priority_level: "low" | "medium" | "high";
  };
  answer_instruction: string;
  questions: CandidateInterviewQuestionV2[];
}

export interface CandidateProfileUpdateV2 {
  updated_resume_analysis: CandidateResumeAnalysisV2;
  confidence_updates: Array<{
    field: string;
    previous_value: string;
    new_value: string;
    reason: string;
  }>;
  contradiction_flags: string[];
  answer_quality: "low" | "medium" | "high";
  authenticity_score: number;
  authenticity_label: "likely_human" | "uncertain" | "likely_ai_assisted";
  authenticity_signals: string[];
  depth_change_detected: boolean;
  follow_up_required: boolean;
  follow_up_focus: string | null;
}
