import express, { Express, Request, Response } from "express";
import {
  extractCookie,
  issueAdminSessionToken,
  verifyAdminSessionToken,
  verifyTelegramInitData,
} from "./admin/admin-auth.service";
import { renderAdminWebappPage } from "./admin/admin-webapp.page";
import { AdminWebappService } from "./admin/admin-webapp.service";
import { DbStatusService } from "./admin/db-status.service";
import { EnvConfig } from "./config/env";
import { OutboundMessageComposerService } from "./ai/outbound-message-composer.service";
import { ActionRouterService } from "./ai/action-router/action-router.service";
import { RouterV2Service } from "./ai/router.v2";
import { AdminNotifier, setDefaultAdminNotifier } from "./admin/admin-notifier";
import { createLogger, Logger } from "./config/logger";
import { EmbeddingsClient } from "./ai/embeddings.client";
import { CHAT_MODEL, EMBEDDINGS_MODEL, LlmClient, TRANSCRIPTION_MODEL } from "./ai/llm.client";
import { TranscriptionClient } from "./ai/transcription.client";
import { DocumentService } from "./documents/document.service";
import { TelegramFileService } from "./documents/storage/telegram-file.service";
import { InterviewsRepository } from "./db/repositories/interviews.repo";
import { JobsRepository } from "./db/repositories/jobs.repo";
import { MatchesRepository } from "./db/repositories/matches.repo";
import { DataDeletionRepository } from "./db/repositories/data-deletion.repo";
import { NotificationLimitsRepository } from "./db/repositories/notification-limits.repo";
import { ProfilesRepository } from "./db/repositories/profiles.repo";
import { QualityFlagsRepository } from "./db/repositories/quality-flags.repo";
import { StatesRepository } from "./db/repositories/states.repo";
import { TelegramUpdatesRepository } from "./db/repositories/telegram-updates.repo";
import { UsersRepository } from "./db/repositories/users.repo";
import { SupabaseRestClient } from "./db/supabase.client";
import { ContactExchangeService } from "./decisions/contact-exchange.service";
import { DecisionService } from "./decisions/decision.service";
import { InterviewEngine } from "./interviews/interview.engine";
import { InterviewPlanService } from "./interviews/interview-plan.service";
import { InterviewResultService } from "./interviews/interview-result.service";
import { CandidateResumeAnalysisService } from "./interviews/candidate-resume-analysis.service";
import { CandidateProfileUpdateV2Service } from "./interviews/candidate-profile-update-v2.service";
import { CandidateTechnicalSummaryService } from "./interviews/candidate-technical-summary.service";
import { InterviewIntentRouterService } from "./interviews/interview-intent-router.service";
import { CandidateNameExtractorService } from "./interviews/candidate-name-extractor.service";
import { ManagerJobProfileV2Service } from "./interviews/manager-job-profile-v2.service";
import { ManagerJobTechnicalSummaryService } from "./interviews/manager-job-technical-summary.service";
import { AnswerEvaluatorService } from "./interviews/answer-evaluator.service";
import { CandidateAnswerInterpreter } from "./interviews/prescreen/candidate-answer-interpreter";
import { CandidateClaimExtractor } from "./interviews/prescreen/candidate-claim-extractor";
import { CandidatePrescreenEngine } from "./interviews/prescreen/candidate-prescreen.engine";
import { CandidateQuestionGenerator } from "./interviews/prescreen/candidate-question-generator";
import { JobAnswerInterpreter } from "./interviews/prescreen/job-answer-interpreter";
import { JobClaimExtractor } from "./interviews/prescreen/job-claim-extractor";
import { JobPrescreenEngine } from "./interviews/prescreen/job-prescreen.engine";
import { JobQuestionGenerator } from "./interviews/prescreen/job-question-generator";
import { HiringScopeGuardrailsService } from "./guardrails/hiring-scope-guardrails.service";
import { NormalizationService } from "./i18n/normalization.service";
import { MatchCardComposerService } from "./matching/match-card-composer.service";
import { MatchingEngine } from "./matching/matching.engine";
import { QdrantClient } from "./matching/qdrant.client";
import { QdrantBackfillService } from "./matching/qdrant-backfill.service";
import { VectorSearchRepository } from "./matching/vector-search.repo";
import { CandidateNotifier } from "./notifications/candidate-notifier";
import { ManagerNotifier } from "./notifications/manager-notifier";
import { NotificationEngine } from "./notifications/notification.engine";
import { InterviewReminderService } from "./notifications/interview-reminder.service";
import { RateLimitService } from "./notifications/rate-limit.service";
import { DataDeletionService } from "./privacy/data-deletion.service";
import { CandidateProfileBuilder } from "./profiles/candidate-profile.builder";
import { JobProfileBuilder } from "./profiles/job-profile.builder";
import { ProfileUpdateService } from "./profiles/profile-update.service";
import { ProfileSummaryService } from "./profiles/profile-summary.service";
import { CandidateMandatoryFieldsService } from "./profiles/candidate-mandatory-fields.service";
import { JobMandatoryFieldsService } from "./jobs/job-mandatory-fields.service";
import { InterviewConfirmationService } from "./confirmations/interview-confirmation.service";
import { QualityFlagsService } from "./qa/quality-flags.service";
import { StateRouter } from "./router/state.router";
import { GatekeeperService } from "./core/state/gatekeeper/gatekeeper.service";
import { buildLlmGateDispatcher } from "./router/dispatch/llm-gate.dispatcher";
import { AlwaysOnRouterService } from "./router/always-on-router.service";
import { UserRagContextService } from "./router/context/user-rag-context.service";
import { DialogueOrchestrator } from "./router/dialogue/dialogue.orchestrator";
import { IntentClassifier } from "./router/dialogue/intent.classifier";
import { LanguageService } from "./router/dialogue/language.service";
import { ReplyComposerV2 } from "./router/dialogue/reply.composer";
import { DialogueOrchestratorV2 } from "./dialogue/dialogue.orchestrator";
import { IntentRouterV2Service } from "./dialogue/intent-router-v2.service";
import { InterviewStorageService } from "./storage/interview-storage.service";
import { MatchStorageService } from "./storage/match-storage.service";
import { StateService } from "./state/state.service";
import { StatePersistenceService } from "./state/state-persistence.service";
import { configureTelegramIdempotency } from "./shared/utils/telegram-idempotency";
import { TelegramClient } from "./telegram/telegram.client";
import { buildWebhookController } from "./telegram/webhook.controller";

