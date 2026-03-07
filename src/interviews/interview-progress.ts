import { InterviewPlan } from "../shared/types/domain.types";
import { InterviewAnswer } from "../shared/types/state.types";

export function isFinalAnswer(answer: InterviewAnswer): boolean {
  return answer.status !== "draft";
}

export function getNextQuestionIndex(
  plan: InterviewPlan,
  answers: ReadonlyArray<InterviewAnswer>,
  skippedIndexes: ReadonlyArray<number> = [],
): number | null {
  const answeredIndexes = new Set(
    answers.filter((item) => isFinalAnswer(item)).map((item) => item.questionIndex),
  );
  const skipped = new Set(skippedIndexes);

  for (let index = 0; index < plan.questions.length; index += 1) {
    if (!answeredIndexes.has(index) && !skipped.has(index)) {
      return index;
    }
  }

  return null;
}

export function isInterviewComplete(
  plan: InterviewPlan,
  answers: ReadonlyArray<InterviewAnswer>,
  skippedIndexes: ReadonlyArray<number> = [],
): boolean {
  return getNextQuestionIndex(plan, answers, skippedIndexes) === null;
}
