import { Logger } from "../config/logger";
import { DocumentType } from "../shared/types/domain.types";
import { extractDocxText } from "./extractors/docx.extractor";
import { extractPdfText } from "./extractors/pdf.extractor";

export class DocumentService {
  constructor(private readonly logger: Logger) {}

  detectDocumentType(fileName?: string, mimeType?: string): DocumentType {
    const normalizedFileName = (fileName ?? "").toLowerCase();
    const normalizedMime = (mimeType ?? "").toLowerCase();

    if (normalizedMime.includes("pdf") || normalizedFileName.endsWith(".pdf")) {
      return "pdf";
    }

    if (
      normalizedMime.includes(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ) || normalizedFileName.endsWith(".docx")
    ) {
      return "docx";
    }

    return "unknown";
  }

  validateSupportedDocument(fileName?: string, mimeType?: string): void {
    const type = this.detectDocumentType(fileName, mimeType);
    const isPdf = type === "pdf";
    const isDocx = type === "docx";

    if (!isPdf && !isDocx) {
      throw new Error("Unsupported document type. Please upload PDF or DOCX.");
    }
  }

  async extractText(buffer: Buffer, fileName?: string, mimeType?: string): Promise<string> {
    this.validateSupportedDocument(fileName, mimeType);

    const isPdf = this.detectDocumentType(fileName, mimeType) === "pdf";

    const text = isPdf ? await extractPdfText(buffer) : await extractDocxText(buffer);
    const compactText = text.replace(/\u0000/g, "").replace(/\s+/g, " ").trim();

    this.logger.info("Document text extracted", {
      mimeType,
      fileName,
      chars: compactText.length,
    });

    if (!compactText) {
      throw new Error("Could not extract text from document.");
    }

    return compactText;
  }
}
