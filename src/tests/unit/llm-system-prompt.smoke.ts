import assert from "node:assert/strict";
import { LlmClient } from "../../ai/llm.client";
import { Logger } from "../../config/logger";
import { HELLY_SYSTEM_PROMPT } from "../../ai/system/helly.system";

const noopLogger: Logger = {
  debug() {},
  info() {},
  warn() {},
  error() {},
};

function main(): void {
  const client = new LlmClient("test-key", noopLogger, "gpt-test");
  const payload = client.buildJsonRequestBody("{}", 123);

  assert.equal(payload.messages[0]?.role, "system");
  assert.equal(payload.messages[0]?.content, HELLY_SYSTEM_PROMPT);
  assert.equal(payload.messages[1]?.role, "user");

  process.stdout.write("OK, HELLY_SYSTEM_PROMPT is attached to LLM payload.\n");
}

main();
