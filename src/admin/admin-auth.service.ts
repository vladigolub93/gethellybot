import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export interface TelegramWebappIdentity {
  telegramUserId: number;
  username?: string;
  firstName?: string;
  lastName?: string;
}

export interface VerifyInitDataResult {
  ok: boolean;
  error?: string;
  identity?: TelegramWebappIdentity;
}

export interface AdminSessionPayload {
  sub: "admin";
  telegramUserId?: number;
  username?: string;
  iat: number;
  exp: number;
  nonce: string;
}

export function verifyTelegramInitData(
  initData: string,
  botToken: string,
  maxAgeSeconds = 86_400,
): VerifyInitDataResult {
  if (!initData || !initData.trim()) {
    return { ok: false, error: "missing_init_data" };
  }

  const params = new URLSearchParams(initData);
  const providedHash = params.get("hash");
  if (!providedHash) {
    return { ok: false, error: "missing_hash" };
  }

  const authDateRaw = params.get("auth_date");
  const authDate = authDateRaw ? Number(authDateRaw) : NaN;
  if (!Number.isFinite(authDate)) {
    return { ok: false, error: "invalid_auth_date" };
  }

  const now = Math.floor(Date.now() / 1000);
  if (now - authDate > maxAgeSeconds) {
    return { ok: false, error: "auth_date_expired" };
  }

  const dataCheckString = Array.from(params.entries())
    .filter(([key]) => key !== "hash")
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");

  const secretKey = createHmac("sha256", "WebAppData")
    .update(botToken)
    .digest();
  const expectedHash = createHmac("sha256", secretKey)
    .update(dataCheckString)
    .digest("hex");

  if (!safeEqualHex(providedHash, expectedHash)) {
    return { ok: false, error: "invalid_hash" };
  }

  const userRaw = params.get("user");
  if (!userRaw) {
    return { ok: false, error: "missing_user" };
  }

  try {
    const user = JSON.parse(userRaw) as {
      id?: number;
      username?: string;
      first_name?: string;
      last_name?: string;
    };
    const userId = typeof user.id === "number" ? user.id : NaN;
    if (!Number.isInteger(userId) || userId <= 0) {
      return { ok: false, error: "invalid_user_id" };
    }

    return {
      ok: true,
      identity: {
        telegramUserId: userId,
        username: user.username,
        firstName: user.first_name,
        lastName: user.last_name,
      },
    };
  } catch {
    return { ok: false, error: "invalid_user_payload" };
  }
}

export function issueAdminSessionToken(input: {
  secret: string;
  ttlSeconds: number;
  telegramUserId?: number;
  username?: string;
}): string {
  const now = Math.floor(Date.now() / 1000);
  const payload: AdminSessionPayload = {
    sub: "admin",
    telegramUserId: input.telegramUserId,
    username: input.username,
    iat: now,
    exp: now + input.ttlSeconds,
    nonce: randomBytes(8).toString("hex"),
  };
  const header = { alg: "HS256", typ: "JWT" };
  const headerB64 = toBase64Url(JSON.stringify(header));
  const payloadB64 = toBase64Url(JSON.stringify(payload));
  const data = `${headerB64}.${payloadB64}`;
  const signature = createHmac("sha256", input.secret).update(data).digest();
  const signatureB64 = toBase64Url(signature);
  return `${data}.${signatureB64}`;
}

export function verifyAdminSessionToken(token: string, secret: string): AdminSessionPayload | null {
  if (!token || typeof token !== "string") {
    return null;
  }
  const parts = token.split(".");
  if (parts.length !== 3) {
    return null;
  }

  const [headerB64, payloadB64, signatureB64] = parts;
  const data = `${headerB64}.${payloadB64}`;
  const expectedSig = createHmac("sha256", secret).update(data).digest();
  const providedSig = fromBase64Url(signatureB64);
  if (!providedSig || !safeEqualBuffer(providedSig, expectedSig)) {
    return null;
  }

  try {
    const payloadRaw = JSON.parse(Buffer.from(payloadB64, "base64url").toString("utf8")) as AdminSessionPayload;
    if (payloadRaw.sub !== "admin") {
      return null;
    }
    if (!Number.isInteger(payloadRaw.iat) || !Number.isInteger(payloadRaw.exp)) {
      return null;
    }
    const now = Math.floor(Date.now() / 1000);
    if (payloadRaw.exp <= now) {
      return null;
    }
    return payloadRaw;
  } catch {
    return null;
  }
}

export function extractCookie(headerValue: string | undefined, cookieName: string): string | null {
  if (!headerValue) {
    return null;
  }
  const parts = headerValue.split(";");
  for (const part of parts) {
    const [name, ...rest] = part.trim().split("=");
    if (name === cookieName) {
      return decodeURIComponent(rest.join("="));
    }
  }
  return null;
}

function safeEqualHex(a: string, b: string): boolean {
  const bufA = Buffer.from(a, "hex");
  const bufB = Buffer.from(b, "hex");
  if (bufA.length !== bufB.length) {
    return false;
  }
  return timingSafeEqual(bufA, bufB);
}

function safeEqualBuffer(a: Buffer, b: Buffer): boolean {
  if (a.length !== b.length) {
    return false;
  }
  return timingSafeEqual(a, b);
}

function toBase64Url(input: string | Buffer): string {
  return Buffer.from(input).toString("base64url");
}

function fromBase64Url(input: string): Buffer | null {
  try {
    return Buffer.from(input, "base64url");
  } catch {
    return null;
  }
}
