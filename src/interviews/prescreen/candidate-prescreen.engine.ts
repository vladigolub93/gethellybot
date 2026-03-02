import { Logger } from "../../config/logger";
import { ProfilesRepository } from "../../db/repositories/profiles.repo";
import { CandidateProfileBuilder } from "../../profiles/candidate-profile.builder";
import { ProfileUpdateService } from "../../profiles/profile-update.service";
import { InterviewPlan } from "../../shared/types/domain.types";
import { InterviewAnswer, UserSessionState } from "../../shared/types/state.types";
import { StateService } from "../../state/state.service";
import { CandidateProfileUpdateV2Service } from "../candidate-profile-update-v2.service";
import { CandidateResumeAnalysisService } from "../candidate-resume-analysis.service";
import { CandidateAnswerInterpreter } from "./candidate-answer-interpreter";
import { CandidateClaimExtractor } from "./candidate-claim-extractor";
import { CandidateQuestionGenerator } from "./candidate-question-generator";
import { AI_ASSISTED_WARNING_V3 } from "../../ai/prompts/shared/ai-assisted-warning-v3";
import {
  CandidateClaimExtractionResult,
  CandidatePrescreenAnswerRecord,
  CandidatePrescreenFact,
  PrescreenV2Language,
} from "./candidate-prescreen.schemas";

interface CandidatePrescreenBootstrapResult {
  summarySentence: string;
  plan: InterviewPlan;
  firstQuestion: string;
  claims: CandidateClaimExtractionResult;
  questionsGenerated: number;
}

interface CandidatePrescreenSubmitInput {
  answerText: string;
  originalText?: string;
  detectedLanguage?: "en" | "ru" | "uk" | "other";
  inputType: "text" | "voice";
  telegramVoiceFileId?: string;
  voiceDurationSec?: number;
  transcriptionStatus?: "success" | "failed";
}

export type CandidatePrescreenSubmitResult =
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
const MAX_AI_RETRIES_PER_QUESTION = 1;

const AI_REANSWER_MESSAGE: Record<PrescreenV2Language, string> = AI_ASSISTED_WARNING_V3 as Record<PrescreenV2Language, string>;
export class CandidatePrescreenEngine {
  constructor(
    private readonly claimExtractor: CandidateClaimExtractor,
    private readonly questionGenerator: CandidateQuestionGenerator,
    private readonly answerInterpreter: CandidateAnswerInterpreter,
    private readonly candidateResumeAnalysisService: CandidateResumeAnalysisService,
    private readonly candidateProfileBuilder: CandidateProfileBuilder,
    private readonly candidateProfileUpdateV2Service: CandidateProfileUpdateV2Service,
    private readonly profileUpdateService: ProfileUpdateService,
    private readonly stateService: StateService,
    private readonly profilesRepository: ProfilesRepository,
    private readonly logger: Logger,
  ) {}

