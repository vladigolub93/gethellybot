export function welcomeMessage(): string {
  return [
    "Hi, I am Helly.",
    "",
    "I help technical candidates find the right roles and help hiring managers find the right engineers.",
    "",
    "Choose your role to begin.",
  ].join("\n");
}

export function candidateResumePrompt(): string {
  return "Please upload your resume as a PDF or DOCX file to continue.";
}

export function managerJobPrompt(): string {
  return "Please upload the job description as a PDF or DOCX file to continue.";
}

export function onboardingLearnHowItWorksMessage(): string {
  return [
    "For candidates:",
    "You upload your resume, I ask a few smart technical questions, then I match you with relevant roles.",
    "",
    "For hiring managers:",
    "You upload a job description, I clarify real requirements, then I find suitable candidates.",
  ].join("\n");
}

export function candidateOnboardingMessage(): string {
  return [
    "Thanks for choosing to get started.",
    "",
    "Finding the right role is not just about keywords.",
    "I will ask a few focused questions to better understand your real experience and strengths.",
    "",
    "You can answer in text or by sending a voice message.",
    "Take your time and be specific.",
    "",
    "Your profile will only be shared with a hiring manager if you decide to apply.",
  ].join("\n");
}

export function managerOnboardingMessage(): string {
  return [
    "Thanks for getting started.",
    "",
    "Job descriptions are often incomplete.",
    "I will ask a few clarification questions to understand the real product, challenges, and expectations.",
    "",
    "The more concrete your answers, the better the matching will be.",
  ].join("\n");
}

export function onboardingPrivacyNoteMessage(): string {
  return [
    "Your data is stored securely and used only for matching within this platform.",
    "You can request deletion at any time.",
  ].join("\n");
}

export function candidateInterviewPreparationMessage(): string {
  return [
    "I want to understand your real experience, not just what is written in the resume.",
    "",
    "There are no trick questions.",
    "Please be detailed and concrete.",
  ].join("\n");
}

export function managerInterviewPreparationMessage(): string {
  return [
    "I want to understand the real needs behind this role.",
    "",
    "Clear context helps avoid mismatches later.",
  ].join("\n");
}

export function interviewOngoingReminderMessage(): string {
  return [
    "We are currently in the interview step.",
    "Please answer the question above to continue.",
  ].join("\n");
}

export function firstMatchExplanationMessage(): string {
  return [
    "I found a role that may align with your experience.",
    "Take a look and decide if it feels relevant.",
  ].join("\n");
}

export function firstManagerMatchExplanationMessage(): string {
  return "A candidate aligned with your role requirements has shown interest.";
}

export function processingDocumentMessage(): string {
  return "Document received. Extracting text and preparing interview questions...";
}

export function questionMessage(questionIndex: number, questionText: string): string {
  return `Question ${questionIndex + 1}:\n${questionText}`;
}

export function interviewAlreadyStartedMessage(): string {
  return "Interview is already in progress. Please answer the current question.";
}

export function documentUploadNotAllowedMessage(): string {
  return "Document upload is allowed only when waiting for resume or job description. Use /start if needed.";
}

export function textOnlyReplyMessage(): string {
  return "Please reply with text.";
}

export function transcribingVoiceMessage(): string {
  return "Transcribing voice message...";
}

export function transcriptionFailedMessage(): string {
  return "Voice transcription failed. Please reply with text or resend a shorter voice message.";
}

export function voiceTooLongMessage(maxDurationSec: number): string {
  return `Voice message is too long. Please send up to ${maxDurationSec} seconds or split into parts.`;
}

export function candidateInterviewCompletedMessage(): string {
  return "Thank you. Your interview is complete. We will review your information next.\n\nYou can /start to run another interview.";
}

export function managerInterviewCompletedMessage(): string {
  return "Thank you. Your hiring intake is complete. We will proceed with the next matching step.\n\nYou can /start to run another interview.";
}

export function interviewSummaryUnavailableMessage(): string {
  return "Interview completed. Summary is temporarily unavailable. You can /start to run another interview.";
}

export function missingInterviewContextMessage(): string {
  return "Interview context is missing. Please /start and upload your document again.";
}

export function unsupportedInputMessage(): string {
  return "I could not process that in the current step. Use /start to restart.";
}

export function profileUnavailableMessage(): string {
  return "Profile is not ready yet. Continue interview or upload your document first.";
}

export function candidateOpportunityMessage(params: {
  score: number;
  jobSummary: string;
  explanationMessage: string;
  jobTechnicalSummary?: {
    headline: string;
    product_context: string;
    core_tech: string[];
  } | null;
}): string {
  const displayScore = params.score > 1 ? Math.round(params.score) : Math.round(params.score * 100);
  const summary = params.jobTechnicalSummary;
  const coreTech = summary?.core_tech?.length ? summary.core_tech.slice(0, 6).join(", ") : "unknown";
  return [
    "New opportunity matching your profile",
    "",
    `Match score: ${displayScore}%`,
    `Role: ${summary?.headline || params.jobSummary}`,
    `Product: ${summary?.product_context || "unknown"}`,
    `Core tech: ${coreTech}`,
    params.explanationMessage,
  ].join("\n");
}

export function managerCandidateAppliedMessage(params: {
  candidateUserId: number;
  score: number;
  candidateSummary: string;
  candidateTechnicalSummary?: {
    headline: string;
    technical_depth_summary: string;
    ownership_and_authority: string;
    risk_flags: string[];
    interview_confidence_level: "low" | "medium" | "high";
  } | null;
  explanationMessage: string;
}): string {
  const displayScore = params.score > 1 ? Math.round(params.score) : Math.round(params.score * 100);
  const technicalSummary = params.candidateTechnicalSummary;
  const riskFlags =
    technicalSummary && technicalSummary.risk_flags.length > 0
      ? technicalSummary.risk_flags.slice(0, 3).join("; ")
      : "None reported";

  return [
    "Candidate applied to your role",
    "",
    `Candidate: #${params.candidateUserId}`,
    `Score: ${displayScore}%`,
    `Headline: ${technicalSummary?.headline || "Not available"}`,
    `Technical depth: ${technicalSummary?.technical_depth_summary || params.candidateSummary}`,
    `Ownership: ${technicalSummary?.ownership_and_authority || "Not available"}`,
    `Risk flags: ${riskFlags}`,
    `Interview confidence: ${technicalSummary?.interview_confidence_level || "medium"}`,
    params.explanationMessage,
  ].join("\n");
}

export function candidateAppliedAcknowledgement(): string {
  return "Application sent to hiring manager.";
}

export function candidateRejectedAcknowledgement(): string {
  return "No problem.\nI will keep looking for roles that better match your experience.";
}

export function managerRejectedAcknowledgement(): string {
  return "Understood.\nI will continue searching for stronger alignment.";
}

export function managerAcceptedAcknowledgement(): string {
  return "Candidate accepted. Contacts were shared.";
}

export function askQuestionNotImplementedMessage(): string {
  return "Ask question flow is not implemented yet in MVP.";
}

export function candidateManagerRejectedMessage(): string {
  return "Hiring manager rejected your application for this role.";
}

export function contactsSharedToCandidateMessage(managerUsername: string): string {
  return `Mutual interest confirmed. Contact hiring manager: ${managerUsername}.`;
}

export function contactsSharedToManagerMessage(candidateUsername: string): string {
  return `Mutual interest confirmed. Contact candidate: ${candidateUsername}.`;
}
