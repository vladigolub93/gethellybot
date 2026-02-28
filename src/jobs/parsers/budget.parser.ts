import { JobBudgetCurrency, JobBudgetPeriod } from "../../shared/types/state.types";

export interface ParsedBudget {
  min: number | null;
  max: number | null;
  currency: JobBudgetCurrency | null;
  period: JobBudgetPeriod | null;
  isValid: boolean;
  currencyMissing: boolean;
  periodMissing: boolean;
}

export function parseBudget(textEnglish: string): ParsedBudget {
  const raw = textEnglish.trim();
  if (!raw) {
    return invalidBudget();
  }

  const normalized = raw.toLowerCase();
  const amounts = extractAmounts(normalized);
  if (amounts.length === 0) {
    return invalidBudget();
  }

  const min = Math.min(...amounts);
  const max = Math.max(...amounts);
  const currency = parseCurrency(normalized);
  const period = parsePeriod(normalized);

  const usOriented =
    normalized.includes("us") ||
    normalized.includes("usa") ||
    normalized.includes("united states") ||
    normalized.includes("american");
  const inferredCurrency = currency ?? (usOriented ? "USD" : null);

  const currencyMissing = inferredCurrency === null;
  const periodMissing = period === null;

  return {
    min,
    max,
    currency: inferredCurrency,
    period,
    isValid: !currencyMissing && !periodMissing,
    currencyMissing,
    periodMissing,
  };
}

function extractAmounts(text: string): number[] {
  const results: number[] = [];
  const regex = /(\d+(?:[.,]\d+)?)(\s*[k])?/gi;
  for (const match of text.matchAll(regex)) {
    const numeric = Number((match[1] ?? "").replace(",", "."));
    if (!Number.isFinite(numeric) || numeric <= 0) {
      continue;
    }
    const value = match[2] ? Math.round(numeric * 1000) : Math.round(numeric);
    results.push(value);
    if (results.length >= 2) {
      break;
    }
  }
  return results;
}

function parseCurrency(text: string): JobBudgetCurrency | null {
  if (/\busd\b/.test(text) || /\$/.test(text)) {
    return "USD";
  }
  if (/\beur\b/.test(text) || /€/.test(text)) {
    return "EUR";
  }
  if (/\bils\b/.test(text) || /₪/.test(text)) {
    return "ILS";
  }
  if (/\bgbp\b/.test(text) || /£/.test(text)) {
    return "GBP";
  }
  if (/\bother\b/.test(text)) {
    return "other";
  }
  return null;
}

function parsePeriod(text: string): JobBudgetPeriod | null {
  if (
    /\bper\s+month\b/.test(text) ||
    /\bmonthly\b/.test(text) ||
    /\/\s*month\b/.test(text) ||
    /\bmonth\b/.test(text)
  ) {
    return "month";
  }
  if (
    /\bper\s+year\b/.test(text) ||
    /\byearly\b/.test(text) ||
    /\bannually\b/.test(text) ||
    /\/\s*year\b/.test(text) ||
    /\byear\b/.test(text)
  ) {
    return "year";
  }
  return null;
}

function invalidBudget(): ParsedBudget {
  return {
    min: null,
    max: null,
    currency: null,
    period: null,
    isValid: false,
    currencyMissing: true,
    periodMissing: true,
  };
}
