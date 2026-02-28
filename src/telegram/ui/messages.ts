export function welcomeMessage(): string {
  return [
    "Hi, I am Helly.",
    "",
    "I help technical candidates find the right roles and help hiring managers find the right engineers.",
  ].join("\n");
}

export function contactRequestMessage(): string {
  return [
    "Before we begin, please share your Telegram contact.",
    "This helps us connect you with the right person after mutual approval.",
    "Your contact is never shared unless both sides approve.",
    "Tap Share my contact below, or send your phone number in text, example +380991112233.",
    "If you want to continue now, tap or type Skip for now.",
  ].join("\n");
}

export function roleSelectionMessage(): string {
  return [
    "Choose your role to begin.",
    "You can tap a button below or type, I am a Candidate or I am Hiring.",
  ].join("\n");
}

export function contactSavedMessage(): string {
  return "Thanks, your contact is saved. You can continue now.";
}

export function contactSkippedMessage(): string {
  return "No problem, you can continue now. You can share contact later at any time.";
}

export function ownContactRequiredMessage(): string {
  return "Please share your own Telegram contact so I can verify consent correctly.";
}

export function candidateContactRequiredForExchangeMessage(): string {
  return [
    "To share your contact with the hiring manager, please send your phone number first.",
    "Example, +380991112233.",
  ].join("\n");
}

export function managerContactRequiredForExchangeMessage(): string {
  return [
    "To share your contact with the candidate, please send your phone number first.",
    "Example, +380991112233.",
  ].join("\n");
}

export function candidateResumePrompt(): string {
  return "Send your resume as a PDF or DOCX file, or paste the text here. You can also forward a file from another chat.";
}

export function managerJobPrompt(): string {
  return "Send the job description as a PDF or DOCX file, or paste the text here. You can also forward a file from another chat.";
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

export function interviewLanguageSupportMessage(): string {
  return "You can answer in Russian or Ukrainian, I will understand.";
}

export function candidateMandatoryIntroMessage(): string {
  return "Before I start matching, I need a few practical details to avoid mismatches.";
}

export function candidateMandatoryLocationQuestionMessage(): string {
  return [
    "Where are you currently located? Please include country and city.",
    "You can also share your Telegram location.",
  ].join("\n");
}

export function candidateMandatoryLocationRetryMessage(): string {
  return "Please reply with Country, City. Example: Ukraine, Dnipro.";
}

export function candidateMandatoryLocationPinReceivedMessage(): string {
  return "Location pin received. Please also type Country, City so I can store both fields.";
}

export function candidateMandatoryWorkModeQuestionMessage(): string {
  return "Are you looking for remote, hybrid, onsite, or flexible?";
}

export function candidateMandatoryWorkModeRetryMessage(): string {
  return "Please choose one option, remote, hybrid, onsite, or flexible.";
}

export function candidateMandatorySalaryQuestionMessage(): string {
  return [
    "What are your salary expectations? Please include amount, currency, and whether it is per month or per year.",
    "Example: 6500 USD per month.",
  ].join("\n");
}

export function candidateMandatorySalaryRetryMessage(): string {
  return "Please send salary as amount, currency, and period. Example: 6500 USD per month.";
}

export function candidateMandatorySalaryCurrencyConfirmMessage(input: {
  amount: number;
  period: "month" | "year";
}): string {
  return `I can save this as ${input.amount} USD per ${input.period}. Reply yes to confirm, or resend with currency.`;
}

export function candidateMandatoryCompletedMessage(): string {
  return "Great, details saved. Matching is now available.";
}

export function candidateMatchingBlockedByMandatoryMessage(): string {
  return "I can start matching after we fill the details above.";
}

export function candidateMatchingActionsReadyMessage(): string {
  return "You can run matching now. Use Find roles, Show matches, or Pause matching.";
}

export function managerMandatoryIntroMessage(): string {
  return "Before I start matching candidates, I need a few practical details to avoid mismatches.";
}

export function managerMandatoryWorkFormatQuestionMessage(): string {
  return "Is this role remote, hybrid, or onsite?";
}

export function managerMandatoryCountriesQuestionMessage(): string {
  return [
    "Which countries can you consider for this remote role?",
    "Reply with a list of countries, or say worldwide.",
  ].join("\n");
}

export function managerMandatoryCountriesRetryMessage(): string {
  return "Please reply with countries separated by commas, or say worldwide. Example: Israel, Poland.";
}

export function managerMandatoryBudgetQuestionMessage(): string {
  return [
    "What is the budget for this role?",
    "Please include a range if possible, currency, and whether it is per month or per year.",
    "Example: 8000 to 10000 USD per month.",
  ].join("\n");
}

export function managerMandatoryBudgetRetryMessage(): string {
  return "Please provide budget with amount or range, currency, and period. Example: 8000-10000 USD per month.";
}

export function managerMandatoryBudgetCurrencyRetryMessage(): string {
  return "Please include currency explicitly, for example USD, EUR, ILS, or GBP.";
}

export function managerMandatoryBudgetPeriodRetryMessage(): string {
  return "Please include period, per month or per year.";
}

export function managerMandatoryBudgetCurrencyConfirmMessage(input: {
  min: number;
  max: number;
  period: "month" | "year";
}): string {
  return `I can save this as ${input.min}-${input.max} USD per ${input.period}. Reply yes to confirm, or resend with currency.`;
}

export function managerMandatoryCompletedMessage(): string {
  return "Great, details saved. Matching is now available.";
}

export function managerMatchingBlockedByMandatoryMessage(): string {
  return "I can start matching after we fill the details above.";
}

export function managerMatchingActionsReadyMessage(): string {
  return "You can run matching now. Use Find candidates, Show matches, or Pause matching.";
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

export function stillProcessingDocumentMessage(): string {
  return "Still processing your document. I will send the next step as soon as it is ready.";
}

export function stillProcessingAnswerMessage(): string {
  return "Still processing your last answer. I will send the next step shortly.";
}

export function questionMessage(questionIndex: number, questionText: string): string {
  void questionIndex;
  return questionText.trim();
}

export function quickFollowUpMessage(followUpText: string): string {
  return `Quick follow up:\n${followUpText}`;
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

export function managerCandidateSuggestionMessage(params: {
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
    "Candidate match suggestion",
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

export function contactsSharedToCandidateMessage(managerContactDetails: string): string {
  return [
    "The hiring manager agreed to connect. Here are their details:",
    managerContactDetails,
  ].join("\n");
}

export function contactsSharedToManagerMessage(candidateContactDetails: string): string {
  return [
    "The candidate agreed to connect. Here are their details:",
    candidateContactDetails,
  ].join("\n");
}
