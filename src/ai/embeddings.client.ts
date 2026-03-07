import fetch from "node-fetch";

interface EmbeddingsResponse {
  data: Array<{
    embedding: number[];
  }>;
}

export class EmbeddingsClient {
  constructor(
    private readonly apiKey: string,
    private readonly model: string,
  ) {}

  async createEmbedding(text: string): Promise<number[]> {
    const response = await fetch("https://api.openai.com/v1/embeddings", {
      method: "POST",
      headers: {
        authorization: `Bearer ${this.apiKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: this.model,
        input: text.slice(0, 6000),
      }),
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Embeddings API error: HTTP ${response.status} - ${body}`);
    }

    const body = (await response.json()) as EmbeddingsResponse;
    const vector = body.data[0]?.embedding;
    if (!Array.isArray(vector) || vector.length === 0) {
      throw new Error("Embeddings API returned empty vector.");
    }

    return vector;
  }
}