export interface AppContext {
  app: Express;
  telegramClient: TelegramClient;
  logger: Logger;
}

export function createApp(env: EnvConfig): AppContext {
  const logger = createLogger({
    telegram: {
      enabled: env.telegramLogsEnabled,
      token: env.telegramBotToken,
      chatId: env.telegramLogsChatId,
      minLevel: env.telegramLogsLevel,
      ratePerMinute: env.telegramLogsRatePerMin,
      batchMs: env.telegramLogsBatchMs,
    },
  });
  if (env.adminTelegramChatId) {
    const adminNotifier = new AdminNotifier({
      botToken: env.telegramBotToken,
      adminChatId: env.adminTelegramChatId,
      minLevel: env.adminLogLevel,
      logger,
    });
    setDefaultAdminNotifier(adminNotifier);
  }
  const app = express();

  app.use(express.json({ limit: "2mb" }));

  const llmClient = new LlmClient(env.openaiApiKey, logger, CHAT_MODEL);
  const outboundMessageComposer = new OutboundMessageComposerService(llmClient, logger);
  const telegramClient = new TelegramClient(
    env.telegramBotToken,
    logger,
    env.telegramButtonsEnabled,
    (input) => outboundMessageComposer.compose(input),
  );
  const telegramFileService = new TelegramFileService(telegramClient);
  const documentService = new DocumentService(logger);
  const transcriptionClient = new TranscriptionClient(
    env.openaiApiKey,
    TRANSCRIPTION_MODEL || env.openaiTranscriptionModel,
  );
  const embeddingsClient = new EmbeddingsClient(
    env.openaiApiKey,
    EMBEDDINGS_MODEL || env.openaiEmbeddingModel,
  );
  const interviewResultService = new InterviewResultService(llmClient);
  const candidateProfileBuilder = new CandidateProfileBuilder(llmClient);
  const jobProfileBuilder = new JobProfileBuilder(llmClient);
  const profileSummaryService = new ProfileSummaryService();
  const interviewStorageService = new InterviewStorageService();
  const qdrantClient = new QdrantClient(
    {
      baseUrl: env.qdrantUrl,
      apiKey: env.qdrantApiKey,
      candidateCollection: env.qdrantCandidateCollection,
    },
    logger,
  );
  logger.info("Qdrant vector search", {
    enabled: qdrantClient.isEnabled(),
    collection: env.qdrantCandidateCollection,
  });
  const supabaseClient =
    env.supabaseUrl && env.supabaseApiKey
      ? new SupabaseRestClient({
          url: env.supabaseUrl,
          serviceRoleKey: env.supabaseApiKey,
        })
      : undefined;
  const interviewsRepository = new InterviewsRepository(logger, supabaseClient);
  const profilesRepository = new ProfilesRepository(logger, supabaseClient);
  const vectorSearchRepository = new VectorSearchRepository(
    profilesRepository,
    logger,
  );
  const jobsRepository = new JobsRepository(logger, supabaseClient);
  const matchesRepository = new MatchesRepository(logger, supabaseClient);
  const dataDeletionRepository = new DataDeletionRepository(logger, supabaseClient);
  const notificationLimitsRepository = new NotificationLimitsRepository(logger, supabaseClient);
  const qualityFlagsRepository = new QualityFlagsRepository(logger, supabaseClient);
  const usersRepository = new UsersRepository(logger, supabaseClient);
  const candidateMandatoryFieldsService = new CandidateMandatoryFieldsService(usersRepository);
  const jobMandatoryFieldsService = new JobMandatoryFieldsService(jobsRepository);
  const interviewConfirmationService = new InterviewConfirmationService(
    llmClient,
    profilesRepository,
    jobsRepository,
    logger,
  );
  const statesRepository = new StatesRepository(logger, supabaseClient);
  const telegramUpdatesRepository = new TelegramUpdatesRepository(logger, supabaseClient);
  configureTelegramIdempotency({
    repository: telegramUpdatesRepository,
    logger,
  });
  const stateService = new StateService();
  const statePersistenceService = new StatePersistenceService(
    logger,
    usersRepository,
    statesRepository,
  );
  const dataDeletionService = new DataDeletionService(
    dataDeletionRepository,
    usersRepository,
    logger,
    qdrantClient,
  );
  const adminWebappService = new AdminWebappService(
    logger,
    dataDeletionService,
    supabaseClient,
    qdrantClient,
  );
  const qualityFlagsService = new QualityFlagsService(qualityFlagsRepository, logger);
  const guardrailsService = new HiringScopeGuardrailsService(
    llmClient,
    logger,
    qualityFlagsService,
  );
  const rateLimitService = new RateLimitService(notificationLimitsRepository, logger);
  const interviewPlanService = new InterviewPlanService(
    llmClient,
    logger,
    profilesRepository,
    jobsRepository,
    qualityFlagsService,
  );
  const candidateResumeAnalysisService = new CandidateResumeAnalysisService(
    llmClient,
    profilesRepository,
    qualityFlagsService,
  );
  const candidateProfileUpdateV2Service = new CandidateProfileUpdateV2Service(
    llmClient,
    profilesRepository,
    logger,
    qualityFlagsService,
  );
  const candidateTechnicalSummaryService = new CandidateTechnicalSummaryService(llmClient);
  const alwaysOnRouterService = new AlwaysOnRouterService(llmClient, logger);
  const actionRouterService = new ActionRouterService(llmClient, logger);
  const gatekeeperService = new GatekeeperService();
  const routerV2Service = new RouterV2Service(llmClient, logger);
  const languageService = new LanguageService(usersRepository, logger);
  const intentClassifier = new IntentClassifier(llmClient, logger);
  const replyComposerV2 = new ReplyComposerV2(llmClient, logger, env.prescreenV3Enabled);
  const dialogueOrchestrator = new DialogueOrchestrator(
    intentClassifier,
    languageService,
    replyComposerV2,
    logger,
  );
  const intentRouterV2 = new IntentRouterV2Service(llmClient, logger);
  const interviewIntentRouterService = new InterviewIntentRouterService(llmClient, logger);
  const candidateNameExtractorService = new CandidateNameExtractorService(llmClient, logger);
  const normalizationService = new NormalizationService(llmClient);
  const userRagContextService = new UserRagContextService(
    usersRepository,
    profilesRepository,
    jobsRepository,
    logger,
  );
  const managerJobProfileV2Service = new ManagerJobProfileV2Service(
    llmClient,
    jobsRepository,
    qualityFlagsService,
  );
  const managerJobTechnicalSummaryService = new ManagerJobTechnicalSummaryService(llmClient);
  const answerEvaluatorService = new AnswerEvaluatorService(llmClient, logger);
  const candidateClaimExtractor = new CandidateClaimExtractor(llmClient, logger);
  const candidateQuestionGenerator = new CandidateQuestionGenerator(llmClient, logger);
  const candidateAnswerInterpreter = new CandidateAnswerInterpreter(llmClient, logger);
  const jobClaimExtractor = new JobClaimExtractor(llmClient, logger);
  const jobQuestionGenerator = new JobQuestionGenerator(llmClient, logger);
  const jobAnswerInterpreter = new JobAnswerInterpreter(llmClient, logger);
  const profileUpdateService = new ProfileUpdateService(
    llmClient,
    embeddingsClient,
    profilesRepository,
    vectorSearchRepository,
    logger,
  );
  const candidatePrescreenEngine = new CandidatePrescreenEngine(
    candidateClaimExtractor,
    candidateQuestionGenerator,
    candidateAnswerInterpreter,
    candidateResumeAnalysisService,
    candidateProfileBuilder,
    candidateProfileUpdateV2Service,
    profileUpdateService,
    stateService,
    profilesRepository,
    logger,
  );
  const jobPrescreenEngine = new JobPrescreenEngine(
    jobClaimExtractor,
    jobQuestionGenerator,
    jobAnswerInterpreter,
    interviewPlanService,
    jobProfileBuilder,
    managerJobProfileV2Service,
    profileUpdateService,
    stateService,
    profilesRepository,
    logger,
  );
  const matchStorageService = new MatchStorageService(logger, matchesRepository);
  const matchingEngine = new MatchingEngine(
    interviewStorageService,
    embeddingsClient,
    vectorSearchRepository,
    profilesRepository,
    jobsRepository,
    usersRepository,
    matchStorageService,
    llmClient,
    logger,
    qdrantClient,
    qualityFlagsService,
  );
  const matchCardComposerService = new MatchCardComposerService(llmClient, logger);
  const dialogueOrchestratorV2 = new DialogueOrchestratorV2(
    intentRouterV2,
    async (input) => {
      const result = await replyComposerV2.compose({
        userRole: input.userRole,
        userLanguage: input.userLanguage,
        currentState: input.currentState,
        lastUserMessage: input.lastUserMessage,
        nextQuestionText: input.nextQuestionText,
        userFrustrated: input.userFrustrated,
      });
      return result?.message ?? null;
    },
    logger,
    matchingEngine,
    matchCardComposerService,
  );
  const qdrantBackfillService = new QdrantBackfillService(
    profilesRepository,
    embeddingsClient,
    qdrantClient,
    logger,
  );
  const decisionService = new DecisionService(matchStorageService, jobsRepository, logger);
  const contactExchangeService = new ContactExchangeService(
    stateService,
    usersRepository,
    telegramClient,
    logger,
  );
  const candidateNotifier = new CandidateNotifier(telegramClient);
  const managerNotifier = new ManagerNotifier(telegramClient, logger);
  const notificationEngine = new NotificationEngine(
    stateService,
    statePersistenceService,
    telegramClient,
    candidateNotifier,
    managerNotifier,
    rateLimitService,
    jobsRepository,
    usersRepository,
    logger,
  );
  const interviewReminderService = new InterviewReminderService(
    statesRepository,
    telegramClient,
    logger,
  );
  const interviewEngine = new InterviewEngine(
    interviewPlanService,
    stateService,
    interviewResultService,
    interviewStorageService,
    interviewsRepository,
    candidateProfileBuilder,
    jobProfileBuilder,
    embeddingsClient,
    profilesRepository,
    jobsRepository,
    candidateResumeAnalysisService,
    candidateProfileUpdateV2Service,
    candidateTechnicalSummaryService,
    managerJobProfileV2Service,
    managerJobTechnicalSummaryService,
    interviewConfirmationService,
    answerEvaluatorService,
    logger,
    qualityFlagsService,
    qdrantBackfillService,
  );
  if (env.qdrantBackfillOnStart && qdrantBackfillService.isEnabled()) {
    void qdrantBackfillService
      .backfillExistingCandidates(500)
      .then((result) => {
        logger.info("Qdrant backfill on start finished", result);
      })
      .catch((error) => {
        logger.warn("Qdrant backfill on start failed", {
          error: error instanceof Error ? error.message : "Unknown error",
        });
      });
  }
  if (env.interviewReminderEnabled && interviewReminderService.isEnabled()) {
    const intervalMs = Math.floor(env.interviewReminderCheckIntervalMinutes * 60 * 1000);
    setTimeout(() => {
      void interviewReminderService.sendDueReminders().catch((error) => {
        logger.warn("interview.reminder.initial_run_failed", {
          error: error instanceof Error ? error.message : "Unknown error",
        });
      });
    }, 25_000);
    setInterval(() => {
      void interviewReminderService.sendDueReminders().catch((error) => {
        logger.warn("interview.reminder.scheduled_run_failed", {
          error: error instanceof Error ? error.message : "Unknown error",
        });
      });
    }, intervalMs);
    logger.info("Interview reminder scheduler started", {
      intervalMinutes: env.interviewReminderCheckIntervalMinutes,
    });
  }
  const stateRouter = new StateRouter(
    stateService,
    statePersistenceService,
    telegramClient,
    telegramFileService,
    documentService,
    transcriptionClient,
    env.voiceMaxDurationSec,
    env.telegramReactionsEnabled,
    env.telegramReactionsProbability,
    interviewEngine,
    matchingEngine,
    matchStorageService,
    notificationEngine,
    candidateMandatoryFieldsService,
    jobMandatoryFieldsService,
    decisionService,
    contactExchangeService,
    profileSummaryService,
    guardrailsService,
    dataDeletionService,
    usersRepository,
    jobsRepository,
    profilesRepository,
    llmClient,
    routerV2Service,
    alwaysOnRouterService,
    interviewIntentRouterService,
    normalizationService,
    interviewConfirmationService,
    userRagContextService,
    candidateNameExtractorService,
    env.prescreenV2Enabled,
    env.jobPrescreenV2Enabled,
    candidatePrescreenEngine,
    jobPrescreenEngine,
    logger,
    env.conversationStateV2Enabled,
    dialogueOrchestratorV2,
    env.dialogueV2Enabled,
    replyComposerV2,
    languageService,
    dialogueOrchestrator,
    env.adminUserIds,
    env.enableTypedRoleSelectionRouter,
    env.enableTypedContactRouter,
    env.enableTypedCvRouter,
    env.enableTypedJdRouter,
    env.enableTypedCandidateMandatoryRouter,
    env.enableTypedManagerMandatoryRouter,
    env.enableTypedCandidateDecisionRouter,
    env.enableTypedManagerDecisionRouter,
    env.enableTypedInterviewInviteRouter,
    env.enableTypedInterviewAnswerRouter,
    env.enableTypedCandidateReviewRouter,
    env.enableTypedManagerReviewRouter,
    actionRouterService,
    gatekeeperService,
  );
  const llmGateDispatcher = buildLlmGateDispatcher({
    stateRouter,
    logger,
  });
  const webhookController = buildWebhookController({
    dispatcher: llmGateDispatcher,
    logger,
    secretToken: env.telegramSecretToken,
  });

  app.get("/health", (_request: Request, response: Response) => {
    response.status(200).json({ ok: true });
  });

  const dbStatusService = new DbStatusService(logger, supabaseClient);
  const adminSessionCookieName = "helly_admin_session";
  const adminSessionSecret = env.adminSecret || env.telegramBotToken;

  function readAdminSession(request: Request): {
    telegramUserId?: number;
    username?: string;
  } | null {
    const cookieToken = extractCookie(request.header("cookie"), adminSessionCookieName);
    const bearerToken = extractBearerToken(request.header("authorization"));
    const token = cookieToken || bearerToken;
    if (!token) {
      return null;
    }
    const payload = verifyAdminSessionToken(token, adminSessionSecret);
    if (!payload) {
      return null;
    }
    if (
      env.adminUserIds.length > 0 &&
      (!payload.telegramUserId || !env.adminUserIds.includes(payload.telegramUserId))
    ) {
      return null;
    }
    return {
      telegramUserId: payload.telegramUserId,
      username: payload.username,
    };
  }

  app.get("/admin/webapp", async (request: Request, response: Response) => {
    response.setHeader("Cache-Control", "no-store, no-cache, must-revalidate");
    response.setHeader("Pragma", "no-cache");
    response.setHeader("Expires", "0");
    let initialDashboard = null;
    const session = readAdminSession(request);
    if (session) {
      try {
        initialDashboard = await adminWebappService.getDashboardData();
      } catch (error) {
        logger.warn("admin.webapp.initial_dashboard_failed", {
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }
    response.status(200).type("html").send(renderAdminWebappPage(initialDashboard));
  });

  app.get("/admin/webapp-open", async (request: Request, response: Response) => {
    response.setHeader("Cache-Control", "no-store, no-cache, must-revalidate");
    response.setHeader("Pragma", "no-cache");
    response.setHeader("Expires", "0");
    let initialDashboard = null;
    const session = readAdminSession(request);
    if (session) {
      try {
        initialDashboard = await adminWebappService.getDashboardData();
      } catch (error) {
        logger.warn("admin.webapp_open.initial_dashboard_failed", {
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }
    response.status(200).type("html").send(renderAdminWebappPage(initialDashboard));
  });

  app.post("/admin/api/auth/login", (request: Request, response: Response) => {
    const initData =
      typeof request.body?.initData === "string"
        ? request.body.initData
        : "";
    if (!initData.trim()) {
      response.status(400).json({ ok: false, error: "Missing Telegram initData" });
      return;
    }

    const verification = verifyTelegramInitData(initData, env.telegramBotToken);
    if (!verification.ok || !verification.identity) {
      logger.warn("Admin login failed due to Telegram validation", {
        error: verification.error ?? "unknown_error",
      });
      response.status(401).json({
        ok: false,
        error: `Telegram validation failed: ${verification.error ?? "unknown_error"}`,
      });
      return;
    }

    if (
      env.adminUserIds.length > 0 &&
      !env.adminUserIds.includes(verification.identity.telegramUserId)
    ) {
      logger.warn("Admin login blocked by ADMIN_USER_IDS", {
        telegramUserId: verification.identity.telegramUserId,
      });
      response.status(403).json({ ok: false, error: "Access denied" });
      return;
    }

    const sessionToken = issueAdminSessionToken({
      secret: adminSessionSecret,
      ttlSeconds: env.adminWebappSessionTtlSec,
      telegramUserId: verification.identity.telegramUserId,
      username: verification.identity.username,
    });

    response.setHeader(
      "Set-Cookie",
      buildCookieHeader(adminSessionCookieName, sessionToken, env.adminWebappSessionTtlSec, env.nodeEnv === "production"),
    );
    response.status(200).json({
      ok: true,
      sessionToken,
      telegramUserId: verification.identity.telegramUserId,
      username: verification.identity.username ?? null,
    });
    logger.info("Admin login succeeded with Telegram initData", {
      telegramUserId: verification.identity.telegramUserId,
    });
  });

  app.post("/admin/api/auth/telegram-login", (request: Request, response: Response) => {
    const initData =
      typeof request.body?.initData === "string"
        ? request.body.initData
        : "";
    if (!initData.trim()) {
      response.status(400).json({ ok: false, error: "Missing Telegram initData" });
      return;
    }

    const verification = verifyTelegramInitData(initData, env.telegramBotToken);
    if (!verification.ok || !verification.identity) {
      logger.warn("Admin telegram-login failed due to Telegram validation", {
        error: verification.error ?? "unknown_error",
      });
      response.status(401).json({
        ok: false,
        error: `Telegram validation failed: ${verification.error ?? "unknown_error"}`,
      });
      return;
    }

    const allowedAdminIds = env.adminUserIds;
    if (
      allowedAdminIds.length > 0 &&
      !allowedAdminIds.includes(verification.identity.telegramUserId)
    ) {
      logger.warn("Admin telegram-login blocked by ADMIN_USER_IDS", {
        telegramUserId: verification.identity.telegramUserId,
      });
      response.status(403).json({ ok: false, error: "Access denied" });
      return;
    }

    const sessionToken = issueAdminSessionToken({
      secret: adminSessionSecret,
      ttlSeconds: env.adminWebappSessionTtlSec,
      telegramUserId: verification.identity.telegramUserId,
      username: verification.identity.username,
    });
    response.setHeader(
      "Set-Cookie",
      buildCookieHeader(adminSessionCookieName, sessionToken, env.adminWebappSessionTtlSec, env.nodeEnv === "production"),
    );
    response.status(200).json({
      ok: true,
      sessionToken,
      telegramUserId: verification.identity.telegramUserId,
      username: verification.identity.username ?? null,
    });
    logger.info("Admin login succeeded with Telegram auto-login", {
      telegramUserId: verification.identity.telegramUserId,
    });
  });

  app.post("/admin/api/auth/logout", (_request: Request, response: Response) => {
    response.setHeader(
      "Set-Cookie",
      buildCookieHeader(adminSessionCookieName, "", 0, env.nodeEnv === "production"),
    );
    response.status(200).json({ ok: true });
  });

  app.get("/admin/api/session", (request: Request, response: Response) => {
    const session = readAdminSession(request);
    if (!session) {
      response.status(401).json({ ok: false, error: "Unauthorized" });
      return;
    }
    response.status(200).json({ ok: true, session });
  });

  app.get("/admin/api/dashboard", async (request: Request, response: Response) => {
    const session = readAdminSession(request);
    if (!session) {
      response.status(401).json({ ok: false, error: "Access denied" });
      return;
    }
    try {
      const dashboard = await adminWebappService.getDashboardData();
      response.status(200).json(dashboard);
    } catch (error) {
      logger.error("admin.dashboard.load_failed", {
        error: error instanceof Error ? error.message : "Unknown error",
      });
      response.status(500).json({
        ok: false,
        error: "Dashboard data load failed. Check Supabase credentials and migrations.",
      });
    }
  });

  app.delete("/admin/api/users/:telegramUserId", async (request: Request, response: Response) => {
    const session = readAdminSession(request);
    if (!session) {
      response.status(401).json({ ok: false, error: "Access denied" });
      return;
    }
    const telegramUserId = Number(request.params.telegramUserId);
    const result = await adminWebappService.deleteUser(telegramUserId);
    response.status(result.ok ? 200 : 400).json(result);
  });

  app.delete(
    "/admin/api/candidates/:telegramUserId",
    async (request: Request, response: Response) => {
      const session = readAdminSession(request);
      if (!session) {
        response.status(401).json({ ok: false, error: "Access denied" });
        return;
      }
      const telegramUserId = Number(request.params.telegramUserId);
      const result = await adminWebappService.deleteCandidate(telegramUserId);
      response.status(result.ok ? 200 : 400).json(result);
    },
  );

  app.delete("/admin/api/jobs/:jobId", async (request: Request, response: Response) => {
    const session = readAdminSession(request);
    if (!session) {
      response.status(401).json({ ok: false, error: "Access denied" });
      return;
    }
    const result = await adminWebappService.deleteJob(String(request.params.jobId ?? ""));
    response.status(result.ok ? 200 : 400).json(result);
  });

  app.get("/admin/db-status", async (request: Request, response: Response) => {
    if (!env.adminSecret) {
      response.status(503).json({
        ok: false,
        missing_tables: [],
        missing_columns: [],
        applied_migrations_count: 0,
      });
      return;
    }

    const providedSecret =
      request.header("x-admin-secret") ??
      (typeof request.query.secret === "string" ? request.query.secret : "");
    if (!providedSecret || providedSecret !== env.adminSecret) {
      response.status(401).json({ ok: false, error: "Unauthorized" });
      return;
    }

    const report = await dbStatusService.getStatus();
    response.status(report.ok ? 200 : 503).json(report);
  });

  app.use(env.telegramWebhookPath, webhookController);

  return { app, telegramClient, logger };
}

function buildCookieHeader(
  name: string,
  value: string,
  maxAgeSeconds: number,
  secure: boolean,
): string {
  const parts = [
    `${name}=${encodeURIComponent(value)}`,
    "Path=/admin",
    "HttpOnly",
    "SameSite=Lax",
    `Max-Age=${maxAgeSeconds}`,
  ];
  if (secure) {
    parts.push("Secure");
  }
  return parts.join("; ");
}

function extractBearerToken(authorizationHeader: string | undefined): string | null {
  if (!authorizationHeader) {
    return null;
  }
  const trimmed = authorizationHeader.trim();
  if (!trimmed.toLowerCase().startsWith("bearer ")) {
    return null;
  }
  const token = trimmed.slice(7).trim();
  return token.length > 0 ? token : null;
}
