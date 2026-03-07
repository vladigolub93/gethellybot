export interface JobProfileV2 {
  role_title: string | null;
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
  technology_map: {
    core: Array<{
      technology: string;
      required_depth: "basic" | "working" | "strong" | "expert";
      mandatory: true;
    }>;
    secondary: Array<{
      technology: string;
      required_depth: "basic" | "working" | "strong" | "expert";
      mandatory: false;
    }>;
    discarded_or_noise: string[];
  };
  architecture_and_scale: {
    architecture_style: "microservices" | "monolith" | "event_driven" | "mixed" | "unknown";
    distributed_systems: "yes" | "no" | "unknown";
    high_load: "yes" | "no" | "unknown";
    scale_clues: string[];
  };
  domain_requirements: {
    primary_domain: string | null;
    domain_depth_required: "none" | "helpful" | "important" | "critical" | "unknown";
    regulatory_or_constraints: string | null;
  };
  ownership_expectation: {
    decision_authority_required: "executor" | "contributor" | "owner" | "technical_lead" | "unknown";
    production_responsibility: "yes" | "no" | "unknown";
  };
  non_negotiables: string[];
  flexible_requirements: string[];
  constraints: string[];
}

export interface JobProfileUpdateV2 {
  updated_job_profile: JobProfileV2;
  profile_updates: Array<{
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
  follow_up_required: boolean;
  follow_up_focus: string | null;
}

export interface JobTechnicalSummaryV2 {
  headline: string;
  product_context: string;
  current_tasks: string[];
  current_challenges: string[];
  core_tech: string[];
  key_requirements: string[];
  domain_need: "none" | "helpful" | "important" | "critical" | "unknown";
  ownership_expectation: "executor" | "contributor" | "owner" | "technical_lead" | "unknown";
  notes_for_matching: string;
}
