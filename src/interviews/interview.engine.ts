import { EmbeddingsClient } from "../ai/embeddings.client";
import { Logger } from "../config/logger";
import { InterviewsRepository } from "../db/repositories/interviews.repo";
import { JobsRepository } from "../db/repositories/jobs.repo";
import { ProfilesRepository } from "../db/repositories/profiles.repo";
import { InterviewStorageService } from "../storage/interview-storage.service";
import { CandidateProfileBuilder } from "../profiles/candidate-profile.builder";
import { JobProfileBuilder } from "../profiles/job-profile.builder";
import { InterviewPlanService } from "./interview-plan.service";
import { CandidateProfile, InterviewPlan, JobProfile } from "../shared/types/domain.types";
import { StateService } from "../state/state.service";
import { InterviewAnswer, UserSessionState, UserState } from "../shared/types/state.types";
import { CandidateResumeAnalysisService } from "./candidate-resume-analysis.service";
import { CandidateProfileUpdateV2Service } from "./candidate-profile-update-v2.service";
import {
  CandidateInterviewConfidenceUpdate,
  CandidateTechnicalSummaryService,
} from "./candidate-technical-summary.service";
import { ManagerJobProfileV2Service } from "./manager-job-profile-v2.service";
import { ManagerJobTechnicalSummaryService } from "./manager-job-technical-summary.service";
import { evaluateInterviewBootstrap } from "./interview-bootstrap.guard";
import { getNextQuestionIndex, isFinalAnswer, isInterviewComplete } from "./interview-progress";
import { formatInterviewResultMessage, InterviewResultService } from "./interview-result.service";
import { interviewSummaryUnavailableMessage } from "../telegram/ui/messages";
import { CandidateInterviewPlanV2 } from "../shared/types/interview-plan.types";
import { CandidateResumeAnalysisV2 } from "../shared/types/candidate-analysis.types";
import { CandidateTechnicalSummaryV1 } from "../shared/types/candidate-summary.types";
import { JobDescriptionAnalysisV1 } from "../shared/types/job-analysis.types";
import { JobProfileV2, JobTechnicalSummaryV2 } from "../shared/types/job-profile.types";
import { QualityFlagsService } from "../qa/quality-flags.service";
import { InterviewConfirmationService } from "../confirmations/interview-confirmation.service";
import { QdrantBackfillService } from "../matching/qdrant-backfill.service";

export interface InterviewBootstrapResult {
  nextState: UserState;
  firstQuestion: string;
  plan: InterviewPlan;
  answerInstruction?: string;
  candidatePlanV2?: CandidateInterviewPlanV2;
  intakeOneLiner?: string;
}

export interface InterviewAnswerInput {
  answerText: string;
  originalText?: string;
  detectedLanguage?: "en" | "ru" | "uk" | "other";
  inputType: "text" | "voice";
  telegramVoiceFileId?: string;
  voiceDurationSec?: number;
  transcriptionStatus?: "success" | "failed";
}

export type InterviewAnswerResult =
  | {
      kind: "next_question";
      questionIndex: number;
      questionText: string;
      isFollowUp?: boolean;
      preQuestionMessage?: string;
    }
  | {
      kind: "reanswer_required";
      questionIndex: number;
      questionText: string;
      message: string;
    }
  | {
      kind: "completed";
      completedState: UserState;
      completionMessage: string;
      followupMessage?: string;
    };

export class InterviewEngine {
  constructor(
    private readonly interviewPlanService: InterviewPlanService,
    private readonly stateService: StateService,
    private readonly interviewResultService: InterviewResultService,
    private readonly interviewStorageService: InterviewStorageService,
    private readonly interviewsRepository: InterviewsRepository,
    private readonly candidateProfileBuilder: CandidateProfileBuilder,
    private readonly jobProfileBuilder: JobProfileBuilder,
    private readonly embeddingsClient: EmbeddingsClient,
    private readonly profilesRepository: ProfilesRepository,
    private readonly jobsRepository: JobsRepository,
    private readonly candidateResumeAnalysisService: CandidateResumeAnalysisService,
    private readonly candidateProfileUpdateV2Service: CandidateProfileUpdateV2Service,
    private readonly candidateTechnicalSummaryService: CandidateTechnicalSummaryService,
    private readonly managerJobProfileV2Service: ManagerJobProfileV2Service,
    private readonly managerJobTechnicalSummaryService: ManagerJobTechnicalSummaryService,
    private readonly interviewConfirmationService: InterviewConfirmationService,
    private readonly logger: Logger,
    private readonly qualityFlagsService?: QualityFlagsService,
    private readonly qdrantBackfillService?: QdrantBackfillService,
  ) {}

