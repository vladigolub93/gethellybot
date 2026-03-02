/**
 * Stage 10: Composes a single match card (title + body) via LLM v3 prompt.
 * Buttons (Apply/Reject or Accept/Reject) are added by the caller with matchId.
 */

import { callJsonPromptSafe } from "../ai/llm.safe";
import {
  buildMatchCardComposeV3Prompt,
  MatchCardComposeV3InputCandidate,
  MatchCardComposeV3InputManager,
} from "../ai/prompts/matching/match_card_compose_v3.prompt";
import { isMatchCardComposeV3OutputSchema } from "../ai/schemas/llm-json-schemas";
import { Logger } from "../config/logger";
import { MatchRecord } from "../decisions/match.types";
import { LlmClient } from "../ai/llm.client";

export type CardLanguage = "en" | "ru" | "uk";

export interface MatchCardComposerResult {
  text: string;
  title?: string;
}

export class MatchCardComposerService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async composeForCandidate(
    match: MatchRecord,
    language: CardLanguage,
  ): Promise<MatchCardComposerResult> {
    const job = match.jobTechnicalSummary;
    const input: MatchCardComposeV3InputCandidate = {
      role: "candidate",
      language,
      jobSummary: match.jobSummary,
      headline: job?.headline ?? null,
      coreTech: job?.core_tech ?? [],
      mustHaves: job?.key_requirements ?? [],
      domain: job?.domain_need && job.domain_need !== "none" ? String(job.domain_need) : null,
      workFormat: null,
      allowedCountries: [],
      budget: null,
      whyMatched: match.explanationJson?.message_for_candidate ?? match.explanation,
    };

    return this.compose(input, () => fallbackCandidateCard(match));
  }

  async composeForManager(
    match: MatchRecord,
    language: CardLanguage,
  ): Promise<MatchCardComposerResult> {
    const cand = match.candidateTechnicalSummary;
    const input: MatchCardComposeV3InputManager = {
      role: "manager",
      language,
      candidateSummary: match.candidateSummary,
      roleSeniority: cand?.headline ?? null,
      yearsExperience: null,
      coreStack: cand ? [cand.technical_depth_summary].filter(Boolean) : [],
      domains: cand?.domain_expertise ? [cand.domain_expertise] : [],
      location: null,
      workPreference: null,
      salaryExpectation: null,
      whyMatched: match.explanationJson?.message_for_manager ?? match.explanation,
    };

    return this.compose(input, () => fallbackManagerCard(match));
  }

  private async compose(
    input: MatchCardComposeV3InputCandidate | MatchCardComposeV3InputManager,
    fallback: () => string,
  ): Promise<MatchCardComposerResult> {
    const prompt = buildMatchCardComposeV3Prompt(input);
    const result = await callJsonPromptSafe({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 600,
      promptName: "match_card_compose_v3",
      schemaHint: "title, body, keyFacts",
      timeoutMs: 15_000,
      validate: isMatchCardComposeV3OutputSchema,
    });

    if (!result.ok) {
      this.logger.warn("match_card_compose_v3 failed, using fallback", {
        error_code: result.error_code,
        role: input.role,
      });
      return { text: fallback() };
    }

    const body = result.data.body.slice(0, 800);
    const title = result.data.title?.trim();
    const text = title ? `${title}\n\n${body}` : body;
    return { text, title: result.data.title };
  }
}

function fallbackCandidateCard(match: MatchRecord): string {
  const job = match.jobTechnicalSummary;
  const headline = job?.headline ?? "Role";
  const why = match.explanationJson?.message_for_candidate ?? match.explanation;
  return `${headline}\n\n${match.jobSummary.slice(0, 400)}${match.jobSummary.length > 400 ? "…" : ""}\n\nWhy matched: ${why}`;
}

function fallbackManagerCard(match: MatchRecord): string {
  const cand = match.candidateTechnicalSummary;
  const headline = cand?.headline ?? "Candidate";
  const why = match.explanationJson?.message_for_manager ?? match.explanation;
  return `${headline}\n\n${match.candidateSummary.slice(0, 400)}${match.candidateSummary.length > 400 ? "…" : ""}\n\nWhy matched: ${why}`;
}
