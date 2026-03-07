export interface ParsedCountries {
  worldwide: boolean;
  countries: string[];
  isValid: boolean;
}

export function parseCountries(textEnglish: string): ParsedCountries {
  const raw = textEnglish.trim();
  if (!raw) {
    return {
      worldwide: false,
      countries: [],
      isValid: false,
    };
  }

  const lower = raw.toLowerCase();
  if (
    lower.includes("worldwide") ||
    lower.includes("global") ||
    lower === "any country"
  ) {
    return {
      worldwide: true,
      countries: [],
      isValid: true,
    };
  }

  const tokens = raw
    .split(/[,\n;]+/)
    .map((token) => token.trim())
    .filter(Boolean);

  const deduped = Array.from(
    new Map(tokens.map((country) => [country.toLowerCase(), country])).values(),
  );

  return {
    worldwide: false,
    countries: deduped,
    isValid: deduped.length > 0,
  };
}
