import { Logger } from "../../config/logger";
import { ProfilesRepository } from "../../db/repositories/profiles.repo";
import { JobProfileBuilder } from "../../profiles/job-profile.builder";
import { ProfileUpdateService } from "../../profiles/profile-update.service";
import { InterviewPlan } from "../../shared/types/domain.types";
import { InterviewAnswer, UserSessionState } from "../../shared/types/state.types";
import { StateService } from "../../state/state.service";
import { InterviewPlanService } from "../interview-plan.service";
import { ManagerJobProfileV2Service } from "../manager-job-profile-v2.service";
import { PrescreenV2Language } from "./candidate-prescreen.schemas";
import { JobAnswerInterpreter } from "./job-answer-interpreter";
import { JobClaimExtractor } from "./job-claim-extractor";
import { JobQuestionGenerator } from "./job-question-generator";
import {
  JobClaimExtractionResult,
  JobPrescreenFact,
  buildJobSummarySentence,
} from "./job-prescreen.schemas";

interface JobPrescreenBootstrapResult {
  summarySentence: string;
  plan: InterviewPlan;
  firstQuestion: string;
  claims: JobClaimExtractionResult;
  questionsGenerated: number;
}

interface JobPrescreenSubmitInput {
  answerText: string;
  originalText?: string;
  detectedLanguage?: "en" | "ru" | "uk" | "other";
  inputType: "text" | "voice";
  telegramVoiceFileId?: string;
  voiceDurationSec?: number;
  transcriptionStatus?: "success" | "failed";
}

export type JobPrescreenSubmitResult =
  | {
      kind: "reanswer_required";
      message: string;
      questionIndex: number;
    }
  | {
      kind: "next_question";
      questionIndex: number;
      questionText: string;
      isFollowUp?: boolean;
      preQuestionMessage?: string;
    }
  | {
      kind: "completed";
      completionMessage: string;
    };

const MAX_BASE_QUESTIONS = 8;
const MAX_TOTAL_FOLLOWUPS = 2;
const JOB_PRESCREEN_DONE_MESSAGE = "Thanks. Your job profile is updated. You can ask me to find candidates anytime.";

export class JobPrescreenEngine {
  constructor(
    private readonly claimExtractor: JobClaimExtractor,
    private readonly questionGenerator: JobQuestionGenerator,
    private readonly answerInterpreter: JobAnswerInterpreter,
    private readonly interviewPlanService: InterviewPlanService,
    private readonly jobProfileBuilder: JobProfileBuilder,
    private readonly managerJobProfileV2Service: ManagerJobProfileV2Service,
    private readonly profileUpdateService: ProfileUpdateService,
    private readonly stateService: StateService,
    private readonly profilesRepository: ProfilesRepository,
    private readonly logger: Logger,
  ) {}

