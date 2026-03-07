import { callJsonPromptSafe } from "../ai/llm.safe";
import { LlmClient } from "../ai/llm.client";
import { buildCandidateOneLinerV1Prompt } from "../ai/prompts/confirmations/candidate-one-liner.v1.prompt";
import { buildInterviewProgressOneLinerV1Prompt } from "../ai/prompts/confirmations/interview-progress-one-liner.v1.prompt";
import { buildJobOneLinerV1Prompt } from "../ai/prompts/confirmations/job-one-liner.v1.prompt";
import { Logger } from "../config/logger";
import { JobsRepository } from "../db/repositories/jobs.repo";
import { ProfilesRepository } from "../db/repositories/profiles.repo";

interface OneLinerPayload {
  one_liner?: unknown;
}

export class InterviewConfirmationService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly profilesRepository: ProfilesRepository,
    private readonly jobsRepository: JobsRepository,
    private readonly logger: Logger,
  ) {}

  async generateCandidateIntakeOneLiner(input: {
    telegramUserId: number;
    resumeAnalysisJson: unknown;
    currentProfileJson: unknown;
  }): Promise<string | null> {
    const prompt = buildCandidateOneLinerV1Prompt({
      resumeAnalysisJson: input.resumeAnalysisJson,
      currentProfileJson: input.currentProfileJson,
    });

    const oneLiner = await this.generateOneLiner({
      prompt,
      promptName: "candidate_one_liner_v1",
      schemaHint: "JSON object with one_liner as a one sentence string.",
    });
    if (!oneLiner) {
      return null;
    }

    await this.profilesRepository.saveLastConfirmationOneLiner({
      telegramUserId: input.telegramUserId,
      oneLiner,
    });
    return oneLiner;
  }

  async generateJobIntakeOneLiner(input: {
    managerTelegramUserId: number;
    jobAnalysisJson: unknown;
    currentJobProfileJson: unknown;
  }): Promise<string | null> {
    const prompt = buildJobOneLinerV1Prompt({
      jobAnalysisJson: input.jobAnalysisJson,
      currentJobProfileJson: input.currentJobProfileJson,
    });

    const oneLiner = await this.generateOneLiner({
      prompt,
      promptName: "job_one_liner_v1",
      schemaHint: "JSON object with one_liner as a one sentence string.",
    });
    if (!oneLiner) {
      return null;
    }

    await this.jobsRepository.saveLastConfirmationOneLiner({
      managerTelegramUserId: input.managerTelegramUserId,
      oneLiner,
    });
    return oneLiner;
  }

  async generateInterviewProgressOneLiner(input: {
    telegramUserId: number;
    role: "candidate" | "manager";
    lastAnswersEnglish: string[];
    currentProfileJson: unknown;
  }): Promise<string | null> {
    const prompt = buildInterviewProgressOneLinerV1Prompt({
      role: input.role,
      lastAnswersEnglish: input.lastAnswersEnglish,
      currentProfileJson: input.currentProfileJson,
    });
    const oneLiner = await this.generateOneLiner({
      prompt,
      promptName: "interview_progress_one_liner_v1",
      schemaHint: "JSON object with one_liner as a one sentence string.",
    });
    if (!oneLiner) {
      return null;
    }

    if (input.role === "candidate") {
      await this.profilesRepository.saveLastConfirmationOneLiner({
        telegramUserId: input.telegramUserId,
        oneLiner,
      });
    } else {
      await this.jobsRepository.saveLastConfirmationOneLiner({
        managerTelegramUserId: input.telegramUserId,
        oneLiner,
      });
    }
    return oneLiner;
  }

  private async generateOneLiner(input: {
    prompt: string;
    promptName: string;
    schemaHint: string;
  }): Promise<string | null> {
    const safe = await callJsonPromptSafe<OneLinerPayload>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt: input.prompt,
      maxTokens: 120,
      promptName: input.promptName,
      schemaHint: input.schemaHint,
    });
    if (!safe.ok) {
      this.logger.warn("One-liner generation failed", {
        promptName: input.promptName,
        errorCode: safe.error_code,
      });
      return null;
    }

    const line = normalizeOneLiner(safe.data.one_liner);
    if (!line) {
      return null;
    }
    return line;
  }
}

function normalizeOneLiner(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const collapsed = value.replace(/\s+/g, " ").trim();
  if (!collapsed) {
    return null;
  }
  const sentence = extractFirstSentence(collapsed);
  return sentence.slice(0, 280);
}

function extractFirstSentence(text: string): string {
  const match = text.match(/^(.+?[.!?])(?:\s|$)/);
  if (match?.[1]) {
    return match[1].trim();
  }
  return text.endsWith(".") ? text : `${text}.`;
}
