export interface VectorItem {
  userId: number;
  vector: number[];
  summaryText: string;
}

export interface VectorSearchResult {
  userId: number;
  similarity: number;
  summaryText: string;
}

export class VectorSearchRepository {
  searchTopK(queryVector: number[], items: ReadonlyArray<VectorItem>, topK: number): VectorSearchResult[] {
    const scored = items
      .map((item) => ({
        userId: item.userId,
        similarity: cosineSimilarity(queryVector, item.vector),
        summaryText: item.summaryText,
      }))
      .filter((item) => Number.isFinite(item.similarity))
      .sort((a, b) => b.similarity - a.similarity);

    return scored.slice(0, topK);
  }
}

function cosineSimilarity(a: number[], b: number[]): number {
  const size = Math.min(a.length, b.length);
  if (size === 0) {
    return 0;
  }

  let dot = 0;
  let normA = 0;
  let normB = 0;

  for (let index = 0; index < size; index += 1) {
    dot += a[index] * b[index];
    normA += a[index] * a[index];
    normB += b[index] * b[index];
  }

  if (normA === 0 || normB === 0) {
    return 0;
  }

  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}
