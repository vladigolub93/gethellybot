import { LlmClient } from "../ai/llm.client";
import { buildCandidateInterviewPlanPrompt } from "../ai/prompts/candidate-interview.prompt";
import { CANDIDATE_INTERVIEW_PLAN_V2_PROMPT } from "../ai/prompts/candidate/interview-plan.v2.prompt";
import { JOB_DESCRIPTION_ANALYSIS_V1_PROMPT } from "../ai/prompts/manager/job-description-analysis.v1.prompt";
import { MANAGER_INTERVIEW_PLAN_V1_PROMPT } from "../ai/prompts/manager/manager-interview-plan.v1.prompt";
import { buildManagerInterviewPlanPrompt } from "../ai/prompts/manager-interview.prompt";
import { Logger } from "../config/logger";
import { JobsRepository } from "../db/repositories/jobs.repo";
import { ProfilesRepository } from "../db/repositories/profiles.repo";
import { QualityFlagsService } from "../qa/quality-flags.service";
import {
  CandidateResumeAnalysisV2,
  CandidateResumeAnalysisV2Result,
} from "../shared/types/candidate-analysis.types";
import { InterviewPlan } from "../shared/types/domain.types";
import {
  JobDescriptionAnalysisV1,
  JobDescriptionAnalysisV1Result,
  ManagerInterviewPlanV1,
} from "../shared/types/job-analysis.types";
import { UserRole } from "../shared/types/state.types";
import { CandidateInterviewPlanV2, CandidateInterviewQuestionV2 } from "../shared/types/interview-plan.types";
import { buildFallbackPlan, validateAndFreezeInterviewPlan } from "./interview-plan.guard";

interface BuildPlanOptions {
  telegramUserId?: number;
}

