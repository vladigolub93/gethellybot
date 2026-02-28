import { CandidateSalaryCurrency, CandidateSalaryPeriod } from "../../shared/types/state.types";

export interface ParsedSalary {
  amount: number | null;
  currency: CandidateSalaryCurrency | null;
  period: CandidateSalaryPeriod | null;
  isValid: boolean;
  currencyMissing: boolean;
  periodMissing: boolean;
}

export function parseSalary(textEnglish: string): ParsedSalary {
  const raw = textEnglish.trim();
  if (!raw) {
    return invalid();
  }

  const amountMatch = raw.match(/(\d+(?:[.,]\d+)?)(\s*[kK])?/);
  if (!amountMatch) {
    return invalid();
  }

  const numeric = Number(amountMatch[1].replace(",", "."));
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return invalid();
  }

  const amount = amountMatch[2] ? Math.round(numeric * 1000) : Math.round(numeric);
  const lower = raw.toLowerCase();
  const currency = parseCurrency(lower);
  const period = parsePeriod(lower);

  const periodMissing = period === null;
  const currencyMissing = currency === null;
  const finalCurrency: CandidateSalaryCurrency = currency ?? "USD";

  return {
    amount,
    currency: finalCurrency,
    period,
    isValid: !periodMissing,
    currencyMissing,
    periodMissing,
  };
}

function parseCurrency(lower: string): CandidateSalaryCurrency | null {
  if (/\busd\b/.test(lower) || /\$/.test(lower)) {
    return "USD";
  }
  if (/\beur\b/.test(lower) || /€/.test(lower)) {
    return "EUR";
  }
  if (/\bils\b/.test(lower) || /₪/.test(lower)) {
    return "ILS";
  }
  if (/\bgbp\b/.test(lower) || /£/.test(lower)) {
    return "GBP";
  }
  if (/\bother\b/.test(lower)) {
    return "other";
  }
  return null;
}

function parsePeriod(lower: string): CandidateSalaryPeriod | null {
  if (
    /\bper\s+month\b/.test(lower) ||
    /\bmonthly\b/.test(lower) ||
    /\/\s*month\b/.test(lower) ||
    /\bmonth\b/.test(lower)
  ) {
    return "month";
  }
  if (
    /\bper\s+year\b/.test(lower) ||
    /\byearly\b/.test(lower) ||
    /\bannually\b/.test(lower) ||
    /\/\s*year\b/.test(lower) ||
    /\byear\b/.test(lower)
  ) {
    return "year";
  }
  return null;
}

function invalid(): ParsedSalary {
  return {
    amount: null,
    currency: null,
    period: null,
    isValid: false,
    currencyMissing: false,
    periodMissing: true,
  };
}
