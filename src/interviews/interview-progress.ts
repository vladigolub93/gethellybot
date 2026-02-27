import { InterviewPlan } from "../shared/types/domain.types";
import { InterviewAnswer } from "../shared/types/state.types";

export function getNextQuestionIndex(
  plan: InterviewPlan,
  answers: ReadonlyArray<InterviewAnswer>,
): number | null {
  const answeredIndexes = new Set(answers.map((item) => item.questionIndex));

  for (let index = 0; index < plan.questions.length; index += 1) {
    if (!answeredIndexes.has(index)) {
      return index;
    }
  }

  return null;
}

export function isInterviewComplete(
  plan: InterviewPlan,
  answers: ReadonlyArray<InterviewAnswer>,
): boolean {
  return getNextQuestionIndex(plan, answers) === null;
}
