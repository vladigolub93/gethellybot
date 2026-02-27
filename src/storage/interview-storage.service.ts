import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { CandidateProfile, DocumentType, InterviewResultArtifact, JobProfile } from "../shared/types/domain.types";
import { InterviewAnswer, UserRole } from "../shared/types/state.types";
import { JobTechnicalSummaryV2 } from "../shared/types/job-profile.types";

export interface PersistedInterviewRecord {
  role: UserRole;
  telegramUserId: number;
  startedAt: string;
  completedAt: string;
  documentType: DocumentType;
  extractedText: string;
  planQuestions: ReadonlyArray<{ id: string; question: string }>;
  answers: ReadonlyArray<InterviewAnswer>;
  finalArtifact: InterviewResultArtifact | null;
  finalProfile?: CandidateProfile | JobProfile | null;
  managerTechnicalSummary?: JobTechnicalSummaryV2 | null;
  managerProfileUpdates?: ReadonlyArray<{
    field: string;
    previous_value: string;
    new_value: string;
    reason: string;
  }>;
  managerContradictionFlags?: ReadonlyArray<string>;
}

const STORAGE_DIR = path.resolve(process.cwd(), "data", "interviews");
const MAX_EXTRACTED_TEXT_LENGTH = 10000;

export class InterviewStorageService {
  async save(record: PersistedInterviewRecord): Promise<string> {
    await mkdir(STORAGE_DIR, { recursive: true });

    const rolePrefix = record.role === "candidate" ? "candidate" : "hiring";
    const timestamp = toFileTimestamp(record.completedAt);
    const fileName = `${rolePrefix}_${record.telegramUserId}_${timestamp}.json`;
    const filePath = path.join(STORAGE_DIR, fileName);

    const payload = {
      role: record.role,
      telegramUserId: record.telegramUserId,
      startedAt: record.startedAt,
      completedAt: record.completedAt,
      documentType: record.documentType,
      extractedText: trimExtractedText(record.extractedText),
      planQuestions: record.planQuestions,
      answers: record.answers,
      finalArtifact: record.finalArtifact,
      finalProfile: record.finalProfile ?? null,
      managerTechnicalSummary: record.managerTechnicalSummary ?? null,
      managerProfileUpdates: record.managerProfileUpdates ?? [],
      managerContradictionFlags: record.managerContradictionFlags ?? [],
    };

    await writeFile(filePath, JSON.stringify(payload, null, 2), "utf-8");
    return filePath;
  }

  async listByRole(role: UserRole): Promise<PersistedInterviewRecord[]> {
    await mkdir(STORAGE_DIR, { recursive: true });
    const entries = await readdir(STORAGE_DIR, { withFileTypes: true });
    const files = entries.filter((entry) => entry.isFile()).map((entry) => entry.name);
    const matchedFiles =
      role === "candidate"
        ? files.filter((fileName) => fileName.startsWith("candidate_") && fileName.endsWith(".json"))
        : files.filter((fileName) => fileName.startsWith("hiring_") && fileName.endsWith(".json"));

    const records: PersistedInterviewRecord[] = [];

    for (const fileName of matchedFiles) {
      const filePath = path.join(STORAGE_DIR, fileName);
      try {
        const raw = await readFile(filePath, "utf-8");
        const parsed = JSON.parse(raw) as PersistedInterviewRecord;
        records.push(parsed);
      } catch {
        continue;
      }
    }

    records.sort((a, b) => (a.completedAt < b.completedAt ? 1 : -1));
    return records;
  }
}

function trimExtractedText(text: string): string {
  if (text.length <= MAX_EXTRACTED_TEXT_LENGTH) {
    return text;
  }
  return text.slice(0, MAX_EXTRACTED_TEXT_LENGTH);
}

function toFileTimestamp(isoTimestamp: string): string {
  return isoTimestamp.replace(/[:.]/g, "-");
}