export class InterviewPlanService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
    private readonly profilesRepository: ProfilesRepository,
    private readonly jobsRepository: JobsRepository,
    private readonly qualityFlagsService?: QualityFlagsService,
  ) {}

  async buildPlan(role: UserRole, sourceText: string, options?: BuildPlanOptions): Promise<InterviewPlan> {
    if (role === "candidate" && options?.telegramUserId) {
      const analysis = await this.getCandidateResumeAnalysis(options.telegramUserId);
      if (analysis?.is_technical) {
        this.logger.debug("Candidate resume analysis is available for interview planning", {
          telegramUserId: options.telegramUserId,
          isTechnical: true,
        });
        const planV2 = await this.buildCandidateInterviewPlanV2(analysis, options);
        return this.mapCandidateInterviewPlanV2ToInterviewPlan(planV2);
      }
    }

    const prompt =
      role === "candidate"
        ? buildCandidateInterviewPlanPrompt(sourceText)
        : buildManagerInterviewPlanPrompt(sourceText);

    const firstAttempt = await this.tryGenerate(prompt);
    if (firstAttempt) {
      return validateAndFreezeInterviewPlan(role, firstAttempt);
    }
    this.logger.warn("Interview plan generation attempt 1 failed");

    const secondAttempt = await this.tryGenerate(prompt);
    if (secondAttempt) {
      return validateAndFreezeInterviewPlan(role, secondAttempt);
    }
    this.logger.warn("Interview plan generation attempt 2 failed, using fallback");

    return buildFallbackPlan(role);
  }

  async buildCandidateInterviewPlanV2(
    candidateResumeAnalysis: CandidateResumeAnalysisV2,
    options?: BuildPlanOptions,
  ): Promise<CandidateInterviewPlanV2> {
    const prompt = [
      CANDIDATE_INTERVIEW_PLAN_V2_PROMPT,
      "",
      JSON.stringify(candidateResumeAnalysis, null, 2),
    ].join("\n");

    const firstAttempt = await this.tryGenerateCandidatePlanV2(prompt);
    if (firstAttempt) {
      await this.persistCandidatePlanV2(options?.telegramUserId, firstAttempt);
      return firstAttempt;
    }
    if (options?.telegramUserId) {
      await this.qualityFlagsService?.raise({
        entityType: "candidate",
        entityId: String(options.telegramUserId),
        flag: "interview_plan_parse_failed",
        details: { step: "candidate_plan_v2_attempt_1" },
      });
    }
    this.logger.warn("Candidate interview plan v2 generation attempt 1 failed");

    const secondAttempt = await this.tryGenerateCandidatePlanV2(prompt);
    if (secondAttempt) {
      await this.persistCandidatePlanV2(options?.telegramUserId, secondAttempt);
      return secondAttempt;
    }
    if (options?.telegramUserId) {
      await this.qualityFlagsService?.raise({
        entityType: "candidate",
        entityId: String(options.telegramUserId),
        flag: "interview_plan_parse_failed",
        details: { step: "candidate_plan_v2_attempt_2" },
      });
    }
    this.logger.warn("Candidate interview plan v2 generation attempt 2 failed, using fallback");

    const fallback = buildFallbackCandidatePlanV2(candidateResumeAnalysis);
    await this.persistCandidatePlanV2(options?.telegramUserId, fallback);
    return fallback;
  }

  async buildJobDescriptionAnalysisV1(
    managerTelegramUserId: number,
    jobDescriptionText: string,
  ): Promise<JobDescriptionAnalysisV1Result> {
    const prompt = [JOB_DESCRIPTION_ANALYSIS_V1_PROMPT, "", jobDescriptionText].join("\n");
    const firstAttempt = await this.tryGenerateJobDescriptionAnalysisV1(prompt);
    if (firstAttempt) {
      if (firstAttempt.is_technical_role && firstAttempt.missing_critical_information.length >= 6) {
        await this.qualityFlagsService?.raise({
          entityType: "job",
          entityId: String(managerTelegramUserId),
          flag: "jd_analysis_high_ambiguity",
          details: {
            missingCriticalInfo: firstAttempt.missing_critical_information.length,
            risks: firstAttempt.risk_of_misalignment.length,
          },
        });
      }
      await this.jobsRepository.saveJobDescriptionAnalysis({
        managerTelegramUserId,
        jobSummary: jobDescriptionText,
        analysis: firstAttempt,
      });
      return firstAttempt;
    }
    this.logger.warn("Job description analysis v1 generation attempt 1 failed");

    const secondAttempt = await this.tryGenerateJobDescriptionAnalysisV1(prompt);
    if (secondAttempt) {
      if (secondAttempt.is_technical_role && secondAttempt.missing_critical_information.length >= 6) {
        await this.qualityFlagsService?.raise({
          entityType: "job",
          entityId: String(managerTelegramUserId),
          flag: "jd_analysis_high_ambiguity",
          details: {
            missingCriticalInfo: secondAttempt.missing_critical_information.length,
            risks: secondAttempt.risk_of_misalignment.length,
          },
        });
      }
      await this.jobsRepository.saveJobDescriptionAnalysis({
        managerTelegramUserId,
        jobSummary: jobDescriptionText,
        analysis: secondAttempt,
      });
      return secondAttempt;
    }
    this.logger.warn("Job description analysis v1 generation attempt 2 failed, using fallback");

    const fallback = buildFallbackJobDescriptionAnalysisV1();
    await this.jobsRepository.saveJobDescriptionAnalysis({
      managerTelegramUserId,
      jobSummary: jobDescriptionText,
      analysis: fallback,
    });
    return fallback;
  }

  async buildManagerInterviewPlanV1(
    jobAnalysis: JobDescriptionAnalysisV1,
    options?: BuildPlanOptions,
  ): Promise<ManagerInterviewPlanV1> {
    const prompt = [MANAGER_INTERVIEW_PLAN_V1_PROMPT, "", JSON.stringify(jobAnalysis, null, 2)].join(
      "\n",
    );
    const firstAttempt = await this.tryGenerateManagerInterviewPlanV1(prompt);
    if (firstAttempt) {
      await this.persistManagerInterviewPlanV1(options?.telegramUserId, firstAttempt);
      return firstAttempt;
    }
    if (options?.telegramUserId) {
      await this.qualityFlagsService?.raise({
        entityType: "job",
        entityId: String(options.telegramUserId),
        flag: "interview_plan_parse_failed",
        details: { step: "manager_plan_v1_attempt_1" },
      });
    }
    this.logger.warn("Manager interview plan v1 generation attempt 1 failed");

    const secondAttempt = await this.tryGenerateManagerInterviewPlanV1(prompt);
    if (secondAttempt) {
      await this.persistManagerInterviewPlanV1(options?.telegramUserId, secondAttempt);
      return secondAttempt;
    }
    if (options?.telegramUserId) {
      await this.qualityFlagsService?.raise({
        entityType: "job",
        entityId: String(options.telegramUserId),
        flag: "interview_plan_parse_failed",
        details: { step: "manager_plan_v1_attempt_2" },
      });
    }
    this.logger.warn("Manager interview plan v1 generation attempt 2 failed, using fallback");

    const fallback = buildFallbackManagerInterviewPlanV1(jobAnalysis);
    await this.persistManagerInterviewPlanV1(options?.telegramUserId, fallback);
    return fallback;
  }

  mapManagerInterviewPlanV1ToInterviewPlan(planV1: ManagerInterviewPlanV1): InterviewPlan {
    return validateAndFreezeInterviewPlan("manager", {
      summary: "Manager interview plan v1 generated.",
      questions: planV1.questions.map((question, index) => ({
        id: question.question_id || `M${index + 1}`,
        question: question.question_text,
        goal: question.target_validation,
        gapToClarify: question.based_on_field,
      })),
    });
  }

  mapCandidateInterviewPlanV2ToInterviewPlan(planV2: CandidateInterviewPlanV2): InterviewPlan {
    return validateAndFreezeInterviewPlan("candidate", {
      summary: planV2.interview_strategy.primary_uncertainty || "Candidate interview plan v2 generated.",
      questions: planV2.questions.map((question, index) => ({
        id: question.question_id || `Q${index + 1}`,
        question: question.question_text,
        goal: question.target_validation,
        gapToClarify: question.based_on_field,
      })),
    });
  }

  private async tryGenerate(prompt: string): Promise<InterviewPlan | null> {
    try {
      return await this.llmClient.generateInterviewPlan(prompt);
    } catch {
      return null;
    }
  }

  private async tryGenerateCandidatePlanV2(prompt: string): Promise<CandidateInterviewPlanV2 | null> {
    try {
      const raw = await this.llmClient.generateStructuredJson(prompt, 1800, {
        promptName: "candidate_interview_plan_v2",
      });
      return parseCandidateInterviewPlanV2(raw);
    } catch {
      return null;
    }
  }

  private async tryGenerateJobDescriptionAnalysisV1(
    prompt: string,
  ): Promise<JobDescriptionAnalysisV1Result | null> {
    try {
      const raw = await this.llmClient.generateStructuredJson(prompt, 2200, {
        promptName: "job_description_analysis_v1",
      });
      return parseJobDescriptionAnalysisV1(raw);
    } catch {
      return null;
    }
  }

  private async tryGenerateManagerInterviewPlanV1(prompt: string): Promise<ManagerInterviewPlanV1 | null> {
    try {
      const raw = await this.llmClient.generateStructuredJson(prompt, 1800, {
        promptName: "manager_interview_plan_v1",
      });
      return parseManagerInterviewPlanV1(raw);
    } catch {
      return null;
    }
  }

  private async persistCandidatePlanV2(
    telegramUserId: number | undefined,
    plan: CandidateInterviewPlanV2,
  ): Promise<void> {
    if (!telegramUserId) {
      return;
    }
    try {
      await this.profilesRepository.saveCandidateInterviewPlanV2({
        telegramUserId,
        plan,
      });
    } catch (error) {
      this.logger.warn("Failed to persist candidate interview plan v2", {
        telegramUserId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }

  private async persistManagerInterviewPlanV1(
    telegramUserId: number | undefined,
    plan: ManagerInterviewPlanV1,
  ): Promise<void> {
    if (!telegramUserId) {
      return;
    }
    try {
      await this.jobsRepository.saveManagerInterviewPlan({
        managerTelegramUserId: telegramUserId,
        plan,
      });
    } catch (error) {
      this.logger.warn("Failed to persist manager interview plan v1", {
        telegramUserId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }

  async getCandidateResumeAnalysis(
    telegramUserId: number,
  ): Promise<CandidateResumeAnalysisV2Result | null> {
    return this.profilesRepository.getCandidateResumeAnalysis(telegramUserId);
  }

  async getJobDescriptionAnalysis(
    managerTelegramUserId: number,
  ): Promise<JobDescriptionAnalysisV1Result | null> {
    return this.jobsRepository.getJobDescriptionAnalysis(managerTelegramUserId);
  }
}

function parseCandidateInterviewPlanV2(raw: string): CandidateInterviewPlanV2 {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Candidate interview plan v2 output is not valid JSON.");
  }

  const parsed = JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
  const strategy = normalizeStrategy(parsed.interview_strategy);
  const answerInstruction = normalizeAnswerInstruction(parsed.answer_instruction);
  const questions = normalizeQuestions(parsed.questions);

  if (questions.length === 0) {
    throw new Error("Candidate interview plan v2 output does not include valid questions.");
  }

  return {
    interview_strategy: strategy,
    answer_instruction: answerInstruction,
    questions,
  };
}

function parseJobDescriptionAnalysisV1(raw: string): JobDescriptionAnalysisV1Result {
  const parsed = parseJsonObject(raw);
  if (typeof parsed.is_technical_role !== "boolean") {
    throw new Error("Job description analysis v1 output is invalid: missing is_technical_role.");
  }
  if (!parsed.is_technical_role) {
    return {
      is_technical_role: false,
      reason: "Non technical role",
    };
  }

  return {
    is_technical_role: true,
    role_title_guess: toNullableText(parsed.role_title_guess),
    product_context: {
      product_type: normalizeEnum(parsed.product_context, "product_type", [
        "b2b",
        "b2c",
        "internal",
        "platform",
        "unknown",
      ]) as JobDescriptionAnalysisV1["product_context"]["product_type"],
      company_stage: normalizeEnum(parsed.product_context, "company_stage", [
        "early_startup",
        "growth",
        "enterprise",
        "unknown",
      ]) as JobDescriptionAnalysisV1["product_context"]["company_stage"],
      what_the_product_does: toNullableNestedText(parsed.product_context, "what_the_product_does"),
      users_or_customers: toNullableNestedText(parsed.product_context, "users_or_customers"),
    },
    work_scope: {
      current_tasks: toNestedStringArray(parsed.work_scope, "current_tasks"),
      current_challenges: toNestedStringArray(parsed.work_scope, "current_challenges"),
      deliverables_or_outcomes: toNestedStringArray(parsed.work_scope, "deliverables_or_outcomes"),
    },
    technology_signal_map: {
      likely_core: toNestedStringArray(parsed.technology_signal_map, "likely_core"),
      likely_secondary: toNestedStringArray(parsed.technology_signal_map, "likely_secondary"),
      likely_noise_or_unclear: toNestedStringArray(
        parsed.technology_signal_map,
        "likely_noise_or_unclear",
      ),
    },
    architecture_and_scale: {
      architecture_style: normalizeEnum(parsed.architecture_and_scale, "architecture_style", [
        "microservices",
        "monolith",
        "event_driven",
        "mixed",
        "unknown",
      ]) as JobDescriptionAnalysisV1["architecture_and_scale"]["architecture_style"],
      distributed_systems: normalizeEnum(parsed.architecture_and_scale, "distributed_systems", [
        "yes",
        "no",
        "unknown",
      ]) as JobDescriptionAnalysisV1["architecture_and_scale"]["distributed_systems"],
      high_load: normalizeEnum(parsed.architecture_and_scale, "high_load", [
        "yes",
        "no",
        "unknown",
      ]) as JobDescriptionAnalysisV1["architecture_and_scale"]["high_load"],
      scale_clues: toNestedStringArray(parsed.architecture_and_scale, "scale_clues"),
    },
    domain_inference: {
      primary_domain: toNullableNestedText(parsed.domain_inference, "primary_domain"),
      domain_depth_required_guess: normalizeEnum(
        parsed.domain_inference,
        "domain_depth_required_guess",
        ["none", "helpful", "important", "critical", "unknown"],
      ) as JobDescriptionAnalysisV1["domain_inference"]["domain_depth_required_guess"],
      evidence: toNullableNestedText(parsed.domain_inference, "evidence"),
    },
    ownership_expectation_guess: {
      decision_authority_required: normalizeEnum(
        parsed.ownership_expectation_guess,
        "decision_authority_required",
        ["executor", "contributor", "owner", "technical_lead", "unknown"],
      ) as JobDescriptionAnalysisV1["ownership_expectation_guess"]["decision_authority_required"],
      production_responsibility: normalizeEnum(
        parsed.ownership_expectation_guess,
        "production_responsibility",
        ["yes", "no", "unknown"],
      ) as JobDescriptionAnalysisV1["ownership_expectation_guess"]["production_responsibility"],
    },
    requirements: {
      non_negotiables_guess: toNestedStringArray(parsed.requirements, "non_negotiables_guess"),
      flexible_or_nice_to_have_guess: toNestedStringArray(
        parsed.requirements,
        "flexible_or_nice_to_have_guess",
      ),
      constraints: toNestedStringArray(parsed.requirements, "constraints"),
    },
    risk_of_misalignment: toStringArray(parsed.risk_of_misalignment),
    missing_critical_information: toStringArray(parsed.missing_critical_information),
    interview_focus_recommendations: toStringArray(parsed.interview_focus_recommendations),
  };
}

function parseManagerInterviewPlanV1(raw: string): ManagerInterviewPlanV1 {
  const parsed = parseJsonObject(raw);
  const answerInstruction = toText(parsed.answer_instruction);
  const questions = normalizeManagerPlanQuestions(parsed.questions);
  if (!answerInstruction || questions.length === 0) {
    throw new Error("Manager interview plan v1 output is invalid: missing required fields.");
  }
  return {
    answer_instruction: answerInstruction,
    questions,
  };
}

function normalizeStrategy(raw: unknown): CandidateInterviewPlanV2["interview_strategy"] {
  const source = isRecord(raw) ? raw : {};
  const riskPriorityLevel = toText(source.risk_priority_level).toLowerCase();
  return {
    primary_risk: toText(source.primary_risk),
    primary_uncertainty: toText(source.primary_uncertainty),
    risk_priority_level:
      riskPriorityLevel === "low" || riskPriorityLevel === "medium" || riskPriorityLevel === "high"
        ? riskPriorityLevel
        : "medium",
  };
}

function normalizeAnswerInstruction(raw: unknown): string {
  const instruction = toText(raw);
  if (instruction) {
    return instruction;
  }
  return "Please provide a detailed answer with concrete examples. You may respond in text or send a voice message if that is easier.";
}

function normalizeQuestions(raw: unknown): CandidateInterviewQuestionV2[] {
  if (!Array.isArray(raw)) {
    return [];
  }

  const normalized: CandidateInterviewQuestionV2[] = [];
  for (let index = 0; index < raw.length; index += 1) {
    const source = raw[index];
    if (!isRecord(source)) {
      continue;
    }
    const questionText = toText(source.question_text);
    if (!questionText) {
      continue;
    }
    const questionType = normalizeQuestionType(source.question_type);
    normalized.push({
      question_id: toText(source.question_id) || `Q${index + 1}`,
      question_text: questionText,
      question_type: questionType,
      target_validation: toText(source.target_validation),
      based_on_field: toText(source.based_on_field),
    });
  }
  return normalized.slice(0, 8);
}

function normalizeQuestionType(raw: unknown): CandidateInterviewQuestionV2["question_type"] {
  const value = toText(raw).toLowerCase();
  if (
    value === "depth_test" ||
    value === "authority_test" ||
    value === "domain_test" ||
    value === "architecture_test" ||
    value === "elimination_test"
  ) {
    return value;
  }
  return "depth_test";
}

function buildFallbackCandidatePlanV2(
  analysis: CandidateResumeAnalysisV2,
): CandidateInterviewPlanV2 {
  const firstCoreSkill = analysis.core_technologies[0]?.name || "your primary technology stack";
  const firstRisk = analysis.technical_risk_flags[0] || "unclear technical depth";
  const firstMissing = analysis.missing_critical_information[0] || "your most important technical ownership area";

  return {
    interview_strategy: {
      primary_risk: firstRisk,
      primary_uncertainty: firstMissing,
      risk_priority_level: "high",
    },
    answer_instruction:
      "Please provide a detailed answer with concrete examples. You may respond in text or send a voice message if that is easier.",
    questions: [
      {
        question_id: "Q1",
        question_text: `Please describe a recent project where you used ${firstCoreSkill}, including key technical decisions and outcomes.`,
        question_type: "depth_test",
        target_validation: "Validate depth of core technology usage",
        based_on_field: "core_technologies",
      },
      {
        question_id: "Q2",
        question_text:
          "Walk me through a difficult production issue you handled, how you diagnosed it, and what trade-offs you made.",
        question_type: "elimination_test",
        target_validation: "Validate practical production problem solving",
        based_on_field: "ownership_signals.production_responsibility",
      },
      {
        question_id: "Q3",
        question_text:
          "Describe a system architecture decision you owned, what alternatives you considered, and why you chose the final approach.",
        question_type: "architecture_test",
        target_validation: "Validate architecture ownership and reasoning",
        based_on_field: "architecture_signals",
      },
      {
        question_id: "Q4",
        question_text:
          "Tell me about the scale your system handled, including load patterns, bottlenecks, and how you improved reliability.",
        question_type: "architecture_test",
        target_validation: "Validate system complexity and scale claims",
        based_on_field: "scale_indicators",
      },
      {
        question_id: "Q5",
        question_text:
          "Which decisions did you make independently versus with team approval, and how did those decisions affect delivery?",
        question_type: "authority_test",
        target_validation: "Validate authority level and ownership boundaries",
        based_on_field: "decision_authority_level",
      },
      {
        question_id: "Q6",
        question_text: `Please clarify ${firstMissing} with a concrete example, specific constraints, and measurable impact.`,
        question_type: "domain_test",
        target_validation: "Clarify missing critical information",
        based_on_field: "missing_critical_information",
      },
    ],
  };
}

function buildFallbackJobDescriptionAnalysisV1(): JobDescriptionAnalysisV1 {
  return {
    is_technical_role: true,
    role_title_guess: null,
    product_context: {
      product_type: "unknown",
      company_stage: "unknown",
      what_the_product_does: null,
      users_or_customers: null,
    },
    work_scope: {
      current_tasks: [],
      current_challenges: [],
      deliverables_or_outcomes: [],
    },
    technology_signal_map: {
      likely_core: [],
      likely_secondary: [],
      likely_noise_or_unclear: [],
    },
    architecture_and_scale: {
      architecture_style: "unknown",
      distributed_systems: "unknown",
      high_load: "unknown",
      scale_clues: [],
    },
    domain_inference: {
      primary_domain: null,
      domain_depth_required_guess: "unknown",
      evidence: null,
    },
    ownership_expectation_guess: {
      decision_authority_required: "unknown",
      production_responsibility: "unknown",
    },
    requirements: {
      non_negotiables_guess: [],
      flexible_or_nice_to_have_guess: [],
      constraints: [],
    },
    risk_of_misalignment: ["Job description lacks clear technical signals."],
    missing_critical_information: [
      "Product context",
      "Real tasks in first months",
      "Core technologies with expected depth",
      "Ownership and production responsibility",
    ],
    interview_focus_recommendations: [
      "Clarify product and users",
      "Clarify real tasks and current challenges",
      "Separate must-have from nice-to-have technologies",
      "Clarify domain criticality and ownership expectations",
    ],
  };
}

function buildFallbackManagerInterviewPlanV1(
  analysis: JobDescriptionAnalysisV1,
): ManagerInterviewPlanV1 {
  const productFocus = analysis.product_context.what_the_product_does ?? "what the product does";
  const coreTech =
    analysis.technology_signal_map.likely_core[0] ??
    analysis.technology_signal_map.likely_secondary[0] ??
    "the core technology stack";
  const domain = analysis.domain_inference.primary_domain ?? "your domain context";

  return {
    answer_instruction:
      "Please provide detailed answers with concrete examples. You may respond in text or by sending a voice message.",
    questions: [
      {
        question_id: "M1",
        question_text: `Please describe ${productFocus}, who the users are, and what outcome this role must deliver in the next 3 months.`,
        target_validation: "Clarify product context and near-term outcomes",
        based_on_field: "product_context",
      },
      {
        question_id: "M2",
        question_text:
          "What are the most important day-to-day tasks for this role, and which current challenges should this person solve first?",
        target_validation: "Clarify real work scope and immediate challenges",
        based_on_field: "work_scope",
      },
      {
        question_id: "M3",
        question_text:
          "Can you share one recent technical problem your team faced and what a successful hire would do differently?",
        target_validation: "Clarify challenge ownership and practical expectations",
        based_on_field: "work_scope.current_challenges",
      },
      {
        question_id: "M4",
        question_text: `Which parts of ${coreTech} are truly required from day one, and what depth do you expect in those areas?`,
        target_validation: "Separate core technologies from optional stack items",
        based_on_field: "technology_signal_map",
      },
      {
        question_id: "M5",
        question_text: `How critical is experience in ${domain}, and where can strong engineering ability compensate for domain gaps?`,
        target_validation: "Clarify domain criticality and flexibility",
        based_on_field: "domain_inference",
      },
      {
        question_id: "M6",
        question_text:
          "What technical decisions should this role make independently, and which decisions require broader team alignment?",
        target_validation: "Clarify expected ownership and authority",
        based_on_field: "ownership_expectation_guess",
      },
    ],
  };
}

function normalizeManagerPlanQuestions(
  raw: unknown,
): ManagerInterviewPlanV1["questions"] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .filter((item): item is Record<string, unknown> => isRecord(item))
    .map((item, index) => ({
      question_id: toText(item.question_id) || `M${index + 1}`,
      question_text: toText(item.question_text),
      target_validation: toText(item.target_validation),
      based_on_field: toText(item.based_on_field),
    }))
    .filter((item) => Boolean(item.question_text))
    .slice(0, 9);
}

function parseJsonObject(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("LLM output does not include JSON object");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}

function normalizeEnum(
  container: unknown,
  key: string,
  allowed: string[],
): string {
  const value = toNestedText(container, key).toLowerCase();
  if (allowed.includes(value)) {
    return value;
  }
  return "unknown";
}

function toNullableText(value: unknown): string | null {
  const text = toText(value);
  return text || null;
}

function toNestedText(container: unknown, key: string): string {
  if (!isRecord(container)) {
    return "";
  }
  return toText(container[key]);
}

function toNullableNestedText(container: unknown, key: string): string | null {
  const text = toNestedText(container, key);
  return text || null;
}

function toNestedStringArray(container: unknown, key: string): string[] {
  if (!isRecord(container)) {
    return [];
  }
  return toStringArray(container[key]);
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => toText(item))
    .filter((item) => Boolean(item))
    .slice(0, 20);
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
