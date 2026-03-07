import assert from "node:assert/strict";
import {
  NormalizationService,
  detectLanguageQuick,
  parseNormalizationResult,
} from "../../i18n/normalization.service";

async function run(): Promise<void> {
  const ruService = new NormalizationService({
    async generateStructuredJson() {
      return JSON.stringify({
        detected_language: "ru",
        needs_translation: true,
        english_text: "I have 5 years of Node.js experience.",
      });
    },
  });
  const ru = await ruService.normalizeToEnglish("У меня 5 лет опыта с Node.js.");
  assert.equal(ru.detected_language, "ru");
  assert.equal(ru.english_text, "I have 5 years of Node.js experience.");

  const ukService = new NormalizationService({
    async generateStructuredJson() {
      return JSON.stringify({
        detected_language: "uk",
        needs_translation: true,
        english_text: "I built microservices in Go and PostgreSQL.",
      });
    },
  });
  const uk = await ukService.normalizeToEnglish("Я будував мікросервіси на Go та PostgreSQL.");
  assert.equal(uk.detected_language, "uk");
  assert.equal(uk.english_text, "I built microservices in Go and PostgreSQL.");

  const mixed = parseNormalizationResult(
    JSON.stringify({
      detected_language: "ru",
      needs_translation: true,
      english_text: "I led CI/CD for AWS and improved SLO.",
    }),
    "Вел CI/CD в AWS и улучшил SLO.",
  );
  assert.equal(mixed.detected_language, "ru");
  assert.match(mixed.english_text, /\bCI\/CD\b/);
  assert.match(mixed.english_text, /\bAWS\b/);
  assert.match(mixed.english_text, /\bSLO\b/);

  const englishSource = "I designed Kafka pipelines for real-time analytics.";
  const enService = new NormalizationService({
    async generateStructuredJson() {
      return JSON.stringify({
        detected_language: "en",
        needs_translation: false,
        english_text: englishSource,
      });
    },
  });
  const en = await enService.normalizeToEnglish(englishSource);
  assert.equal(en.detected_language, "en");
  assert.equal(en.english_text, englishSource);
  assert.equal(detectLanguageQuick(englishSource), "en");

  console.log("normalization.service smoke checks passed");
}

void run();
