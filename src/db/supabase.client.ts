import fetch from "node-fetch";

export interface SupabaseRestClientConfig {
  url: string;
  serviceRoleKey: string;
}

export class SupabaseRestClient {
  constructor(private readonly config: SupabaseRestClientConfig) {}

  async insert(table: string, payload: Record<string, unknown>): Promise<void> {
    await this.requestVoid("POST", `/rest/v1/${table}`, payload, {
      prefer: "return=minimal",
    });
  }

  async upsert(
    table: string,
    payload: Record<string, unknown>,
    options: { onConflict: string },
  ): Promise<void> {
    await this.requestVoid(
      "POST",
      `/rest/v1/${table}?on_conflict=${encodeURIComponent(options.onConflict)}`,
      payload,
      {
        prefer: "resolution=merge-duplicates,return=minimal",
      },
    );
  }

  async selectOne<T>(
    table: string,
    filters: Record<string, string | number>,
    columns = "*",
  ): Promise<T | null> {
    const rows = await this.selectMany<T>(table, filters, columns);
    if (!rows.length) {
      return null;
    }
    return rows[0];
  }

  async selectMany<T>(
    table: string,
    filters: Record<string, string | number>,
    columns = "*",
  ): Promise<T[]> {
    const query = new URLSearchParams();
    query.set("select", columns);
    for (const [key, value] of Object.entries(filters)) {
      query.set(key, `eq.${value}`);
    }

    const response = await fetch(
      `${this.config.url}/rest/v1/${table}?${query.toString()}`,
      {
        method: "GET",
        headers: this.baseHeaders({
          accept: "application/json",
        }),
      },
    );

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Supabase select failed: HTTP ${response.status} - ${body}`);
    }

    const rows = (await response.json()) as T[];
    if (!Array.isArray(rows)) {
      return [];
    }
    return rows;
  }

  async rpc<TResult>(
    fnName: string,
    payload: Record<string, unknown>,
  ): Promise<TResult[]> {
    const response = await fetch(
      `${this.config.url}/rest/v1/rpc/${fnName}`,
      {
        method: "POST",
        headers: this.baseHeaders({
          accept: "application/json",
        }),
        body: JSON.stringify(payload),
      },
    );

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Supabase RPC failed (${fnName}): HTTP ${response.status} - ${body}`);
    }

    const rows = (await response.json()) as TResult[];
    return Array.isArray(rows) ? rows : [];
  }

  async deleteMany(
    table: string,
    filters: Record<string, string | number>,
  ): Promise<void> {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
      query.set(key, `eq.${value}`);
    }

    const response = await fetch(
      `${this.config.url}/rest/v1/${table}?${query.toString()}`,
      {
        method: "DELETE",
        headers: this.baseHeaders({
          prefer: "return=minimal",
        }),
      },
    );

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Supabase delete failed: HTTP ${response.status} - ${body}`);
    }
  }

  private async requestVoid(
    method: "POST",
    path: string,
    payload: Record<string, unknown>,
    extraHeaders?: Record<string, string>,
  ): Promise<void> {
    const response = await fetch(`${this.config.url}${path}`, {
      method,
      headers: this.baseHeaders(extraHeaders),
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Supabase request failed: HTTP ${response.status} - ${body}`);
    }
  }

  private baseHeaders(extraHeaders?: Record<string, string>): Record<string, string> {
    return {
      apikey: this.config.serviceRoleKey,
      authorization: `Bearer ${this.config.serviceRoleKey}`,
      "content-type": "application/json",
      ...(extraHeaders ?? {}),
    };
  }
}
