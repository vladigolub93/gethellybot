export interface JobDescriptionAnalysisV1 {
  is_technical_role: true;
  role_title_guess: string | null;
  product_context: {
    product_type: "b2b" | "b2c" | "internal" | "platform" | "unknown";
    company_stage: "early_startup" | "growth" | "enterprise" | "unknown";
    what_the_product_does: string | null;
    users_or_customers: string | null;
  };
  work_scope: {
    current_tasks: string[];
    current_challenges: string[];
    deliverables_or_outcomes: string[];
  };
  technology_signal_map: {
    likely_core: string[];
    likely_secondary: string[];
    likely_noise_or_unclear: string[];
  };
  architecture_and_scale: {
    architecture_style: "microservices" | "monolith" | "event_driven" | "mixed" | "unknown";
    distributed_systems: "yes" | "no" | "unknown";
    high_load: "yes" | "no" | "unknown";
    scale_clues: string[];
  };
  domain_inference: {
    primary_domain: string | null;
    domain_depth_required_guess: "none" | "helpful" | "important" | "critical" | "unknown";
    evidence: string | null;
  };
  ownership_expectation_guess: {
    decision_authority_required: "executor" | "contributor" | "owner" | "technical_lead" | "unknown";
    production_responsibility: "yes" | "no" | "unknown";
  };
  requirements: {
    non_negotiables_guess: string[];
    flexible_or_nice_to_have_guess: string[];
    constraints: string[];
  };
  risk_of_misalignment: string[];
  missing_critical_information: string[];
  interview_focus_recommendations: string[];
}

export interface JobDescriptionAnalysisNonTechnicalV1 {
  is_technical_role: false;
  reason: "Non technical role";
}

export type JobDescriptionAnalysisV1Result =
  | JobDescriptionAnalysisV1
  | JobDescriptionAnalysisNonTechnicalV1;

export interface ManagerInterviewPlanV1 {
  answer_instruction: string;
  questions: Array<{
    question_id: string;
    question_text: string;
    target_validation: string;
    based_on_field: string;
  }>;
}