  async bootstrap(
    session: UserSessionState,
    resumeText: string,
    language: PrescreenV2Language,
  ): Promise<CandidatePrescreenBootstrapResult> {
    const analysis = await this.candidateResumeAnalysisService.analyzeAndPersist(
      session.userId,
      resumeText,
    );

    if (!analysis.is_technical) {
      throw new Error("This profile is outside Helly scope. Only technical engineering resumes are supported.");
    }

    const claims = await this.claimExtractor.extract({
      resumeText,
      existingCandidateProfile: session.candidateProfile
        ? (session.candidateProfile as unknown as Record<string, unknown>)
        : null,
    });

    try {
      await this.profileUpdateService.updateCandidateProfileFromResumeExtract({
        telegramUserId: session.userId,
        resumeAnalysis: analysis,
        claimExtraction: claims,
        languagePreference: session.preferredLanguage ?? "unknown",
        contactPhone: session.contactPhoneNumber ?? null,
        name: session.contactFirstName ?? null,
      });
    } catch (error) {
      this.logger.warn("candidate.prescreen.profile_sync.resume_extract_failed", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    const generated = await this.questionGenerator.generate({
      language,
      claimExtraction: claims,
      maxQuestions: MAX_BASE_QUESTIONS,
      knownFacts: session.prescreenFacts ?? [],
    });

    if (!generated.questions.length) {
      throw new Error("Candidate prescreen v2 generated no questions.");
    }

    const plan: InterviewPlan = {
      summary: "Candidate Prescreen v2",
      questions: generated.questions.map((question) => ({
        id: question.id,
        question: question.question,
        goal: `Verify ${question.tech_or_topic}`,
        gapToClarify: question.tech_or_topic,
      })),
    };

    const summarySentence = buildSummarySentence(claims, language);

    await this.profilesRepository.saveCandidatePrescreenSnapshot({
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

    this.stateService.setPrescreenVersion(session.userId, "v2");
    this.stateService.setPrescreenPlan(session.userId, generated.questions);
    this.stateService.setPrescreenQuestionIndex(session.userId, 0);
    this.stateService.resetPrescreenAnswers(session.userId);
    this.stateService.resetPrescreenFacts(session.userId);
    this.stateService.resetPrescreenRetryMaps(session.userId);

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
    input: CandidatePrescreenSubmitInput,
  ): Promise<CandidatePrescreenSubmitResult> {
    const plan = session.interviewPlan;
    const prescreenPlan = session.prescreenPlan ?? [];
    if (!plan || !prescreenPlan.length) {
      throw new Error("Prescreen context is missing.");
    }

    const language = resolvePrescreenLanguage(session.preferredLanguage, input.detectedLanguage);
    const questionIndex = resolveQuestionIndex(session, plan.questions.length);
    if (questionIndex === null) {
      return {
        kind: "completed",
        completionMessage: "Thanks, your profile is updated. You can ask me to find jobs anytime.",
      };
    }

    const question = plan.questions[questionIndex];
    const answerText = input.answerText.trim();
    const originalText = (input.originalText ?? input.answerText).trim();
    const knownFacts = session.prescreenFacts ?? [];

    const interpretation = await this.answerInterpreter.interpret({
      language,
      question: question.question,
      answer: answerText,
      knownFacts,
    });

    const aiLikely = isLikelyAiAssisted(
      interpretation.ai_assisted_likelihood,
      interpretation.ai_assisted_confidence,
    );

    if (aiLikely) {
      const aiRetryCount = this.stateService.getPrescreenAiRetryCount(session.userId, questionIndex);
      if (aiRetryCount < MAX_AI_RETRIES_PER_QUESTION) {
        this.stateService.incrementPrescreenAiRetryCount(session.userId, questionIndex);
        return {
          kind: "reanswer_required",
          message: AI_REANSWER_MESSAGE[language],
          questionIndex,
        };
      }
    }

    const totalFollowUps = session.prescreenTotalFollowUps ?? 0;
    const followUpsForQuestion = this.stateService.getPrescreenFollowUpCount(session.userId, questionIndex);
    if (
      interpretation.should_follow_up &&
      interpretation.follow_up_question &&
      followUpsForQuestion < 1 &&
      totalFollowUps < MAX_TOTAL_FOLLOWUPS
    ) {
      this.stateService.incrementPrescreenFollowUpCount(session.userId, questionIndex);
      this.stateService.incrementPrescreenTotalFollowUps(session.userId);
      this.stateService.setPrescreenQuestionIndex(session.userId, questionIndex);
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
      qualityWarning: aiLikely,
      aiAssistedLikelihood: interpretation.ai_assisted_likelihood,
      aiAssistedConfidence: interpretation.ai_assisted_confidence,
      missingElements: interpretation.facts.length
        ? []
        : ["No verifiable project artifact in answer"],
      authenticitySignals: interpretation.notes ? [interpretation.notes] : [],
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
    this.stateService.addPrescreenAnswer(session.userId, {
      question_id: question.id,
      question_text: question.question,
      answer_text: answerText,
      interpreted_facts: interpretation.facts,
      notes: interpretation.notes,
      ai_assisted_likelihood: interpretation.ai_assisted_likelihood,
      ai_assisted_confidence: interpretation.ai_assisted_confidence,
      quality_warning: aiLikely,
      created_at: answerRecord.answeredAt,
    });
    this.stateService.upsertPrescreenFacts(session.userId, interpretation.facts);
    this.stateService.clearPendingFollowUp(session.userId);

    await this.updateCandidateProfileFromPrescreenAnswer(
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
      this.stateService.clearPrescreenQuestionIndex(session.userId);
      return {
        kind: "completed",
        completionMessage: "Thanks, your profile is updated. You can ask me to find jobs anytime.",
      };
    }

    this.stateService.setPrescreenQuestionIndex(session.userId, nextQuestionIndex);
    this.stateService.setCurrentQuestionIndex(session.userId, nextQuestionIndex);
    this.stateService.clearPrescreenAiRetryCount(session.userId, questionIndex);

    return {
      kind: "next_question",
      questionIndex: nextQuestionIndex,
      questionText: plan.questions[nextQuestionIndex].question,
      preQuestionMessage: buildProgressNote(language, session.prescreenAnswers?.length ?? 0),
    };
  }

  async skipCurrentQuestion(session: UserSessionState): Promise<CandidatePrescreenSubmitResult> {
    const plan = session.interviewPlan;
    if (!plan) {
      throw new Error("Prescreen context is missing.");
    }
    const questionIndex = resolveQuestionIndex(session, plan.questions.length);
    if (questionIndex === null) {
      return {
        kind: "completed",
        completionMessage: "Thanks, your profile is updated. You can ask me to find jobs anytime.",
      };
    }

    const nextQuestionIndex = questionIndex + 1;
    if (nextQuestionIndex >= plan.questions.length) {
      this.stateService.clearCurrentQuestionIndex(session.userId);
      this.stateService.clearPrescreenQuestionIndex(session.userId);
      return {
        kind: "completed",
        completionMessage: "Thanks, your profile is updated. You can ask me to find jobs anytime.",
      };
    }

    this.stateService.setPrescreenQuestionIndex(session.userId, nextQuestionIndex);
    this.stateService.setCurrentQuestionIndex(session.userId, nextQuestionIndex);

    return {
      kind: "next_question",
      questionIndex: nextQuestionIndex,
      questionText: plan.questions[nextQuestionIndex].question,
    };
  }

  private async updateCandidateProfileFromPrescreenAnswer(
    session: UserSessionState,
    question: InterviewPlan["questions"][number],
    answerRecord: InterviewAnswer,
    facts: CandidatePrescreenFact[],
    notes?: string,
  ): Promise<void> {
    try {
      const updated = await this.candidateProfileBuilder.update({
        candidateId: String(session.userId),
        previousProfile: session.candidateProfile,
        question,
        answerText: answerRecord.answerText,
        extractedText: session.candidateResumeText ?? "",
      });
      this.stateService.setCandidateProfile(session.userId, updated);
    } catch (error) {
      this.logger.warn("candidate.prescreen.profile_builder_failed", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    try {
      const profileUpdateV2 = await this.candidateProfileUpdateV2Service.updateFromAnswer({
        telegramUserId: session.userId,
        currentQuestion: {
          id: question.id,
          text: question.question,
          questionType: "depth_test",
          targetValidation: question.goal,
          basedOnField: question.gapToClarify,
        },
        answerText: answerRecord.answerText,
      });
      if (profileUpdateV2) {
        this.stateService.addCandidateConfidenceUpdates(
          session.userId,
          profileUpdateV2.confidence_updates,
        );
        this.stateService.addCandidateContradictionFlags(
          session.userId,
          profileUpdateV2.contradiction_flags,
        );
      }
    } catch (error) {
      this.logger.warn("candidate.prescreen.profile_update_v2_failed", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    try {
      await this.profileUpdateService.updateCandidateProfileFromAnswerFacts({
        telegramUserId: session.userId,
        facts,
        notes,
      });
    } catch (error) {
      this.logger.warn("candidate.prescreen.profile_sync.answer_facts_failed", {
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

    await this.profilesRepository.saveCandidatePrescreenSnapshot({
      telegramUserId: userId,
      prescreenVersion: "v2",
      snapshot: {
        language: latest.preferredLanguage ?? "unknown",
        current_question_index: latest.prescreenQuestionIndex ?? latest.currentQuestionIndex ?? 0,
        questions: latest.prescreenPlan ?? [],
        answers: latest.prescreenAnswers ?? [],
        facts: latest.prescreenFacts ?? [],
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
  const explicit = session.prescreenQuestionIndex;
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

function isLikelyAiAssisted(
  likelihood: "low" | "medium" | "high",
  confidence: number,
): boolean {
  return likelihood === "high" || (likelihood === "medium" && confidence >= 0.82);
}

function buildProgressNote(language: PrescreenV2Language, answersCount: number): string | undefined {
  if (answersCount <= 0) {
    return undefined;
  }
  if (answersCount % 2 !== 0) {
    return undefined;
  }
  if (language === "ru") {
    return "Спасибо, это полезно. Идем дальше.";
  }
  if (language === "uk") {
    return "Дякую, це корисно. Рухаємось далі.";
  }
  return "Thanks, this is helpful. Let us continue.";
}

function buildSummarySentence(
  claims: CandidateClaimExtractionResult,
  language: PrescreenV2Language,
): string {
  const role = claims.primary_roles[0] ?? "software engineer";
  const years = typeof claims.years_experience_estimate === "number"
    ? `~${claims.years_experience_estimate} years`
    : "unknown years";
  const topTech = claims.tech_claims
    .slice(0, 3)
    .map((claim) => claim.tech)
    .filter(Boolean)
    .join(", ");

  if (language === "ru") {
    return `Вижу, что ты в основном ${role.toLowerCase()}, примерно ${years}, и часто упоминаешь ${topTech || "основной backend стек"}. Я задам несколько коротких вопросов, чтобы подтвердить реальный практический опыт.`;
  }
  if (language === "uk") {
    return `Бачу, що ти переважно ${role.toLowerCase()}, приблизно ${years}, і часто згадуєш ${topTech || "основний backend стек"}. Я поставлю кілька коротких питань, щоб підтвердити реальний практичний досвід.`;
  }
  return `I see you are mainly a ${role} with ${years}, and you mention ${topTech || "a backend-focused stack"}. I will ask a few quick questions to confirm your real hands-on experience.`;
}
