import { InterviewPlan, InterviewQuestion } from "../shared/types/domain.types";
import { UserRole } from "../shared/types/state.types";

export const MAX_INTERVIEW_QUESTIONS = 10;
export const MAX_CANDIDATE_INTERVIEW_QUESTIONS = 10;
export const MAX_MANAGER_INTERVIEW_QUESTIONS = 10;

export function fallbackQuestionByRole(role: UserRole): string {
  if (role === "candidate") {
    return "Can you briefly walk me through your background and recent experience?";
  }

  return "Can you describe the role you are hiring for and what problem this hire should solve?";
}

export function buildFallbackPlan(role: UserRole): InterviewPlan {
  return freezeInterviewPlan({
    summary: "Fallback interview plan was used.",
    questions: [
      {
        id: "q1",
        question: fallbackQuestionByRole(role),
        goal: "Collect essential context",
        gapToClarify: "No reliable interview plan from LLM",
      },
    ],
  });
}

export function validateAndFreezeInterviewPlan(role: UserRole, rawPlan: InterviewPlan): InterviewPlan {
  const normalizedSummary =
    typeof rawPlan.summary === "string" && rawPlan.summary.trim()
      ? rawPlan.summary.trim()
      : "Interview plan generated.";

  const normalizedQuestions = normalizeQuestions(
    rawPlan.questions,
    role === "candidate"
      ? MAX_CANDIDATE_INTERVIEW_QUESTIONS
      : MAX_MANAGER_INTERVIEW_QUESTIONS,
  );

  if (normalizedQuestions.length === 0) {
    return buildFallbackPlan(role);
  }

  return freezeInterviewPlan({
    summary: normalizedSummary,
    questions: normalizedQuestions,
  });
}

function normalizeQuestions(
  rawQuestions: ReadonlyArray<InterviewQuestion>,
  maxQuestions: number,
): InterviewQuestion[] {
  const source = Array.isArray(rawQuestions) ? rawQuestions : [];
  const valid = source
    .map((question, index) => normalizeQuestion(question, index))
    .filter((question): question is InterviewQuestion => Boolean(question));

  return valid.slice(0, maxQuestions);
}

function normalizeQuestion(rawQuestion: InterviewQuestion, index: number): InterviewQuestion | null {
  if (!rawQuestion || typeof rawQuestion.question !== "string") {
    return null;
  }

  const questionText = rawQuestion.question.trim();
  if (!questionText) {
    return null;
  }

  const id = typeof rawQuestion.id === "string" && rawQuestion.id.trim() ? rawQuestion.id : `q${index + 1}`;
  const goal = typeof rawQuestion.goal === "string" ? rawQuestion.goal.trim() : "";
  const gapToClarify =
    typeof rawQuestion.gapToClarify === "string" ? rawQuestion.gapToClarify.trim() : "";

  return {
    id,
    question: questionText,
    goal,
    gapToClarify,
  };
}

function freezeInterviewPlan(plan: InterviewPlan): InterviewPlan {
  const frozenQuestions = plan.questions.map((question) => Object.freeze({ ...question }));
  const frozenPlan = {
    summary: plan.summary,
    questions: Object.freeze(frozenQuestions),
  };

  return Object.freeze(frozenPlan);
}