  async bootstrap(
    session: UserSessionState,
    jdText: string,
    language: PrescreenV2Language,
  ): Promise<JobPrescreenBootstrapResult> {
    const jobAnalysis = await this.interviewPlanService.buildJobDescriptionAnalysisV1(
      session.userId,
      jdText,
    );
    if (!jobAnalysis.is_technical_role) {
      throw new Error("This role is outside Helly scope. Only technical hiring roles are supported.");
    }

    const claims = await this.claimExtractor.extract({
      jdText,
      existingJobProfile: session.managerJobProfileV2
        ? (session.managerJobProfileV2 as unknown as Record<string, unknown>)
        : session.jobProfile
        ? (session.jobProfile as unknown as Record<string, unknown>)
        : null,
      jobAnalysis,
    });

    try {
      await this.profileUpdateService.updateJobProfileFromJdExtract({
        telegramUserId: session.userId,
        jdAnalysis: jobAnalysis,
        claimExtraction: claims,
      });
    } catch (error) {
      this.logger.warn("job.prescreen.profile_sync.jd_extract_failed", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    const generated = await this.questionGenerator.generate({
      language,
      claimExtraction: claims,
      maxQuestions: MAX_BASE_QUESTIONS,
      knownFacts: session.jobPrescreenFacts ?? [],
    });
    if (!generated.questions.length) {
      throw new Error("Job prescreen v2 generated no questions.");
    }

    const plan: InterviewPlan = {
      summary: "Job Prescreen v2",
      questions: generated.questions.map((question) => ({
        id: question.id,
        question: question.question,
        goal: `Clarify ${question.topic}`,
        gapToClarify: question.topic,
      })),
    };

    const summarySentence = buildJobSummarySentence(claims, language);

    await this.profilesRepository.saveJobPrescreenSnapshot({
      telegramUserId: session.userId,
      prescreenVersion: "v2",
      snapshot: {
        language,
        claims,
        questions: generated.questions,
        current_question_index: 0,
        answers: [],
        facts: [],
      },
    });

    this.stateService.setJobPrescreenVersion(session.userId, "v2");
    this.stateService.setJobPrescreenPlan(session.userId, generated.questions);
    this.stateService.setJobPrescreenQuestionIndex(session.userId, 0);
    this.stateService.resetJobPrescreenAnswers(session.userId);
    this.stateService.resetJobPrescreenFacts(session.userId);
    this.stateService.resetJobPrescreenRetryMaps(session.userId);

    return {
      summarySentence,
      plan,
      firstQuestion: generated.questions[0].question,
      claims,
      questionsGenerated: generated.questions.length,
    };
  }

  async submitAnswer(
    session: UserSessionState,
    input: JobPrescreenSubmitInput,
  ): Promise<JobPrescreenSubmitResult> {
    const plan = session.interviewPlan;
    const prescreenPlan = session.jobPrescreenPlan ?? [];
    if (!plan || !prescreenPlan.length) {
      throw new Error("Job prescreen context is missing.");
    }

    const language = resolvePrescreenLanguage(session.preferredLanguage, input.detectedLanguage);
    const questionIndex = resolveQuestionIndex(session, plan.questions.length);
    if (questionIndex === null) {
      return {
        kind: "completed",
        completionMessage: JOB_PRESCREEN_DONE_MESSAGE,
      };
    }

    const question = plan.questions[questionIndex];
    const answerText = input.answerText.trim();
    const originalText = (input.originalText ?? input.answerText).trim();
    const knownFacts = session.jobPrescreenFacts ?? [];

    const interpretation = await this.answerInterpreter.interpret({
      language,
      question: question.question,
      answer: answerText,
      knownFacts,
    });

    const totalFollowUps = session.jobPrescreenTotalFollowUps ?? 0;
    const followUpsForQuestion = this.stateService.getJobPrescreenFollowUpCount(session.userId, questionIndex);
    if (
      interpretation.should_follow_up &&
      interpretation.follow_up_question &&
      followUpsForQuestion < 1 &&
      totalFollowUps < MAX_TOTAL_FOLLOWUPS
    ) {
      this.stateService.incrementJobPrescreenFollowUpCount(session.userId, questionIndex);
      this.stateService.incrementJobPrescreenTotalFollowUps(session.userId);
      this.stateService.setJobPrescreenQuestionIndex(session.userId, questionIndex);
      this.stateService.setCurrentQuestionIndex(session.userId, questionIndex);
      return {
        kind: "next_question",
        questionIndex,
        questionText: interpretation.follow_up_question,
        isFollowUp: true,
      };
    }

    const answerRecord: InterviewAnswer = {
      questionIndex,
      questionId: question.id,
      questionText: question.question,
      answerText,
      status: "final",
      originalText,
      normalizedEnglishText: answerText,
      detectedLanguage: input.detectedLanguage,
      inputType: input.inputType,
      telegramVoiceFileId: input.telegramVoiceFileId,
      voiceDurationSec: input.voiceDurationSec,
      transcriptionStatus: input.transcriptionStatus,
      answeredAt: new Date().toISOString(),
    };

    this.stateService.upsertAnswer(session.userId, answerRecord);
    this.stateService.addJobPrescreenAnswer(session.userId, {
      question_id: question.id,
      question_text: question.question,
      answer_text: answerText,
      interpreted_facts: interpretation.facts,
      notes: interpretation.notes,
      created_at: answerRecord.answeredAt,
    });
    this.stateService.upsertJobPrescreenFacts(session.userId, interpretation.facts);
    this.stateService.clearPendingFollowUp(session.userId);

    await this.updateJobProfileFromPrescreenAnswer(
      session,
      question,
      answerRecord,
      interpretation.facts,
      interpretation.notes,
    );
    await this.persistSnapshot(session.userId);

    const nextQuestionIndex = questionIndex + 1;
    if (nextQuestionIndex >= plan.questions.length) {
      this.stateService.clearCurrentQuestionIndex(session.userId);
      this.stateService.clearJobPrescreenQuestionIndex(session.userId);
      return {
        kind: "completed",
        completionMessage: JOB_PRESCREEN_DONE_MESSAGE,
      };
    }

    this.stateService.setJobPrescreenQuestionIndex(session.userId, nextQuestionIndex);
    this.stateService.setCurrentQuestionIndex(session.userId, nextQuestionIndex);

    return {
      kind: "next_question",
      questionIndex: nextQuestionIndex,
      questionText: plan.questions[nextQuestionIndex].question,
      preQuestionMessage: buildProgressNote(language, session.jobPrescreenAnswers?.length ?? 0),
    };
  }

  async skipCurrentQuestion(session: UserSessionState): Promise<JobPrescreenSubmitResult> {
    const plan = session.interviewPlan;
    if (!plan) {
      throw new Error("Job prescreen context is missing.");
    }

    const questionIndex = resolveQuestionIndex(session, plan.questions.length);
    if (questionIndex === null) {
      return {
        kind: "completed",
        completionMessage: JOB_PRESCREEN_DONE_MESSAGE,
      };
    }

    const nextQuestionIndex = questionIndex + 1;
    if (nextQuestionIndex >= plan.questions.length) {
      this.stateService.clearCurrentQuestionIndex(session.userId);
      this.stateService.clearJobPrescreenQuestionIndex(session.userId);
      return {
        kind: "completed",
        completionMessage: JOB_PRESCREEN_DONE_MESSAGE,
      };
    }

    this.stateService.setJobPrescreenQuestionIndex(session.userId, nextQuestionIndex);
    this.stateService.setCurrentQuestionIndex(session.userId, nextQuestionIndex);
    return {
      kind: "next_question",
      questionIndex: nextQuestionIndex,
      questionText: plan.questions[nextQuestionIndex].question,
    };
  }

  private async updateJobProfileFromPrescreenAnswer(
    session: UserSessionState,
    question: InterviewPlan["questions"][number],
    answerRecord: InterviewAnswer,
    facts: JobPrescreenFact[],
    notes?: string,
  ): Promise<void> {
    try {
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
    } catch (error) {
      this.logger.warn("job.prescreen.profile_update_v2_failed", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    try {
      const updated = await this.jobProfileBuilder.update({
        jobId: String(session.userId),
        previousProfile: session.jobProfile,
        question,
        answerText: answerRecord.answerText,
        extractedText: session.jobDescriptionText ?? "",
      });
      this.stateService.setJobProfile(session.userId, updated);
    } catch (error) {
      this.logger.warn("job.prescreen.profile_builder_failed", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    try {
      await this.profileUpdateService.updateJobProfileFromAnswerFacts({
        telegramUserId: session.userId,
        facts,
        notes,
      });
    } catch (error) {
      this.logger.warn("job.prescreen.profile_sync.answer_facts_failed", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }

  private async persistSnapshot(userId: number): Promise<void> {
    const latest = this.stateService.getSession(userId);
    if (!latest) {
      return;
    }
    await this.profilesRepository.saveJobPrescreenSnapshot({
      telegramUserId: userId,
      prescreenVersion: "v2",
      snapshot: {
        language: latest.preferredLanguage ?? "unknown",
        current_question_index: latest.jobPrescreenQuestionIndex ?? latest.currentQuestionIndex ?? 0,
        questions: latest.jobPrescreenPlan ?? [],
        answers: latest.jobPrescreenAnswers ?? [],
        facts: latest.jobPrescreenFacts ?? [],
      },
    });
  }
}

function resolvePrescreenLanguage(
  preferredLanguage: UserSessionState["preferredLanguage"],
  detectedLanguage?: "en" | "ru" | "uk" | "other",
): PrescreenV2Language {
  if (detectedLanguage === "ru" || detectedLanguage === "uk") {
    return detectedLanguage;
  }
  if (preferredLanguage === "ru" || preferredLanguage === "uk") {
    return preferredLanguage;
  }
  return "en";
}

function resolveQuestionIndex(
  session: UserSessionState,
  questionCount: number,
): number | null {
  const explicit = session.jobPrescreenQuestionIndex;
  if (typeof explicit === "number" && explicit >= 0 && explicit < questionCount) {
    return explicit;
  }
  const fallback = session.currentQuestionIndex;
  if (typeof fallback === "number" && fallback >= 0 && fallback < questionCount) {
    return fallback;
  }
  if (questionCount > 0) {
    return 0;
  }
  return null;
}

function buildProgressNote(language: PrescreenV2Language, answersCount: number): string | undefined {
  if (answersCount <= 0 || answersCount % 2 !== 0) {
    return undefined;
  }
  if (language === "ru") {
    return "Спасибо, это полезно. Продолжим.";
  }
  if (language === "uk") {
    return "Дякую, це корисно. Продовжимо.";
  }
  return "Thanks, this is helpful. Let us continue.";
}
