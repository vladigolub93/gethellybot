import "dotenv/config";
import { EmbeddingsClient } from "../src/ai/embeddings.client";
import { createLogger } from "../src/config/logger";
import { ProfilesRepository } from "../src/db/repositories/profiles.repo";
import { SupabaseRestClient } from "../src/db/supabase.client";
import { JobProfileV2, JobTechnicalSummaryV2 } from "../src/shared/types/job-profile.types";
import { QdrantBackfillService } from "../src/matching/qdrant-backfill.service";
import { QdrantClient } from "../src/matching/qdrant.client";

interface SeedJob {
  managerTelegramUserId: number;
  title: string;
  domain: string;
  productContext: string;
  candidateSummary: string;
  workFormat: "remote" | "hybrid";
  remoteCountries: string[];
  remoteWorldwide: boolean;
  budgetMin: number;
  budgetMax: number;
  budgetCurrency: "USD" | "EUR" | "ILS" | "GBP" | "other";
  budgetPeriod: "month";
  mustHaveSkills: [string, string, string, string, string];
  niceToHaveSkills: string[];
  coreTech: [string, string, string, string, string];
  secondaryTech: string[];
}

interface SeededRow {
  id: number;
  manager_telegram_user_id: number;
  status: string;
  job_summary: string;
  job_profile_complete: boolean;
}

const SYSTEM_CREATED_BY_USER_ID = 0;
const JOBS_TABLE = "jobs";

const JOBS: SeedJob[] = [
  {
    managerTelegramUserId: 990001001,
    title: "Junior React Developer",
    domain: "SaaS",
    productContext:
      "You will join a SaaS web app for small teams that manage client projects. The product is in growth stage and ships weekly. The frontend team works closely with backend engineers on customer facing flows.",
    candidateSummary:
      "You will build and improve React screens in a SaaS product used by real customers every day. The role focuses on forms, dashboards, and clean UI state handling. You will work with a senior mentor and ship features to production in short iterations. This is a good fit for a junior engineer who wants practical product experience.",
    workFormat: "remote",
    remoteCountries: ["Ukraine", "Poland", "Romania"],
    remoteWorldwide: false,
    budgetMin: 1200,
    budgetMax: 1800,
    budgetCurrency: "USD",
    budgetPeriod: "month",
    mustHaveSkills: ["React", "TypeScript", "JavaScript", "HTML", "CSS"],
    niceToHaveSkills: ["Redux Toolkit", "Jest", "Storybook"],
    coreTech: ["React", "TypeScript", "REST APIs", "Git", "CSS"],
    secondaryTech: ["Redux Toolkit", "Jest", "CI/CD"],
  },
  {
    managerTelegramUserId: 990001002,
    title: "Junior React Developer",
    domain: "fintech",
    productContext:
      "You will work on a B2B dashboard for finance operations teams. The product aggregates transactions, balances, and alerts from partner systems. The team is building internal tooling that must stay reliable and clear.",
    candidateSummary:
      "This role is for a junior React developer in a fintech B2B dashboard team. You will build table heavy interfaces, filters, and data visualization blocks. The codebase is TypeScript first, with code reviews and clear standards. You should be comfortable learning domain rules and translating them into UI behavior.",
    workFormat: "hybrid",
    remoteCountries: [],
    remoteWorldwide: false,
    budgetMin: 1400,
    budgetMax: 2200,
    budgetCurrency: "USD",
    budgetPeriod: "month",
    mustHaveSkills: ["React", "TypeScript", "JavaScript", "REST APIs", "Git"],
    niceToHaveSkills: ["TanStack Query", "Chart.js", "Figma"],
    coreTech: ["React", "TypeScript", "REST APIs", "Git", "Testing Library"],
    secondaryTech: ["TanStack Query", "Chart.js", "Cypress"],
  },
  {
    managerTelegramUserId: 990001003,
    title: "Junior Node.js Developer",
    domain: "e-commerce",
    productContext:
      "You will work on API and partner integration services for an e-commerce platform. The team maintains order, catalog, and payment related integrations. The stack is Node.js and PostgreSQL with clear release processes.",
    candidateSummary:
      "You will build backend APIs and external integrations in an e-commerce environment. The role includes endpoint implementation, payload validation, and integration debugging. You will pair with mid and senior backend engineers and learn production delivery practices. Good communication and clean code habits matter.",
    workFormat: "remote",
    remoteCountries: ["Ukraine", "Poland", "Bulgaria"],
    remoteWorldwide: false,
    budgetMin: 1500,
    budgetMax: 2300,
    budgetCurrency: "USD",
    budgetPeriod: "month",
    mustHaveSkills: ["Node.js", "TypeScript", "Express", "PostgreSQL", "REST APIs"],
    niceToHaveSkills: ["Docker", "Redis", "Stripe API"],
    coreTech: ["Node.js", "TypeScript", "Express", "PostgreSQL", "REST APIs"],
    secondaryTech: ["Docker", "Redis", "Message queues"],
  },
  {
    managerTelegramUserId: 990001004,
    title: "Junior Node.js Developer",
    domain: "healthcare",
    productContext:
      "You will support background jobs and queue based processing in a healthcare workflow platform. The team handles scheduled tasks, notifications, and data sync jobs. Reliability and clear observability are key for this product.",
    candidateSummary:
      "This backend role focuses on background jobs and queue processing in a healthcare domain product. You will implement workers, retries, and failure handling patterns under guidance. The stack includes Node.js, PostgreSQL, and queue tooling. If you enjoy systems behavior and production debugging, this role is a strong junior path.",
    workFormat: "remote",
    remoteCountries: ["Ukraine", "Poland", "Czech Republic"],
    remoteWorldwide: false,
    budgetMin: 1600,
    budgetMax: 2400,
    budgetCurrency: "USD",
    budgetPeriod: "month",
    mustHaveSkills: ["Node.js", "TypeScript", "PostgreSQL", "Git", "Testing"],
    niceToHaveSkills: ["BullMQ", "Docker", "Prometheus"],
    coreTech: ["Node.js", "TypeScript", "PostgreSQL", "Queues", "Git"],
    secondaryTech: ["BullMQ", "Docker", "Prometheus"],
  },
  {
    managerTelegramUserId: 990001005,
    title: "Junior QA Automation (JavaScript)",
    domain: "SaaS marketplace",
    productContext:
      "You will join a QA automation team for a SaaS marketplace web platform. The product has high release frequency and multiple user roles. The team is expanding automated coverage for UI and API flows.",
    candidateSummary:
      "You will create and maintain JavaScript based automated tests for web UI and API endpoints. The role includes regression suite ownership, flaky test cleanup, and bug reproduction support. You will work inside a cross functional squad and improve release confidence. This role fits a junior QA who already writes code and wants growth in automation.",
    workFormat: "hybrid",
    remoteCountries: [],
    remoteWorldwide: false,
    budgetMin: 1300,
    budgetMax: 2000,
    budgetCurrency: "USD",
    budgetPeriod: "month",
    mustHaveSkills: ["JavaScript", "Playwright", "API testing", "Git", "Test case design"],
    niceToHaveSkills: ["TypeScript", "CI pipelines", "Postman"],
    coreTech: ["JavaScript", "Playwright", "API testing", "Git", "Test strategy"],
    secondaryTech: ["TypeScript", "CI/CD", "SQL"],
  },
];

