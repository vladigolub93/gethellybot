export interface CandidateTechnicalSummaryV1 {
  headline: string;
  technical_depth_summary: string;
  architecture_and_scale: string;
  domain_expertise: string;
  ownership_and_authority: string;
  strength_highlights: string[];
  risk_flags: string[];
  interview_confidence_level: "low" | "medium" | "high";
  overall_assessment: string;
}
