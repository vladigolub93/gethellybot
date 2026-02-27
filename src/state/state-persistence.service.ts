import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { Logger } from "../config/logger";
import { StatesRepository } from "../db/repositories/states.repo";
import { UsersRepository } from "../db/repositories/users.repo";
import { UserSessionState } from "../shared/types/state.types";

const STORAGE_DIR = path.resolve(process.cwd(), "data", "state");
const STORAGE_FILE = path.join(STORAGE_DIR, "sessions.json");

export class StatePersistenceService {
  private readonly cache = new Map<number, UserSessionState>();
  private initialized = false;

  constructor(
    private readonly logger: Logger,
    private readonly usersRepository: UsersRepository,
    private readonly statesRepository: StatesRepository,
  ) {}

  async hydrateSession(
    userId: number,
    chatId: number,
    username?: string,
  ): Promise<UserSessionState | null> {
    await this.ensureInitialized();

    const fromCache = this.cache.get(userId);
    if (fromCache) {
      const merged = {
        ...fromCache,
        chatId,
        username: username ?? fromCache.username,
      };
      this.cache.set(userId, merged);
      return deepClone(merged);
    }

    try {
      const remote = await this.statesRepository.loadByTelegramUserId(userId);
      if (!remote) {
        return null;
      }

      const merged = {
        ...remote,
        chatId,
        username: username ?? remote.username,
      };
      this.cache.set(userId, merged);
      await this.flushCacheToDisk();
      return deepClone(merged);
    } catch (error) {
      this.logger.warn("Failed to hydrate session from Supabase, using local state", {
        userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return null;
    }
  }

  async persistSession(session: UserSessionState): Promise<void> {
    await this.ensureInitialized();
    const snapshot = deepClone(session);
    this.cache.set(session.userId, snapshot);
    await this.flushCacheToDisk();

    try {
      await this.usersRepository.upsertTelegramUser({
        telegramUserId: session.userId,
        telegramUsername: session.username,
        role: session.role,
        onboardingCompleted: session.onboardingCompleted,
        firstMatchExplained: session.firstMatchExplained,
      });
      await this.statesRepository.saveSession(snapshot);
    } catch (error) {
      this.logger.warn("Failed to persist session to Supabase, local cache is still saved", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }

  private async ensureInitialized(): Promise<void> {
    if (this.initialized) {
      return;
    }

    await mkdir(STORAGE_DIR, { recursive: true });
    try {
      const raw = await readFile(STORAGE_FILE, "utf-8");
      const parsed = JSON.parse(raw) as UserSessionState[];
      if (Array.isArray(parsed)) {
        for (const session of parsed) {
          if (session && typeof session.userId === "number") {
            this.cache.set(session.userId, session);
          }
        }
      }
    } catch {
      // Ignore missing file / invalid JSON.
    }

    this.initialized = true;
  }

  private async flushCacheToDisk(): Promise<void> {
    const sessions = Array.from(this.cache.values());
    await writeFile(STORAGE_FILE, JSON.stringify(sessions, null, 2), "utf-8");
  }
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