async function main(): Promise<void> {
  const supabaseUrl = mustEnv("SUPABASE_URL");
  const supabaseServiceRoleKey = mustEnv("SUPABASE_SERVICE_ROLE_KEY");
  const logger = createLogger();

  const supabase = new SupabaseRestClient({
    url: supabaseUrl,
    serviceRoleKey: supabaseServiceRoleKey,
  });

  for (const job of JOBS) {
    const jobProfile = buildJobProfile(job);
    const technicalSummary = buildTechnicalSummary(job);
    const row = {
      manager_telegram_user_id: job.managerTelegramUserId,
      created_by_user_id: SYSTEM_CREATED_BY_USER_ID,
      status: "active",
      job_summary: job.candidateSummary,
      job_profile: {
        title: job.title,
        domain: job.domain,
        mustHaveSkills: job.mustHaveSkills,
        niceToHaveSkills: job.niceToHaveSkills,
      },
      source_type: "text",
      source_text_original: `${job.productContext}\n\n${job.candidateSummary}`,
      source_text_english: `${job.productContext}\n\n${job.candidateSummary}`,
      telegram_file_id: null,
      job_analysis_json: null,
      manager_interview_plan_json: null,
      job_profile_json: jobProfile,
      technical_summary_json: technicalSummary,
      job_work_format: job.workFormat,
      job_remote_countries: job.workFormat === "remote" ? job.remoteCountries : [],
      job_remote_worldwide: job.workFormat === "remote" ? job.remoteWorldwide : false,
      job_budget_min: job.budgetMin,
      job_budget_max: job.budgetMax,
      job_budget_currency: job.budgetCurrency,
      job_budget_period: job.budgetPeriod,
      job_profile_complete: true,
      updated_at: new Date().toISOString(),
    };

    await supabase.upsert(JOBS_TABLE, row, { onConflict: "manager_telegram_user_id" });
  }

  const verification: SeededRow[] = [];
  for (const job of JOBS) {
    const row = await supabase.selectOne<SeededRow>(
      JOBS_TABLE,
      { manager_telegram_user_id: job.managerTelegramUserId },
      "id,manager_telegram_user_id,status,job_summary,job_profile_complete",
    );
    if (!row) {
      throw new Error(`Seed verification failed for manager_telegram_user_id=${job.managerTelegramUserId}`);
    }
    verification.push(row);
  }

  logger.info("seed.test_jobs.completed", {
    jobsSeeded: verification.length,
    managerTelegramUserIds: verification.map((item) => item.manager_telegram_user_id),
  });

  for (const row of verification) {
    // eslint-disable-next-line no-console
    console.log(
      `[seeded] id=${row.id} manager_telegram_user_id=${row.manager_telegram_user_id} status=${row.status} complete=${row.job_profile_complete}`,
    );
  }

  await maybeBackfillQdrant(logger, supabase);
}

