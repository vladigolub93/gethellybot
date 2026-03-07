import { Logger } from "../../config/logger";
import { JobsRepository } from "../../db/repositories/jobs.repo";
import { ProfilesRepository } from "../../db/repositories/profiles.repo";
import { UsersRepository } from "../../db/repositories/users.repo";
import { UserSessionState } from "../../shared/types/state.types";

interface CachedContext {
  expiresAt: number;
  knownUserName: string | null;
  routerContext: string;
}

interface UserRagContext {
  knownUserName: string | null;
  ragContext: string;
}

const CACHE_TTL_MS = 45_000;
const MAX_CONTEXT_LENGTH = 2_500;

export class UserRagContextService {
  private readonly cache = new Map<number, CachedContext>();

  constructor(
    private readonly usersRepository: UsersRepository,
    private readonly profilesRepository: ProfilesRepository,
    private readonly jobsRepository: JobsRepository,
    private readonly logger: Logger,
  ) {}

  invalidate(userId: number): void {
    this.cache.delete(userId);
  }

  async buildRouterContext(session: UserSessionState): Promise<UserRagContext> {
    const cached = this.cache.get(session.userId);
    if (cached && cached.expiresAt > Date.now()) {
      return {
        knownUserName: cached.knownUserName,
        ragContext: cached.routerContext,
      };
    }

    const baseContext = this.buildBaseContext(session);
    const dbContext = await this.buildDbContext(session);
    const merged = truncateContext([baseContext, dbContext.context].filter(Boolean).join("\n"));
    const knownUserName = resolveKnownUserName(session, dbContext.knownUserName);
    this.cache.set(session.userId, {
      expiresAt: Date.now() + CACHE_TTL_MS,
      knownUserName,
      routerContext: merged,
    });
    return {
      knownUserName,
      ragContext: merged,
    };
  }

  async buildInterviewContext(session: UserSessionState, currentQuestion: string): Promise<UserRagContext> {
    const router = await this.buildRouterContext(session);
    const recentAnswers = (session.answers ?? [])
      .slice(-3)
      .map((item) => item.answerText.trim())
      .filter(Boolean)
      .join(" | ");

    const interviewContext = truncateContext(
      [
        router.ragContext,
        `current_question=${currentQuestion}`,
        recentAnswers ? `recent_answers=${recentAnswers}` : "",
      ]
        .filter(Boolean)
        .join("\n"),
    );

    return {
      knownUserName: router.knownUserName,
      ragContext: interviewContext,
    };
  }

  private buildBaseContext(session: UserSessionState): string {
    const parts: string[] = [];
    parts.push(`state=${session.state}`);
    parts.push(`role=${session.role ?? "unknown"}`);
    if (session.interviewPlan) {
      parts.push(`plan_questions=${session.interviewPlan.questions.length}`);
      if (typeof session.currentQuestionIndex === "number") {
        parts.push(`current_question_index=${session.currentQuestionIndex}`);
      }
    }
    if (session.candidateProfileComplete) {
      parts.push("candidate_profile_complete=true");
    }
    if (session.jobProfileComplete) {
      parts.push("job_profile_complete=true");
    }
    if (session.preferredLanguage) {
      parts.push(`preferred_language=${session.preferredLanguage}`);
    }
    return parts.join("\n");
  }

  private async buildDbContext(
    session: UserSessionState,
  ): Promise<{ knownUserName: string | null; context: string }> {
    const parts: string[] = [];
    let knownUserName: string | null = null;

    try {
      const contact = await this.usersRepository.getContact(session.userId);
      if (contact?.firstName) {
        knownUserName = contact.firstName.trim();
        parts.push(`known_name=${knownUserName}`);
      }
    } catch (error) {
      this.logger.debug("user.rag.contact_lookup_failed", {
        userId: session.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    if (session.role === "candidate" || session.state === "waiting_resume" || session.state === "extracting_resume") {
      try {
        const analysis = await this.profilesRepository.getCandidateResumeAnalysis(session.userId);
        if (analysis && analysis.is_technical) {
          parts.push(`candidate_direction=${analysis.primary_direction}`);
          parts.push(`candidate_seniority=${analysis.seniority_estimate}`);
          const topSkills = analysis.skill_depth_classification?.deep_experience?.slice(0, 6) ?? [];
          if (topSkills.length > 0) {
            parts.push(`candidate_top_skills=${topSkills.join(", ")}`);
          }
        }
      } catch (error) {
        this.logger.debug("user.rag.candidate_analysis_lookup_failed", {
          userId: session.userId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    if (session.role === "manager" || session.state === "waiting_job" || session.state === "extracting_job") {
      try {
        const analysis = await this.jobsRepository.getJobDescriptionAnalysis(session.userId);
        if (analysis && analysis.is_technical_role) {
          const roleTitle = analysis.role_title_guess?.trim();
          if (roleTitle) {
            parts.push(`job_role_title=${roleTitle}`);
          }
          const coreTech = analysis.technology_signal_map?.likely_core?.slice(0, 6) ?? [];
          if (coreTech.length > 0) {
            parts.push(`job_core_tech=${coreTech.join(", ")}`);
          }
          const missing = analysis.missing_critical_information?.slice(0, 4) ?? [];
          if (missing.length > 0) {
            parts.push(`job_missing_info=${missing.join(" | ")}`);
          }
        }
      } catch (error) {
        this.logger.debug("user.rag.job_analysis_lookup_failed", {
          userId: session.userId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    return {
      knownUserName,
      context: parts.join("\n"),
    };
  }
}

function truncateContext(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) {
    return "";
  }
  if (trimmed.length <= MAX_CONTEXT_LENGTH) {
    return trimmed;
  }
  return `${trimmed.slice(0, MAX_CONTEXT_LENGTH - 3)}...`;
}

function resolveKnownUserName(session: UserSessionState, fromDb: string | null): string | null {
  if (fromDb && fromDb.trim()) {
    return fromDb.trim();
  }
  if (session.contactFirstName?.trim()) {
    return session.contactFirstName.trim();
  }
  if (session.username?.trim()) {
    return session.username.trim();
  }
  return null;
}