  async bootstrapInterview(
    session: UserSessionState,
    sourceText: string,
  ): Promise<InterviewBootstrapResult> {
    const bootstrap = evaluateInterviewBootstrap(session);
    if (session.interviewPlan) {
      throw new Error("Interview plan already exists. Please continue the current interview.");
    }

    const userId = session.userId;
    let answerInstruction: string | undefined;
    let candidatePlanV2: CandidateInterviewPlanV2 | undefined;
    let intakeOneLiner: string | undefined;
    let plan: InterviewPlan;

    if (bootstrap.role === "candidate") {
      try {
        const analysis = await this.candidateResumeAnalysisService.analyzeAndPersist(userId, sourceText);
        if (!analysis.is_technical) {
          throw new Error(
            "This profile is outside Helly scope. Only hands-on technical engineering resumes are supported.",
          );
        }

        candidatePlanV2 = await this.interviewPlanService.buildCandidateInterviewPlanV2(analysis, {
          telegramUserId: userId,
        });
        plan = this.interviewPlanService.mapCandidateInterviewPlanV2ToInterviewPlan(candidatePlanV2);
        answerInstruction = candidatePlanV2.answer_instruction;
        intakeOneLiner =
          (await this.interviewConfirmationService.generateCandidateIntakeOneLiner({
            telegramUserId: userId,
            resumeAnalysisJson: analysis,
            currentProfileJson: session.candidateProfile ?? {},
          })) ?? undefined;
        if (!intakeOneLiner) {
          intakeOneLiner = buildCandidateFallbackOneLiner(analysis);
        }
      } catch (error) {
        this.logger.warn("Candidate resume analysis v2 failed, fallback interview plan will be used", {
          userId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        plan = await this.interviewPlanService.buildPlan(bootstrap.role, sourceText, {
          telegramUserId: userId,
        });
        answerInstruction =
          "Please provide a detailed answer with concrete examples. You may respond in text or by sending a voice message.";
        intakeOneLiner = "I reviewed your resume and I will ask focused questions to validate real hands-on experience.";
      }
    } else {
      const jobAnalysis = await this.interviewPlanService.buildJobDescriptionAnalysisV1(
        userId,
        sourceText,
      );
      if (!jobAnalysis.is_technical_role) {
        throw new Error("This role is outside Helly scope. Only technical hiring roles are supported.");
      }

      const savedJobAnalysis = await this.interviewPlanService.getJobDescriptionAnalysis(userId);
      const analysisForPlan: JobDescriptionAnalysisV1 =
        savedJobAnalysis && savedJobAnalysis.is_technical_role ? savedJobAnalysis : jobAnalysis;
      const managerPlanV1 = await this.interviewPlanService.buildManagerInterviewPlanV1(
        analysisForPlan,
        {
          telegramUserId: userId,
        },
      );
      plan = this.interviewPlanService.mapManagerInterviewPlanV1ToInterviewPlan(managerPlanV1);
      answerInstruction = managerPlanV1.answer_instruction;
      intakeOneLiner =
        (await this.interviewConfirmationService.generateJobIntakeOneLiner({
          managerTelegramUserId: userId,
          jobAnalysisJson: analysisForPlan,
          currentJobProfileJson: session.managerJobProfileV2 ?? session.jobProfile ?? {},
        })) ?? undefined;
      if (!intakeOneLiner) {
        intakeOneLiner = buildManagerFallbackOneLiner(analysisForPlan);
      }

      // Keep backward path for unexpected failures to avoid breaking manager onboarding.
      if (!plan.questions.length) {
        plan = await this.interviewPlanService.buildPlan(bootstrap.role, sourceText, {
          telegramUserId: userId,
        });
      }
    }

    if (!plan.questions.length) {
      plan = await this.interviewPlanService.buildPlan(bootstrap.role, sourceText, {
        telegramUserId: userId,
      });
    }

    if (bootstrap.role === "candidate") {
      this.stateService.setCandidateResumeText(userId, sourceText);
    } else {
      this.stateService.setJobDescriptionText(userId, sourceText);
    }
    const firstQuestion = plan.questions[0]?.question;
    if (!firstQuestion) {
      throw new Error("Interview bootstrap failed: plan contains no questions.");
    }

    return {
      nextState: bootstrap.nextState,
      firstQuestion,
      plan,
      answerInstruction,
      candidatePlanV2,
      intakeOneLiner,
    };
  }

  async submitAnswer(
    session: UserSessionState,
    answer: InterviewAnswerInput,
  ): Promise<InterviewAnswerResult> {
    if (session.state !== "interviewing_candidate" && session.state !== "interviewing_manager") {
      throw new Error("Interview is not active. Use /start to begin.");
    }

    const plan = session.interviewPlan;
    if (!plan) {
      throw new Error("Interview context is missing. Please /start and upload your document again.");
    }

    const normalizedAnswer = answer.answerText.trim();
    const originalAnswer = (answer.originalText ?? answer.answerText).trim();
    if (!normalizedAnswer) {
      throw new Error("Please reply with text.");
    }

    const answersBefore = this.stateService.getAnswers(session.userId);
    const skippedBefore = this.stateService.getSkippedQuestionIndexes(session.userId);
    const currentIndex = resolveCurrentQuestionIndex(
      plan,
      answersBefore,
      skippedBefore,
      session.currentQuestionIndex,
      session.pendingFollowUp?.questionIndex,
    );

    if (currentIndex === null) {
      const completion = await this.completeInterview(session);
      return {
        kind: "completed",
        completedState: completion.completedState,
        completionMessage: completion.message,
        followupMessage: completion.followupMessage,
      };
    }

    const question = plan.questions[currentIndex];
    const pendingFollowUp = session.pendingFollowUp;
    const isFollowUpAnswer = Boolean(
      pendingFollowUp && pendingFollowUp.questionIndex === currentIndex,
    );
    const currentQuestionText = isFollowUpAnswer ? pendingFollowUp?.questionText ?? question.question : question.question;
    let answerRecord: InterviewAnswer = {
      questionIndex: currentIndex,
      questionId: question.id,
      questionText: currentQuestionText,
      answerText: normalizedAnswer,
      status: "final",
      qualityWarning: false,
      originalText: originalAnswer,
      normalizedEnglishText: normalizedAnswer,
      detectedLanguage: answer.detectedLanguage,
      inputType: answer.inputType,
      telegramVoiceFileId: answer.telegramVoiceFileId,
      voiceDurationSec: answer.voiceDurationSec,
      transcriptionStatus: answer.transcriptionStatus,
      isFollowUp: isFollowUpAnswer,
      answeredAt: new Date().toISOString(),
    };

    const updateResult = await this.updateProfileAfterAnswer(session, question, answerRecord);
    if (updateResult.candidateAuthenticity && session.state === "interviewing_candidate") {
      const aiAssistedScore = normalizeAiAssistedScore(
        updateResult.candidateAuthenticity.authenticityScore,
        updateResult.candidateAuthenticity.authenticityLabel,
      );
      const aiAssistedLikely =
        Boolean(updateResult.candidateAiAssistedLikely) ||
        aiAssistedScore >= AI_ASSISTED_SOFT_THRESHOLD;
      answerRecord = {
        ...answerRecord,
        authenticityScore: updateResult.candidateAuthenticity.authenticityScore,
        authenticitySignals: updateResult.candidateAuthenticity.authenticitySignals,
        authenticityLabel: updateResult.candidateAuthenticity.authenticityLabel,
        aiAssistedScore,
      };

      if (aiAssistedLikely) {
        const currentReanswerCount = this.stateService.getReanswerRequestCount(
          session.userId,
          currentIndex,
        );
        if (currentReanswerCount < MAX_REANSWER_REQUESTS_PER_QUESTION) {
          const nextReanswerCount = this.stateService.incrementReanswerRequestCount(
            session.userId,
            currentIndex,
          );
          answerRecord = {
            ...answerRecord,
            status: "draft",
            qualityWarning: false,
          };
          this.stateService.upsertAnswer(session.userId, answerRecord);
          this.stateService.setCurrentQuestionIndex(session.userId, currentIndex);
          this.stateService.clearPendingFollowUp(session.userId);
          return {
            kind: "reanswer_required",
            questionIndex: currentIndex,
            questionText: currentQuestionText,
            message: buildCandidateAiReanswerMessage(
              resolveReanswerLanguagePreference(session.preferredLanguage, answer.detectedLanguage),
              aiAssistedScore >= AI_ASSISTED_HARD_THRESHOLD,
              nextReanswerCount,
            ),
          };
        }

        answerRecord = {
          ...answerRecord,
          status: "final",
          qualityWarning: true,
        };
        await this.qualityFlagsService?.raise({
          entityType: "candidate",
          entityId: String(session.userId),
          flag: "candidate_ai_assisted_answer_likely",
          details: {
            questionIndex: currentIndex,
            authenticityScore: updateResult.candidateAuthenticity.authenticityScore,
            authenticitySignals: updateResult.candidateAuthenticity.authenticitySignals,
            aiAssistedScore,
            threshold: "max_reanswer_reached_accept_with_warning",
          },
        });
      }
    }

    this.stateService.upsertAnswer(session.userId, answerRecord);
    this.stateService.clearReanswerRequestCount(session.userId, currentIndex);

    const answersAfterCurrent = this.stateService.getAnswers(session.userId);
    const skippedAfterCurrent = this.stateService.getSkippedQuestionIndexes(session.userId);
    const interviewTurnCapReached = hasReachedInterviewTurnCap(
      answersAfterCurrent,
      skippedAfterCurrent,
    );

    if (updateResult.followUpRequired) {
      if (interviewTurnCapReached) {
        this.stateService.clearPendingFollowUp(session.userId);
      } else {
      const followUpsForQuestion = answersAfterCurrent.filter(
        (item) => item.questionIndex === currentIndex && item.isFollowUp && isFinalAnswer(item),
      ).length;
      const totalFollowUps = answersAfterCurrent.filter((item) => item.isFollowUp && isFinalAnswer(item)).length;
      const followUpLimitReached = followUpsForQuestion >= 1 || totalFollowUps >= 1;

      if (followUpLimitReached) {
        await this.qualityFlagsService?.raise({
          entityType: session.state === "interviewing_candidate" ? "candidate" : "job",
          entityId: String(session.userId),
          flag: "follow_up_loop_prevented",
          details: {
            questionIndex: currentIndex,
            followUpsForQuestion,
            totalFollowUps,
          },
        });
      } else {
        const followUpQuestionText = buildFollowUpQuestion(updateResult.followUpFocus);
        this.stateService.setPendingFollowUp(session.userId, {
          questionIndex: currentIndex,
          questionId: question.id,
          questionText: followUpQuestionText,
          focus: updateResult.followUpFocus,
        });
        this.stateService.setCurrentQuestionIndex(session.userId, currentIndex);
        return {
          kind: "next_question",
          questionIndex: currentIndex,
          questionText: followUpQuestionText,
          isFollowUp: true,
          preQuestionMessage: updateResult.preQuestionMessage,
        };
      }
      }
    }
    this.stateService.clearPendingFollowUp(session.userId);

    const answersAfter = this.stateService.getAnswers(session.userId);
    const skippedAfter = this.stateService.getSkippedQuestionIndexes(session.userId);
    if (hasReachedInterviewTurnCap(answersAfter, skippedAfter)) {
      this.stateService.clearCurrentQuestionIndex(session.userId);
      const completion = await this.completeInterview(session);
      return {
        kind: "completed",
        completedState: completion.completedState,
        completionMessage: completion.message,
        followupMessage: completion.followupMessage,
      };
    }
    if (isInterviewComplete(plan, answersAfter, skippedAfter)) {
      this.stateService.clearCurrentQuestionIndex(session.userId);
      const completion = await this.completeInterview(session);
      return {
        kind: "completed",
        completedState: completion.completedState,
        completionMessage: completion.message,
        followupMessage: completion.followupMessage,
      };
    }

    const nextQuestionIndex = getNextQuestionIndex(plan, answersAfter, skippedAfter);
    if (nextQuestionIndex === null) {
      this.stateService.clearCurrentQuestionIndex(session.userId);
      const completion = await this.completeInterview(session);
      return {
        kind: "completed",
        completedState: completion.completedState,
        completionMessage: completion.message,
        followupMessage: completion.followupMessage,
      };
    }

    this.stateService.setCurrentQuestionIndex(session.userId, nextQuestionIndex);
    return {
      kind: "next_question",
      questionIndex: nextQuestionIndex,
      questionText: plan.questions[nextQuestionIndex].question,
      isFollowUp: false,
      preQuestionMessage: updateResult.preQuestionMessage,
    };
  }

  async skipCurrentQuestion(session: UserSessionState): Promise<InterviewAnswerResult> {
    if (session.state !== "interviewing_candidate" && session.state !== "interviewing_manager") {
      throw new Error("Interview is not active.");
    }

    const plan = session.interviewPlan;
    if (!plan) {
      throw new Error("Interview context is missing.");
    }

    const answers = this.stateService
      .getAnswers(session.userId)
      .filter((item) => isFinalAnswer(item));
    const skipped = this.stateService.getSkippedQuestionIndexes(session.userId);
    const currentIndex = resolveCurrentQuestionIndex(
      plan,
      answers,
      skipped,
      session.currentQuestionIndex,
      session.pendingFollowUp?.questionIndex,
    );
    if (currentIndex === null) {
      const completion = await this.completeInterview(session);
      return {
        kind: "completed",
        completedState: completion.completedState,
        completionMessage: completion.message,
        followupMessage: completion.followupMessage,
      };
    }

    this.stateService.clearPendingFollowUp(session.userId);
    this.stateService.markQuestionSkipped(session.userId, currentIndex);
    const skippedAfter = this.stateService.getSkippedQuestionIndexes(session.userId);
    if (hasReachedInterviewTurnCap(answers, skippedAfter)) {
      this.stateService.clearCurrentQuestionIndex(session.userId);
      const completion = await this.completeInterview(session);
      return {
        kind: "completed",
        completedState: completion.completedState,
        completionMessage: completion.message,
        followupMessage: completion.followupMessage,
      };
    }
    const nextQuestionIndex = getNextQuestionIndex(plan, answers, skippedAfter);
    if (nextQuestionIndex === null) {
      this.stateService.clearCurrentQuestionIndex(session.userId);
      const completion = await this.completeInterview(session);
      return {
        kind: "completed",
        completedState: completion.completedState,
        completionMessage: completion.message,
        followupMessage: completion.followupMessage,
      };
    }

    this.stateService.setCurrentQuestionIndex(session.userId, nextQuestionIndex);
    return {
      kind: "next_question",
      questionIndex: nextQuestionIndex,
      questionText: plan.questions[nextQuestionIndex].question,
      isFollowUp: false,
    };
  }

  private async completeInterview(
    session: UserSessionState,
  ): Promise<{ completedState: UserState; message: string; followupMessage?: string }> {
    const completedState = getCompletedState(session.state);
    const role = session.state === "interviewing_candidate" ? "candidate" : "manager";
    const plan = session.interviewPlan;
    if (!plan) {
      return { completedState, message: interviewSummaryUnavailableMessage() };
    }

    const completedAt = new Date().toISOString();
    const startedAt = session.interviewStartedAt ?? completedAt;
    const answers = this.stateService.getAnswers(session.userId);
    const extractedText =
      role === "candidate" ? session.candidateResumeText ?? "" : session.jobDescriptionText ?? "";
    let candidateTechnicalSummary: CandidateTechnicalSummaryV1 | null = null;
    let managerTechnicalSummary: JobTechnicalSummaryV2 | null = null;

    if (role === "candidate") {
      try {
        const latestAnalysis = await this.profilesRepository.getCandidateResumeAnalysis(session.userId);
        if (latestAnalysis && latestAnalysis.is_technical) {
          candidateTechnicalSummary = await this.generateCandidateTechnicalSummary(
            latestAnalysis,
            session.candidateConfidenceUpdates ?? [],
            session.candidateContradictionFlags ?? [],
          );
          await this.profilesRepository.saveCandidateTechnicalSummary({
            telegramUserId: session.userId,
            technicalSummary: candidateTechnicalSummary,
          });
          this.stateService.setCandidateTechnicalSummary(session.userId, candidateTechnicalSummary);
        }
      } catch (error) {
        this.logger.warn("Candidate technical summary generation failed", {
          userId: session.userId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    if (role === "manager") {
      try {
        const latestJobProfile = await this.managerJobProfileV2Service.getCurrentJobProfile(session.userId);
        if (latestJobProfile) {
          managerTechnicalSummary = await this.managerJobTechnicalSummaryService.generate(
            latestJobProfile,
          );
          await this.jobsRepository.saveJobTechnicalSummary({
            managerTelegramUserId: session.userId,
            technicalSummary: managerTechnicalSummary,
          });
          this.stateService.setManagerTechnicalSummary(session.userId, managerTechnicalSummary);
        }
      } catch (error) {
        this.logger.warn("Manager job technical summary generation failed", {
          userId: session.userId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    let artifactMessage = interviewSummaryUnavailableMessage();
    let artifact = null;

    try {
      artifact = await this.interviewResultService.generateArtifact({
        role,
        extractedText,
        plan,
        answers,
      });
      artifactMessage = formatInterviewResultMessage(artifact);
    } catch (error) {
      this.logger.warn("Interview result generation failed, using fallback message", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    this.stateService.markInterviewCompleted(session.userId, completedAt, artifact ?? undefined);

    const record = {
      role,
      telegramUserId: session.userId,
      startedAt,
      completedAt,
      documentType: session.documentType ?? "unknown",
      extractedText,
      planQuestions: plan.questions.map((question) => ({
        id: question.id,
        question: question.question,
      })),
      answers,
      finalArtifact: artifact,
      finalProfile: role === "candidate" ? session.candidateProfile ?? null : session.jobProfile ?? null,
      candidateTechnicalSummary,
      managerTechnicalSummary,
      managerProfileUpdates: session.managerProfileUpdates ?? [],
      managerContradictionFlags: session.managerContradictionFlags ?? [],
    } as const;

    try {
      await this.interviewStorageService.save({
        role: record.role,
        telegramUserId: record.telegramUserId,
        startedAt: record.startedAt,
        completedAt: record.completedAt,
        documentType: record.documentType,
        extractedText: record.extractedText,
        planQuestions: record.planQuestions,
        answers: record.answers,
        finalArtifact: record.finalArtifact,
        finalProfile: record.finalProfile,
        managerTechnicalSummary: record.managerTechnicalSummary,
        managerProfileUpdates: record.managerProfileUpdates,
        managerContradictionFlags: record.managerContradictionFlags,
      });
    } catch (error) {
      this.logger.error("Failed to persist interview record", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    try {
      await this.interviewsRepository.saveCompletedInterview({
        role: record.role,
        telegramUserId: record.telegramUserId,
        startedAt: record.startedAt,
        completedAt: record.completedAt,
        documentType: record.documentType,
        extractedText: record.extractedText,
        planQuestions: record.planQuestions,
        answers: record.answers,
        finalArtifact: record.finalArtifact,
        finalProfile: record.finalProfile,
      });
    } catch (error) {
      this.logger.error("Failed to persist interview record to Supabase", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    await this.persistProfileAndJob(role, session.userId, record.finalProfile);

    return { completedState, message: artifactMessage };
  }

  private async updateProfileAfterAnswer(
    session: UserSessionState,
    question: InterviewPlan["questions"][number],
    answerRecord: InterviewAnswer,
  ): Promise<{
    followUpRequired: boolean;
    followUpFocus: string;
    preQuestionMessage?: string;
    candidateAiAssistedLikely?: boolean;
    candidateAuthenticity?: {
      authenticityScore: number;
      authenticityLabel: "likely_human" | "uncertain" | "likely_ai_assisted";
      authenticitySignals: string[];
    };
  }> {
    let followUpRequired = false;
    let followUpFocus = "";
    let preQuestionMessage: string | undefined;
    let candidateAuthenticity:
      | {
          authenticityScore: number;
          authenticityLabel: "likely_human" | "uncertain" | "likely_ai_assisted";
          authenticitySignals: string[];
        }
      | undefined;
    let candidateAiAssistedLikely = false;

    try {
      if (session.state === "interviewing_candidate") {
        const questionMetadata = resolveCandidateQuestionMetadata(
          session.candidateInterviewPlanV2,
          answerRecord.questionIndex,
          answerRecord.questionId,
          answerRecord.questionText,
        );
        const profileUpdateV2 = await this.candidateProfileUpdateV2Service.updateFromAnswer({
          telegramUserId: session.userId,
          currentQuestion: questionMetadata,
          answerText: answerRecord.answerText,
        });
        if (profileUpdateV2) {
          followUpRequired = profileUpdateV2.follow_up_required;
          followUpFocus = profileUpdateV2.follow_up_focus ?? "";
          candidateAuthenticity = {
            authenticityScore: profileUpdateV2.authenticity_score,
            authenticityLabel: profileUpdateV2.authenticity_label,
            authenticitySignals: profileUpdateV2.authenticity_signals,
          };
          this.stateService.addCandidateConfidenceUpdates(
            session.userId,
            profileUpdateV2.confidence_updates,
          );
          this.stateService.addCandidateContradictionFlags(
            session.userId,
            profileUpdateV2.contradiction_flags,
          );
          if (profileUpdateV2.answer_quality === "low") {
            const recentAnswers = this.stateService.getAnswers(session.userId).slice(-3);
            const lowSignal = recentAnswers.filter((item) => item.isFollowUp).length >= 2;
            if (lowSignal) {
              await this.qualityFlagsService?.raise({
                entityType: "candidate",
                entityId: String(session.userId),
                flag: "too_many_low_answer_quality_in_row",
                details: {
                  questionIndex: answerRecord.questionIndex,
                },
              });
            }
          }
          const aiAssistedScore = normalizeAiAssistedScore(
            profileUpdateV2.authenticity_score,
            profileUpdateV2.authenticity_label,
          );
          const aiAssistedLikely =
            aiAssistedScore >= AI_ASSISTED_SOFT_THRESHOLD ||
            shouldTreatCandidateAnswerAsAiAssisted(
              profileUpdateV2.authenticity_label,
              profileUpdateV2.authenticity_score,
              profileUpdateV2.authenticity_signals,
              answerRecord.answerText,
            );
          candidateAiAssistedLikely = aiAssistedLikely;
          if (aiAssistedLikely) {
            const nextStreak = (session.candidateAiAssistedStreak ?? 0) + 1;
            this.stateService.setCandidateAiAssistedStreak(session.userId, nextStreak);
            followUpRequired = true;
            if (!followUpFocus) {
              followUpFocus =
                "one concrete personal example from your real project, including your own decisions and trade offs";
            }
            preQuestionMessage = buildAiAssistedWarningMessage(nextStreak);
            await this.qualityFlagsService?.raise({
              entityType: "candidate",
              entityId: String(session.userId),
              flag: "candidate_ai_assisted_answer_likely",
              details: {
                questionIndex: answerRecord.questionIndex,
                authenticityScore: profileUpdateV2.authenticity_score,
                authenticitySignals: profileUpdateV2.authenticity_signals,
                aiAssistedScore,
                threshold:
                  aiAssistedScore >= AI_ASSISTED_HARD_THRESHOLD ? "hard" : "soft",
                streak: nextStreak,
              },
            });
            if (nextStreak >= 2) {
              this.stateService.setCandidateNeedsLiveValidation(session.userId, true);
              this.stateService.addCandidateConfidenceUpdates(session.userId, [
                {
                  field: "interview_authenticity_confidence",
                  previous_value: "medium",
                  new_value: "low",
                  reason:
                    "Multiple answers look AI-assisted and need live validation with concrete personal evidence.",
                },
              ]);
            }
          } else {
            this.stateService.setCandidateAiAssistedStreak(session.userId, 0);
          }
        }

        const updated = await this.candidateProfileBuilder.update({
          candidateId: String(session.userId),
          previousProfile: session.candidateProfile,
          question,
          answerText: answerRecord.answerText,
          extractedText: session.candidateResumeText ?? "",
        });
        this.stateService.setCandidateProfile(session.userId, updated);
        return {
          followUpRequired,
          followUpFocus,
          preQuestionMessage,
          candidateAuthenticity,
          candidateAiAssistedLikely,
        };
      }

      if (session.state === "interviewing_manager") {
        const managerProfileUpdate = await this.managerJobProfileV2Service.updateFromAnswer({
          managerTelegramUserId: session.userId,
          currentQuestionText: answerRecord.questionText,
          managerAnswerText: answerRecord.answerText,
        });
        this.stateService.setManagerJobProfileV2(
          session.userId,
          managerProfileUpdate.updated_job_profile,
        );
        this.stateService.addManagerProfileUpdates(
          session.userId,
          managerProfileUpdate.profile_updates,
        );
        this.stateService.addManagerContradictionFlags(
          session.userId,
          managerProfileUpdate.contradiction_flags,
        );

        followUpRequired = managerProfileUpdate.follow_up_required;
        followUpFocus = managerProfileUpdate.follow_up_focus ?? "";
        const managerAiAssistedLikely = shouldTreatManagerAnswerAsAiAssisted(
          managerProfileUpdate.authenticity_label,
          managerProfileUpdate.authenticity_score,
          managerProfileUpdate.authenticity_signals,
          answerRecord.answerText,
        );
        if (managerProfileUpdate.answer_quality === "low") {
          const recentAnswers = this.stateService.getAnswers(session.userId).slice(-3);
          const lowSignal = recentAnswers.filter((item) => item.isFollowUp).length >= 2;
          if (lowSignal) {
            await this.qualityFlagsService?.raise({
              entityType: "job",
              entityId: String(session.userId),
              flag: "too_many_low_answer_quality_in_row",
              details: {
                questionIndex: answerRecord.questionIndex,
              },
            });
          }
        }
        if (managerAiAssistedLikely) {
          const nextStreak = (session.managerAiAssistedStreak ?? 0) + 1;
          this.stateService.setManagerAiAssistedStreak(session.userId, nextStreak);
          followUpRequired = true;
          if (!followUpFocus) {
            followUpFocus =
              "one concrete role context with actual constraints, responsibilities, and expected outcomes in the first three months";
          }
          preQuestionMessage = buildManagerAiAssistedWarningMessage(nextStreak);
          await this.qualityFlagsService?.raise({
            entityType: "job",
            entityId: String(session.userId),
            flag: "manager_ai_assisted_answer_likely",
            details: {
              questionIndex: answerRecord.questionIndex,
              authenticityScore: managerProfileUpdate.authenticity_score,
              authenticitySignals: managerProfileUpdate.authenticity_signals,
              streak: nextStreak,
            },
          });
          if (nextStreak >= 2) {
            this.stateService.setManagerNeedsLiveValidation(session.userId, true);
            this.stateService.addManagerProfileUpdates(session.userId, [
              {
                field: "intake_authenticity_confidence",
                previous_value: "medium",
                new_value: "low",
                reason:
                  "Multiple manager answers look AI-assisted and require concrete operational examples.",
              },
            ]);
          }
        } else {
          this.stateService.setManagerAiAssistedStreak(session.userId, 0);
        }

        const updated = await this.jobProfileBuilder.update({
          jobId: String(session.userId),
          previousProfile: session.jobProfile,
          question,
          answerText: answerRecord.answerText,
          extractedText: session.jobDescriptionText ?? "",
        });
        this.stateService.setJobProfile(session.userId, updated);
        return { followUpRequired, followUpFocus, preQuestionMessage };
      }
    } catch (error) {
      this.logger.warn("Profile update failed after answer", {
        userId: session.userId,
        state: session.state,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    return {
      followUpRequired: false,
      followUpFocus: "",
      preQuestionMessage,
      candidateAuthenticity,
      candidateAiAssistedLikely,
    };
  }

  async generateCandidateTechnicalSummary(
    updatedResumeAnalysis: CandidateResumeAnalysisV2,
    confidenceUpdates: CandidateInterviewConfidenceUpdate[],
    contradictionFlags: string[],
  ): Promise<CandidateTechnicalSummaryV1> {
    return this.candidateTechnicalSummaryService.generateCandidateTechnicalSummary(
      updatedResumeAnalysis,
      confidenceUpdates,
      contradictionFlags,
    );
  }

  private async persistProfileAndJob(
    role: "candidate" | "manager",
    telegramUserId: number,
    finalProfile: CandidateProfile | JobProfile | null | undefined,
  ): Promise<void> {
    if (!finalProfile) {
      return;
    }

    let embedding: number[] | undefined;
    const searchableText = "searchableText" in finalProfile ? finalProfile.searchableText.trim() : "";
    if (searchableText) {
      try {
        embedding = await this.embeddingsClient.createEmbedding(searchableText);
      } catch (error) {
        this.logger.warn("Failed to generate embedding for final profile", {
          telegramUserId,
          role,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    try {
      if (role === "candidate" && isCandidateProfile(finalProfile)) {
        await this.profilesRepository.upsertCandidateProfile({
          telegramUserId,
          profile: finalProfile,
          embedding,
        });
        if (this.qdrantBackfillService?.isEnabled()) {
          await this.qdrantBackfillService.upsertCandidate(telegramUserId);
        }
        return;
      }

      if (role === "manager" && isJobProfile(finalProfile)) {
        await this.profilesRepository.upsertJobProfile({
          telegramUserId,
          profile: finalProfile,
          embedding,
        });
        await this.jobsRepository.upsertManagerJob({
          managerTelegramUserId: telegramUserId,
          status: "draft",
          jobSummary: finalProfile.searchableText,
          jobProfile: finalProfile,
        });
      }
    } catch (error) {
      this.logger.warn("Failed to persist final profile entities to Supabase", {
        telegramUserId,
        role,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }
}

function getCompletedState(state: UserState): UserState {
  return state === "interviewing_candidate" ? "candidate_profile_ready" : "job_profile_ready";
}

function resolveCurrentQuestionIndex(
  plan: InterviewPlan,
  answers: ReadonlyArray<InterviewAnswer>,
  skippedQuestionIndexes: ReadonlyArray<number>,
  currentQuestionIndex?: number,
  pendingFollowUpQuestionIndex?: number,
): number | null {
  if (
    typeof pendingFollowUpQuestionIndex === "number" &&
    pendingFollowUpQuestionIndex >= 0 &&
    pendingFollowUpQuestionIndex < plan.questions.length
  ) {
    return pendingFollowUpQuestionIndex;
  }

  if (
    typeof currentQuestionIndex === "number" &&
    currentQuestionIndex >= 0 &&
    currentQuestionIndex < plan.questions.length &&
    !answers.some((item) => item.questionIndex === currentQuestionIndex && isFinalAnswer(item)) &&
    !skippedQuestionIndexes.includes(currentQuestionIndex)
  ) {
    return currentQuestionIndex;
  }

  return getNextQuestionIndex(plan, answers, skippedQuestionIndexes);
}

function resolveCandidateQuestionMetadata(
  planV2: CandidateInterviewPlanV2 | undefined,
  questionIndex: number,
  questionId: string,
  fallbackQuestionText: string,
): {
  id: string;
  text: string;
  questionType?: string;
  targetValidation?: string;
  basedOnField?: string;
} {
  const question = planV2?.questions[questionIndex];
  if (!question) {
    return {
      id: questionId,
      text: fallbackQuestionText,
    };
  }

  return {
    id: question.question_id || questionId,
    text: question.question_text || fallbackQuestionText,
    questionType: question.question_type,
    targetValidation: question.target_validation,
    basedOnField: question.based_on_field,
  };
}

function buildFollowUpQuestion(focus: string): string {
  const effectiveFocus = simplifyFollowUpFocus(focus);
  return `Quick follow up. Please give one concrete example about ${effectiveFocus}, what you did and why.`;
}

function simplifyFollowUpFocus(focus: string): string {
  const fallback = "the key decision and the outcome";
  const normalized = focus
    .replace(/\s+/g, " ")
    .replace(/[“”"']/g, "")
    .replace(/[—–]/g, ", ")
    .trim();
  if (!normalized) {
    return fallback;
  }

  let candidate = normalized;
  const colonIndex = candidate.indexOf(":");
  if (colonIndex >= 0 && colonIndex < candidate.length - 1) {
    const afterColon = candidate.slice(colonIndex + 1).trim();
    if (afterColon.length >= 12) {
      candidate = afterColon;
    }
  }

  candidate = candidate
    .replace(/^(can you|could you|please|to make this concrete|quick follow up)[,:]?\s*/i, "")
    .replace(/^(confirm whether|confirm if)\s+/i, "")
    .replace(/\b(then|and then|plus)\b.*$/i, "")
    .replace(/[.?!;].*$/, "")
    .replace(/,\s*(with|using)\b.*$/i, "")
    .trim();

  if (!candidate) {
    return fallback;
  }

  const words = candidate.split(/\s+/).filter(Boolean).slice(0, 16);
  const compact = words.join(" ").replace(/[,:]+$/g, "").trim();
  return compact.length >= 6 ? compact : fallback;
}

function buildAiAssistedWarningMessage(streak: number): string {
  if (streak >= 2) {
    return "This still looks AI-generated. Please do not paste AI text, answer from your own real experience. A short voice reply is preferred.";
  }
  return "This looks AI-assisted and too generic. Please reply from your real project experience in your own words, voice is preferred.";
}

function buildManagerAiAssistedWarningMessage(streak: number): string {
  if (streak >= 2) {
    return "This still looks AI-generated and generic. Please do not paste AI text, share real hiring context from your team, voice is preferred.";
  }
  return "This looks AI-assisted and generic. Please answer in your own words with one real role example from your team, voice is preferred.";
}

const AI_ASSISTED_SOFT_THRESHOLD = 0.7;
const AI_ASSISTED_HARD_THRESHOLD = 0.85;
const MAX_REANSWER_REQUESTS_PER_QUESTION = 2;

function normalizeAiAssistedScore(
  authenticityScore: number,
  authenticityLabel: "likely_human" | "uncertain" | "likely_ai_assisted",
): number {
  let score = clamp01(authenticityScore);
  if (authenticityLabel === "likely_human") {
    score = 1 - score;
  } else if (authenticityLabel === "likely_ai_assisted") {
    score = Math.max(score, 1 - score);
  }

  if (authenticityLabel === "likely_ai_assisted" && score < AI_ASSISTED_SOFT_THRESHOLD) {
    return AI_ASSISTED_SOFT_THRESHOLD;
  }
  return score;
}

function resolveReanswerLanguagePreference(
  preferredLanguage: "en" | "ru" | "uk" | "unknown" | undefined,
  detectedLanguage: "en" | "ru" | "uk" | "other" | undefined,
): "en" | "ru" | "uk" {
  if (preferredLanguage === "ru" || preferredLanguage === "uk") {
    return preferredLanguage;
  }
  if (detectedLanguage === "ru" || detectedLanguage === "uk") {
    return detectedLanguage;
  }
  return "en";
}

function buildCandidateAiReanswerMessage(
  language: "en" | "ru" | "uk",
  isHard: boolean,
  attemptNumber: number,
): string {
  if (language === "ru") {
    return isHard
      ? `Это выглядит слишком идеально, похоже на AI-ответ. Я не пытаюсь вас поймать, мне нужен ваш реальный опыт. Пожалуйста, ответьте заново: один реальный проект, что лично сделали вы, и одна конкретная прод-деталь. Голосом тоже отлично. Попытка ${attemptNumber} из ${MAX_REANSWER_REQUESTS_PER_QUESTION}.`
      : `Это звучит слишком гладко, похоже на AI-ответ. Я не пытаюсь вас поймать, мне нужен ваш реальный опыт. Пожалуйста, ответьте заново: один реальный проект, что лично сделали вы, и одна конкретная прод-деталь. Голосом тоже можно. Попытка ${attemptNumber} из ${MAX_REANSWER_REQUESTS_PER_QUESTION}.`;
  }
  if (language === "uk") {
    return isHard
      ? `Це виглядає занадто ідеально, схоже на AI-відповідь. Я не намагаюся вас підловити, мені потрібен ваш реальний досвід. Будь ласка, дайте відповідь ще раз: один реальний проєкт, що саме ви зробили, і одна конкретна прод-деталь. Голосом теж ок. Спроба ${attemptNumber} з ${MAX_REANSWER_REQUESTS_PER_QUESTION}.`
      : `Це звучить трохи занадто гладко, схоже на AI-відповідь. Я не намагаюся вас підловити, мені потрібен ваш реальний досвід. Будь ласка, дайте відповідь ще раз: один реальний проєкт, що саме ви зробили, і одна конкретна прод-деталь. Голосом теж можна. Спроба ${attemptNumber} з ${MAX_REANSWER_REQUESTS_PER_QUESTION}.`;
  }
  return isHard
    ? `This feels a bit too perfect, like an AI answer. I am not trying to catch you, I just need your real experience. Please answer again with one real project, what you personally did, and one concrete production detail. Voice message is totally fine if that is easier. Attempt ${attemptNumber}/${MAX_REANSWER_REQUESTS_PER_QUESTION}.`
    : `This feels a bit too perfect, like an AI answer. I am not trying to catch you, I just need your real experience. Please answer again with one real project, what you personally did, and one concrete production detail. Voice message is totally fine if that is easier. Attempt ${attemptNumber}/${MAX_REANSWER_REQUESTS_PER_QUESTION}.`;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  if (value < 0) {
    return 0;
  }
  if (value > 1) {
    return 1;
  }
  return value;
}

function shouldTreatCandidateAnswerAsAiAssisted(
  authenticityLabel: "likely_human" | "uncertain" | "likely_ai_assisted",
  authenticityScore: number,
  authenticitySignals: ReadonlyArray<string>,
  answerText: string,
): boolean {
  if (authenticityLabel === "likely_ai_assisted" || authenticityScore <= 0.35) {
    return true;
  }

  if (containsFabricationAdmission(answerText)) {
    return true;
  }

  const signalsLookAi = hasAiAuthenticitySignals(authenticitySignals);
  if (signalsLookAi) {
    return true;
  }

  const templatedNarrative = looksTemplatedNarrative(answerText);
  if (authenticityLabel === "uncertain" && authenticityScore <= 0.6 && templatedNarrative) {
    return true;
  }

  if (looksOverStructuredAiEssay(answerText)) {
    return true;
  }

  return false;
}

function shouldTreatManagerAnswerAsAiAssisted(
  authenticityLabel: "likely_human" | "uncertain" | "likely_ai_assisted",
  authenticityScore: number,
  authenticitySignals: ReadonlyArray<string>,
  answerText: string,
): boolean {
  if (authenticityLabel === "likely_ai_assisted" || authenticityScore <= 0.35) {
    return true;
  }

  if (containsFabricationAdmission(answerText)) {
    return true;
  }

  const signalsLookAi = hasAiAuthenticitySignals(authenticitySignals);
  if (signalsLookAi) {
    return true;
  }

  const templatedNarrative = looksTemplatedNarrative(answerText);
  if (authenticityLabel === "uncertain" && authenticityScore <= 0.6 && templatedNarrative) {
    return true;
  }

  if (looksOverStructuredAiEssay(answerText)) {
    return true;
  }

  return false;
}

function hasAiAuthenticitySignals(authenticitySignals: ReadonlyArray<string>): boolean {
  if (authenticitySignals.length === 0) {
    return false;
  }
  const joined = authenticitySignals.join(" ").toLowerCase();
  return /generic|template|boilerplate|polished but generic|hypothetical|not personal|non-responsive|fabricat|invented|copied|ai-assisted|ai generated|no concrete/.test(
    joined,
  );
}

function containsFabricationAdmission(answerText: string): boolean {
  const text = answerText.trim().toLowerCase();
  if (!text) {
    return false;
  }

  return (
    /\bi made (it )?up\b/.test(text) ||
    /\bi invented (it|this)\b/.test(text) ||
    /\bi do not have (that|this|real) experience\b/.test(text) ||
    /\bno real experience\b/.test(text) ||
    /я придумал/.test(text) ||
    /нет у меня такого опыта/.test(text) ||
    /не маю такого досвіду/.test(text)
  );
}

function looksTemplatedNarrative(answerText: string): boolean {
  const text = answerText.trim();
  if (text.length < 550) {
    return false;
  }

  const sectionMarkers = text.match(
    /(^|\n)\s*(ui|api|backend|database|db|response|flow|step\s*\d+|frontend|service)\s*[.:]/gim,
  );
  const markerCount = sectionMarkers?.length ?? 0;

  const paragraphCount = text.split(/\n{2,}/).filter((segment) => segment.trim().length > 0).length;
  return markerCount >= 3 || paragraphCount >= 4;
}

function looksOverStructuredAiEssay(answerText: string): boolean {
  const text = answerText.trim();
  if (text.length < 350) {
    return false;
  }

  const lower = text.toLowerCase();
  const structuralMarkers = [
    "in the ui",
    "in the api layer",
    "at the database layer",
    "on success",
    "what i owned personally",
    "i owned",
    "the tradeoff",
    "the trade-off",
    "end to end",
    "if you want, i can also",
    "if you want i can also",
    "sure. i will",
    "we chose",
  ];
  const markersMatched = structuralMarkers.filter((marker) => lower.includes(marker)).length;
  const paragraphCount = text.split(/\n{2,}/).filter((segment) => segment.trim().length > 0).length;
  const hasWeakConcreteSignal = !/\b(p95|p99|ms|rps|qps|incident|oncall|slo|sla|postmortem|migration|rollback|ticket|pager|prometheus|grafana)\b/i.test(
    text,
  );
  const hasUiApiDbSequence =
    lower.includes("in the ui") &&
    lower.includes("in the api layer") &&
    lower.includes("at the database layer");

  return (
    (paragraphCount >= 4 && markersMatched >= 3 && hasWeakConcreteSignal) ||
    (hasUiApiDbSequence && markersMatched >= 2)
  );
}

function buildCandidateFallbackOneLiner(analysis: CandidateResumeAnalysisV2): string {
  const direction = analysis.primary_direction === "unknown" ? "technical" : analysis.primary_direction;
  const seniority = analysis.seniority_estimate === "unknown" ? "level not fully clear yet" : analysis.seniority_estimate;
  const coreTech = analysis.core_technologies
    .map((item) => item.name.trim())
    .filter(Boolean)
    .slice(0, 3)
    .join(", ");
  const techPart = coreTech ? ` across ${coreTech}` : "";
  return `I parsed your resume as a ${seniority} ${direction} profile${techPart}, now I will validate depth with focused questions.`;
}

function buildManagerFallbackOneLiner(analysis: JobDescriptionAnalysisV1): string {
  const roleTitle = analysis.role_title_guess?.trim() || "technical role";
  const coreTech = analysis.technology_signal_map.likely_core.slice(0, 3).join(", ");
  const techPart = coreTech ? ` with likely core tech ${coreTech}` : "";
  return `I parsed this as a ${roleTitle}${techPart}, next I will clarify real tasks, constraints, and expectations.`;
}

function hasReachedInterviewTurnCap(
  answers: ReadonlyArray<InterviewAnswer>,
  skippedQuestionIndexes: ReadonlyArray<number>,
): boolean {
  const finalAnswersCount = answers.filter((item) => isFinalAnswer(item)).length;
  return finalAnswersCount + skippedQuestionIndexes.length >= 10;
}

function isCandidateProfile(profile: CandidateProfile | JobProfile): profile is CandidateProfile {
  return "candidateId" in profile;
}

function isJobProfile(profile: CandidateProfile | JobProfile): profile is JobProfile {
  return "jobId" in profile;
}
