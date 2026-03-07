import fetch from "node-fetch";
import FormData from "form-data";

interface TranscriptionResponse {
  text?: string;
}

export class TranscriptionClient {
  constructor(
    private readonly apiKey: string,
    private readonly model: string,
  ) {}

  async transcribeOgg(buffer: Buffer, fileName = "voice.ogg"): Promise<string> {
    const form = new FormData();
    form.append("model", this.model);
    form.append("file", buffer, {
      filename: fileName,
      contentType: "audio/ogg",
    });

    const response = await fetch("https://api.openai.com/v1/audio/transcriptions", {
      method: "POST",
      headers: {
        authorization: `Bearer ${this.apiKey}`,
        ...form.getHeaders(),
      },
      body: form,
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Transcription API error: HTTP ${response.status} - ${body}`);
    }

    const body = (await response.json()) as TranscriptionResponse;
    const text = typeof body.text === "string" ? body.text.trim() : "";
    if (!text) {
      throw new Error("Transcription returned empty text.");
    }

    return text;
  }
}
