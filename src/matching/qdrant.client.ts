import fetch from "node-fetch";
import { Logger } from "../config/logger";

interface QdrantSearchPoint {
  id: number | string;
  payload?: Record<string, unknown>;
  score?: number;
}

interface QdrantCollectionResponse {
  result?: {
    points_count?: number;
    vectors_count?: number;
    indexed_vectors_count?: number;
    config?: {
      params?: {
        vectors?: {
          size?: number;
          distance?: string;
        };
      };
    };
  };
}

export interface QdrantClientConfig {
  baseUrl?: string;
  apiKey?: string;
  candidateCollection: string;
}

export class QdrantClient {
  private collectionReady = false;
  private vectorSize: number | null = null;

  constructor(
    private readonly config: QdrantClientConfig,
    private readonly logger: Logger,
  ) {
    if (this.config.baseUrl) {
      this.config.baseUrl = this.config.baseUrl.replace(/\/+$/, "");
    }
  }

  isEnabled(): boolean {
    return Boolean(this.config.baseUrl && this.config.apiKey && this.config.candidateCollection.trim());
  }

  async ensureCandidateCollection(vectorSize: number): Promise<void> {
    if (!this.isEnabled()) {
      return;
    }
    if (this.collectionReady && this.vectorSize === vectorSize) {
      return;
    }

    const collection = this.config.candidateCollection;
    const getResponse = await this.request<QdrantCollectionResponse>(
      "GET",
      `/collections/${encodeURIComponent(collection)}`,
    );

    if (getResponse.ok) {
      const existingSize = Number(getResponse.data.result?.config?.params?.vectors?.size ?? 0);
      if (existingSize > 0 && existingSize !== vectorSize) {
        this.logger.warn("Qdrant collection vector size mismatch, recreating collection", {
          collection,
          existingSize,
          requestedSize: vectorSize,
        });
        await this.requestVoid("DELETE", `/collections/${encodeURIComponent(collection)}`);
      } else {
        this.collectionReady = true;
        this.vectorSize = existingSize || vectorSize;
        return;
      }
    }

    await this.requestVoid("PUT", `/collections/${encodeURIComponent(collection)}`, {
      vectors: {
        size: vectorSize,
        distance: "Cosine",
      },
    });
    this.collectionReady = true;
    this.vectorSize = vectorSize;
    this.logger.info("Qdrant collection is ready", {
      collection,
      vectorSize,
    });
  }

  async upsertCandidateVector(input: {
    candidateTelegramUserId: number;
    vector: number[];
    payload?: Record<string, unknown>;
  }): Promise<void> {
    if (!this.isEnabled()) {
      return;
    }
    if (!Number.isInteger(input.candidateTelegramUserId) || input.candidateTelegramUserId <= 0) {
      return;
    }
    if (!Array.isArray(input.vector) || input.vector.length === 0) {
      return;
    }

    await this.ensureCandidateCollection(input.vector.length);
    const collection = this.config.candidateCollection;
    await this.requestVoid(
      "PUT",
      `/collections/${encodeURIComponent(collection)}/points?wait=true`,
      {
        points: [
          {
            id: input.candidateTelegramUserId,
            vector: input.vector,
            payload: {
              telegram_user_id: input.candidateTelegramUserId,
              ...(input.payload ?? {}),
            },
          },
        ],
      },
    );
  }

  async deleteCandidateVector(candidateTelegramUserId: number): Promise<void> {
    if (!this.isEnabled()) {
      return;
    }
    if (!Number.isInteger(candidateTelegramUserId) || candidateTelegramUserId <= 0) {
      return;
    }

    const collection = this.config.candidateCollection;
    await this.requestVoid(
      "POST",
      `/collections/${encodeURIComponent(collection)}/points/delete?wait=true`,
      {
        points: [candidateTelegramUserId],
      },
    );
  }

  async searchCandidateIds(input: { vector: number[]; limit: number }): Promise<number[]> {
    if (!this.isEnabled()) {
      return [];
    }
    if (!Array.isArray(input.vector) || input.vector.length === 0) {
      return [];
    }
    await this.ensureCandidateCollection(input.vector.length);

    const collection = this.config.candidateCollection;
    const searchBody = {
      vector: input.vector,
      limit: Math.max(1, Math.min(input.limit, 200)),
      with_payload: true,
      with_vector: false,
    };

    let response = await this.request<{
      result?: QdrantSearchPoint[];
    }>(
      "POST",
      `/collections/${encodeURIComponent(collection)}/points/search`,
      searchBody,
    );
    if (!response.ok) {
      response = await this.request<{
        result?: QdrantSearchPoint[];
      }>(
        "POST",
        `/collections/${encodeURIComponent(collection)}/points/query`,
        {
          query: input.vector,
          limit: Math.max(1, Math.min(input.limit, 200)),
          with_payload: true,
          with_vector: false,
        },
      );
    }

    if (!response.ok || !Array.isArray(response.data.result)) {
      return [];
    }

    const ids = response.data.result
      .map((item) => {
        const payloadId = Number(item.payload?.telegram_user_id ?? 0);
        if (Number.isInteger(payloadId) && payloadId > 0) {
          return payloadId;
        }
        const directId = Number(item.id);
        if (Number.isInteger(directId) && directId > 0) {
          return directId;
        }
        return 0;
      })
      .filter((id) => id > 0);

    return Array.from(new Set(ids));
  }

  async getCandidateVectorCount(): Promise<number | null> {
    if (!this.isEnabled()) {
      return null;
    }
    const collection = this.config.candidateCollection;
    const response = await this.request<QdrantCollectionResponse>(
      "GET",
      `/collections/${encodeURIComponent(collection)}`,
    );
    if (!response.ok) {
      return null;
    }
    const result = response.data.result;
    const byPoints = Number(result?.points_count ?? NaN);
    if (Number.isFinite(byPoints) && byPoints >= 0) {
      return Math.floor(byPoints);
    }
    const byVectors = Number(result?.vectors_count ?? NaN);
    if (Number.isFinite(byVectors) && byVectors >= 0) {
      return Math.floor(byVectors);
    }
    const byIndexed = Number(result?.indexed_vectors_count ?? NaN);
    if (Number.isFinite(byIndexed) && byIndexed >= 0) {
      return Math.floor(byIndexed);
    }
    return null;
  }

  private async request<T>(
    method: "GET" | "POST",
    path: string,
    body?: Record<string, unknown>,
  ): Promise<{ ok: true; data: T } | { ok: false; status: number; body: string }> {
    const response = await fetch(`${this.config.baseUrl}${path}`, {
      method,
      headers: this.headers(),
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        body: await response.text(),
      };
    }

    return {
      ok: true,
      data: (await response.json()) as T,
    };
  }

  private async requestVoid(
    method: "POST" | "PUT" | "DELETE",
    path: string,
    body?: Record<string, unknown>,
  ): Promise<void> {
    const response = await fetch(`${this.config.baseUrl}${path}`, {
      method,
      headers: this.headers(),
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Qdrant request failed: HTTP ${response.status} - ${text}`);
    }
  }

  private headers(): Record<string, string> {
    return {
      "content-type": "application/json",
      "api-key": this.config.apiKey ?? "",
    };
  }
}