function buildJobProfile(job: SeedJob): JobProfileV2 {
  return {
    role_title: job.title,
    product_context: {
      product_type: job.domain.toLowerCase().includes("fintech") ? "b2b" : "platform",
      company_stage: "growth",
      what_the_product_does: job.productContext,
      users_or_customers: "Product and operations teams",
    },
    work_scope: {
      current_tasks: [
        "Ship production features each sprint",
        "Fix bugs and improve reliability",
        "Collaborate in code reviews",
      ],
      current_challenges: [
        "Keep quality high with frequent releases",
        "Maintain predictable delivery timelines",
      ],
      deliverables_or_outcomes: [
        "Stable feature releases",
        "Clear ownership of tickets",
      ],
    },
    technology_map: {
      core: job.coreTech.map((technology) => ({
        technology,
        required_depth: "working",
        mandatory: true as const,
      })),
      secondary: job.secondaryTech.map((technology) => ({
        technology,
        required_depth: "basic",
        mandatory: false as const,
      })),
      discarded_or_noise: [],
    },
    architecture_and_scale: {
      architecture_style: "mixed",
      distributed_systems: "yes",
      high_load: "no",
      scale_clues: ["Growing production traffic", "Weekly releases"],
    },
    domain_requirements: {
      primary_domain: job.domain,
      domain_depth_required: "helpful",
      regulatory_or_constraints:
        job.domain.toLowerCase().includes("healthcare") ? "Data handling discipline required" : null,
    },
    ownership_expectation: {
      decision_authority_required: "contributor",
      production_responsibility: "yes",
    },
    non_negotiables: [...job.mustHaveSkills],
    flexible_requirements: [...job.niceToHaveSkills],
    constraints: [
      job.workFormat === "remote"
        ? `Remote countries: ${job.remoteWorldwide ? "worldwide" : job.remoteCountries.join(", ")}`
        : "Hybrid presence expected",
      `Budget ${job.budgetMin}-${job.budgetMax} ${job.budgetCurrency} per ${job.budgetPeriod}`,
    ],
  };
}

function buildTechnicalSummary(job: SeedJob): JobTechnicalSummaryV2 {
  return {
    headline: `${job.title}, ${job.domain}`,
    product_context: job.productContext,
    current_tasks: [
      "Deliver scoped features in production",
      "Work with team on code quality and bug fixes",
    ],
    current_challenges: [
      "Release quality under tight iteration cycles",
      "Balancing speed and reliability",
    ],
    core_tech: [...job.coreTech],
    key_requirements: [...job.mustHaveSkills],
    domain_need: "helpful",
    ownership_expectation: "contributor",
    notes_for_matching:
      "Prioritize junior candidates with real hands-on project work, clean communication, and steady delivery habits.",
  };
}

async function maybeBackfillQdrant(
  logger: ReturnType<typeof createLogger>,
  supabase: SupabaseRestClient,
): Promise<void> {
  const qdrantUrl = process.env.QDRANT_URL?.trim();
  const qdrantApiKey = process.env.QDRANT_API_KEY?.trim();
  const openaiApiKey = process.env.OPENAI_API_KEY?.trim();
  if (!qdrantUrl || !qdrantApiKey || !openaiApiKey) {
    logger.info("seed.test_jobs.qdrant_backfill.skipped", {
      reason: "missing_qdrant_or_openai_env",
    });
    return;
  }

  const embeddingsModel = process.env.OPENAI_EMBEDDINGS_MODEL?.trim() || "text-embedding-3-large";
  const qdrantCollection = process.env.QDRANT_CANDIDATE_COLLECTION?.trim() || "helly_candidates_v1";

  const profilesRepository = new ProfilesRepository(logger, supabase);
  const embeddingsClient = new EmbeddingsClient(openaiApiKey, embeddingsModel);
  const qdrantClient = new QdrantClient(
    {
      baseUrl: qdrantUrl,
      apiKey: qdrantApiKey,
      candidateCollection: qdrantCollection,
    },
    logger,
  );
  const backfill = new QdrantBackfillService(
    profilesRepository,
    embeddingsClient,
    qdrantClient,
    logger,
  );

  if (!backfill.isEnabled()) {
    logger.info("seed.test_jobs.qdrant_backfill.skipped", {
      reason: "qdrant_not_enabled",
    });
    return;
  }

  const result = await backfill.backfillExistingCandidates(500);
  logger.info("seed.test_jobs.qdrant_backfill.completed", result);
}

function mustEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Missing required env: ${name}`);
  }
  return value;
}

void main().catch((error) => {
  // eslint-disable-next-line no-console
  console.error("[seed:test-jobs] failed", error instanceof Error ? error.message : error);
  process.exitCode = 1;
});

