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
import { getNextQuestionIndex, isInterviewComplete } from "./interview-progress";
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
    const answerRecord: InterviewAnswer = {
      questionIndex: currentIndex,
      questionId: question.id,
      questionText: currentQuestionText,
      answerText: normalizedAnswer,
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

    this.stateService.upsertAnswer(session.userId, answerRecord);
    const updateResult = await this.updateProfileAfterAnswer(session, question, answerRecord);
    if (updateResult.followUpRequired) {
      const answersAfterCurrent = this.stateService.getAnswers(session.userId);
      const followUpsForQuestion = answersAfterCurrent.filter(
        (item) => item.questionIndex === currentIndex && item.isFollowUp,
      ).length;
      const totalFollowUps = answersAfterCurrent.filter((item) => item.isFollowUp).length;
      const followUpLimitReached = followUpsForQuestion >= 1 || totalFollowUps >= 2;

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
        };
      }
    }
    this.stateService.clearPendingFollowUp(session.userId);

    const answersAfter = this.stateService.getAnswers(session.userId);

    const skippedAfter = this.stateService.getSkippedQuestionIndexes(session.userId);
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

    const answers = this.stateService.getAnswers(session.userId);
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
  ): Promise<{ followUpRequired: boolean; followUpFocus: string }> {
    let followUpRequired = false;
    let followUpFocus = "";

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
        }

        const updated = await this.candidateProfileBuilder.update({
          candidateId: String(session.userId),
          previousProfile: session.candidateProfile,
          question,
          answerText: answerRecord.answerText,
          extractedText: session.candidateResumeText ?? "",
        });
        this.stateService.setCandidateProfile(session.userId, updated);
        return { followUpRequired, followUpFocus };
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

        const updated = await this.jobProfileBuilder.update({
          jobId: String(session.userId),
          previousProfile: session.jobProfile,
          question,
          answerText: answerRecord.answerText,
          extractedText: session.jobDescriptionText ?? "",
        });
        this.stateService.setJobProfile(session.userId, updated);
        return { followUpRequired, followUpFocus };
      }
    } catch (error) {
      this.logger.warn("Profile update failed after answer", {
        userId: session.userId,
        state: session.state,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    return { followUpRequired: false, followUpFocus: "" };
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
    !answers.some((item) => item.questionIndex === currentQuestionIndex) &&
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
  const normalizedFocus = focus.trim();
  const effectiveFocus = normalizedFocus || "the relevant decision and its impact";
  return `Quick follow up. Please clarify ${effectiveFocus} using one concrete example. Say what you did, what you chose, and why.`;
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

function isCandidateProfile(profile: CandidateProfile | JobProfile): profile is CandidateProfile {
  return "candidateId" in profile;
}

function isJobProfile(profile: CandidateProfile | JobProfile): profile is JobProfile {
  return "jobId" in profile;
}
