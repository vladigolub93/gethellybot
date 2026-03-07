import "dotenv/config";
import { LlmClient } from "../src/ai/llm.client";
import { createLogger } from "../src/config/logger";
import { AnswerEvaluatorService } from "../src/interviews/answer-evaluator.service";

async function run(): Promise<void> {
  const apiKey = process.env.OPENAI_API_KEY?.trim();
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is required for sanity:answer-evaluator");
  }

  const logger = createLogger();
  const llmClient = new LlmClient(apiKey, logger);
  const evaluator = new AnswerEvaluatorService(llmClient, logger);

  const genericEssayAnswer =
    "A robust architecture should include clear layers, scalability, and monitoring. We should always use best practices, resilient patterns, and clean modular code to ensure reliability and maintainability.";
  const detailedRealAnswer =
    "At Rocketpool I owned /api/reservations in Express. I wrote the transaction that inserts into reservations with unique constraint pool_id,row,col, and returns 409 on duplicate key. During a live incident p95 jumped to 1.2s because of missing index on pool_id,created_at. I added the index, p95 dropped to 180ms after deploy.";

  const genericResult = await evaluator.evaluateAnswer({
    role: "candidate",
    question: "Walk me through one real production incident you owned.",
    answer: genericEssayAnswer,
    preferredLanguage: "en",
  });
  const detailedResult = await evaluator.evaluateAnswer({
    role: "candidate",
    question: "Walk me through one real production incident you owned.",
    answer: detailedRealAnswer,
    preferredLanguage: "en",
  });

  console.log("Generic answer evaluation:", genericResult);
  console.log("Detailed answer evaluation:", detailedResult);

  if (!genericResult.should_request_reanswer) {
    throw new Error("Expected generic essay answer to require re-answer");
  }
  if (!detailedResult.should_accept) {
    throw new Error("Expected detailed real answer to be accepted");
  }

  console.log("answer-evaluator sanity passed");
}

run().catch((error) => {
  console.error("answer-evaluator sanity failed:", error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
