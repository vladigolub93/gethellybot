export interface CandidateResumeAnalysisV2 {
  is_technical: true;
  primary_direction:
    | "backend"
    | "frontend"
    | "fullstack"
    | "mobile"
    | "devops"
    | "qa"
    | "data"
    | "ml"
    | "security"
    | "infrastructure"
    | "embedded"
    | "mixed"
    | "unknown";
  seniority_estimate: "junior" | "middle" | "senior" | "lead" | "principal" | "unknown";
  total_experience_years_estimate: number | null;
  decision_authority_level: "executor" | "contributor" | "owner" | "tech_lead" | "unclear";
  hands_on_level: "high" | "medium" | "low" | "unclear";
  skill_depth_classification: {
    deep_experience: string[];
    working_experience: string[];
    mentioned_only: string[];
  };
  core_technologies: Array<{
    name: string;
    years_estimated: number | null;
    confidence: number;
    evidence: string;
  }>;
  secondary_technologies: Array<{
    name: string;
    confidence: number;
  }>;
  domain_expertise: Array<{
    domain:
      | "fintech"
      | "healthcare"
      | "ecommerce"
      | "gaming"
      | "cybersecurity"
      | "telecom"
      | "blockchain"
      | "ai"
      | "enterprise"
      | "edtech"
      | "logistics"
      | "adtech"
      | "embedded"
      | "other";
    years_estimated: number | null;
    depth_level: "low" | "medium" | "high";
    regulatory_or_business_complexity: "none" | "moderate" | "high" | "unknown";
    confidence: number;
    evidence: string;
  }>;
  system_complexity_level: "low" | "medium" | "high" | "unclear";
  scale_indicators: {
    users_scale: "unknown" | "small" | "medium" | "large";
    rps_scale: "unknown" | "low" | "medium" | "high";
    data_volume_scale: "unknown" | "gb" | "tb" | "pb";
  };
  architecture_signals: {
    microservices: boolean;
    monolith: boolean;
    event_driven: boolean;
    distributed_systems: boolean;
    cloud_native: boolean;
    high_load: boolean;
    not_clear: boolean;
  };
  cloud_and_infra: {
    cloud_platforms: string[];
    docker: boolean;
    kubernetes: boolean;
    ci_cd: boolean;
    iac: boolean;
    monitoring: boolean;
    networking_exposure: boolean;
  };
  data_exposure: {
    sql: boolean;
    nosql: boolean;
    data_pipelines: boolean;
    ml_models: boolean;
    analytics: boolean;
    real_time_processing: boolean;
  };
  ownership_signals: {
    architecture_design: boolean;
    led_projects: boolean;
    mentorship: boolean;
    production_responsibility: boolean;
    scalability_responsibility: boolean;
    incident_handling: boolean;
  };
  impact_indicators: string[];
  technical_risk_flags: string[];
  career_pattern: {
    job_hopping_risk: boolean;
    long_term_positions: boolean;
    frequent_short_contracts: boolean;
    career_growth_visible: boolean;
  };
  profile_information_density: "low" | "medium" | "high";
  missing_critical_information: string[];
  interview_focus_recommendations: string[];
}

export interface CandidateResumeAnalysisNonTechnical {
  is_technical: false;
  reason: "Non-technical profile";
}

export type CandidateResumeAnalysisV2Result =
  | CandidateResumeAnalysisV2
  | CandidateResumeAnalysisNonTechnical;
