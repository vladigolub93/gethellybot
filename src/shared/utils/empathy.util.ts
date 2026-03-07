const EMPATHY_LINES = [
  "Understood.",
  "That makes sense.",
  "Thank you for the clarification.",
  "Got it.",
  "That is helpful context.",
] as const;

export function getShortEmpathyLine(previousLine?: string): string {
  const previous = previousLine?.trim();
  const candidates = EMPATHY_LINES.filter((line) => line !== previous);
  if (candidates.length === 0) {
    return EMPATHY_LINES[0];
  }
  const randomIndex = Math.floor(Math.random() * candidates.length);
  return candidates[randomIndex];
}
