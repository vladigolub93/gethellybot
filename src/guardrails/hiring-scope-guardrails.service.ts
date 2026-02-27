import { LlmClient } from "../ai/llm.client";
import { HIRING_SCOPE_GUARDRAILS_V1_PROMPT } from "../ai/prompts/guardrails/hiring-scope-guardrails.v1.prompt";
import { Logger } from "../config/logger";
import { QualityFlagsService } from "../qa/quality-flags.service";
import { HiringScopeGuardrailsDecisionV1 } from "../shared/types/guardrails.types";
import { UserRole, UserState } from "../shared/types/state.types";

export class HiringScopeGuardrailsService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
    private readonly qualityFlagsService?: QualityFlagsService,
  ) {}

  async evaluate(input: {
    userMessage: string;
    userRole: UserRole | undefined;
    currentState: UserState;
    userId: number;
  }): Promise<HiringScopeGuardrailsDecisionV1> {
    const prompt = [
      HIRING_SCOPE_GUARDRAILS_V1_PROMPT,
      "",
      JSON.stringify(
        {
          user_message: input.userMessage,
          user_role: input.userRole ?? null,
          current_state: input.currentState,
        },
        null,
        2,
      ),
    ].join("\n");

    try {
      const raw = await this.llmClient.generateStructuredJson(prompt, 240, {
        promptName: "hiring_scope_guardrails_v1",
      });
      const parsed = parseDecision(raw);
      this.logger.info("Guardrails decision generated", {
        userId: input.userId,
        allowed: parsed.allowed,
        responseStyle: parsed.response_style,
        action: parsed.action,
      });
      return parsed;
    } catch (error) {
      this.logger.warn("Guardrails parsing failed, defaulting to safe redirect", {
        userId: input.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      await this.qualityFlagsService?.raise({
        entityType: "candidate",
        entityId: String(input.userId),
        flag: "guardrails_parse_failed",
        details: {
          state: input.currentState,
        },
      });
      return {
        allowed: false,
        response_style: "redirect",
        safe_reply: "I can help with hiring tasks. Please continue with your interview or recruitment request.",
        action: "request_more_hiring_context",
      };
    }
  }
}

function parseDecision(raw: string): HiringScopeGuardrailsDecisionV1 {
  const parsed = parseJsonObject(raw);

  if (typeof parsed.allowed !== "boolean") {
    throw new Error("Guardrails output invalid allowed field.");
  }

  const responseStyle = toText(parsed.response_style).toLowerCase();
  if (responseStyle !== "normal" && responseStyle !== "redirect" && responseStyle !== "refuse") {
    throw new Error("Guardrails output invalid response_style.");
  }

  const action = toText(parsed.action).toLowerCase();
  if (
    action !== "none" &&
    action !== "request_more_hiring_context" &&
    action !== "privacy_block" &&
    action !== "data_deletion_request"
  ) {
    throw new Error("Guardrails output invalid action.");
  }

  const safeReply = toText(parsed.safe_reply);
  if (!safeReply) {
    throw new Error("Guardrails output missing safe_reply.");
  }

  return {
    allowed: parsed.allowed,
    response_style: responseStyle,
    safe_reply: safeReply,
    action,
  };
}

function parseJsonObject(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Guardrails output is not valid JSON.");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
