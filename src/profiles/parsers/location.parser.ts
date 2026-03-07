export interface ParsedCountryCity {
  country: string;
  city: string;
  isValid: boolean;
}

const KNOWN_COUNTRIES = new Set([
  "ukraine",
  "poland",
  "germany",
  "israel",
  "united states",
  "usa",
  "canada",
  "united kingdom",
  "uk",
  "spain",
  "portugal",
  "france",
  "italy",
  "netherlands",
  "sweden",
  "norway",
  "denmark",
  "estonia",
  "latvia",
  "lithuania",
  "romania",
  "czech republic",
  "slovakia",
  "hungary",
  "austria",
  "switzerland",
  "ireland",
  "turkey",
  "georgia",
  "armenia",
  "kazakhstan",
]);

export function parseCountryCity(textEnglish: string): ParsedCountryCity {
  const normalized = textEnglish
    .trim()
    .replace(/\s+/g, " ");
  if (!normalized) {
    return {
      country: "",
      city: "",
      isValid: false,
    };
  }

  const separatorMatch = normalized.match(/^(.+?)[,\-–]\s*(.+)$/);
  const parenMatch = normalized.match(/^(.+?)\s*\((.+)\)$/);
  let first = "";
  let second = "";
  if (separatorMatch) {
    first = separatorMatch[1].trim();
    second = separatorMatch[2].trim();
  } else if (parenMatch) {
    first = parenMatch[1].trim();
    second = parenMatch[2].trim();
  } else {
    return {
      country: "",
      city: "",
      isValid: false,
    };
  }

  if (first.split(/\s+/).length < 1 || second.split(/\s+/).length < 1) {
    return {
      country: "",
      city: "",
      isValid: false,
    };
  }

  let country = first;
  let city = second;
  if (KNOWN_COUNTRIES.has(second.toLowerCase()) && !KNOWN_COUNTRIES.has(first.toLowerCase())) {
    country = second;
    city = first;
  }

  if (country.length < 2 || city.length < 2) {
    return {
      country: "",
      city: "",
      isValid: false,
    };
  }

  return {
    country,
    city,
    isValid: true,
  };
}
