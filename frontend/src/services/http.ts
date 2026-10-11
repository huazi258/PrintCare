export type ApiNamespace = "core" | "admin";

export class ApiError extends Error {
  public readonly status: number;
  public readonly details: unknown;

  public constructor(message: string, status: number, details: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export interface RequestOptions extends Omit<RequestInit, "body" | "method"> {
  signal?: AbortSignal;
}

function endpoint(namespace: ApiNamespace, path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `/api/${namespace}${normalizedPath}`;
}

function errorMessage(status: number, payload: unknown) {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = payload.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  return `请求失败（HTTP ${status}）`;
}

async function readPayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text || null;
}

async function request<T>(
  namespace: ApiNamespace,
  path: string,
  init: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(endpoint(namespace, path), {
      credentials: "include",
      ...init,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError("网络连接失败，请检查服务是否可用。", 0, error);
  }

  const payload = await readPayload(response);
  if (!response.ok) {
    throw new ApiError(errorMessage(response.status, payload), response.status, payload);
  }
  return payload as T;
}

export const apiClient = {
  get<T>(namespace: ApiNamespace, path: string, options: RequestOptions = {}) {
    return request<T>(namespace, path, { ...options, method: "GET" });
  },

  post<T>(namespace: ApiNamespace, path: string, body?: unknown, options: RequestOptions = {}) {
    const isFormData = body instanceof FormData;
    return request<T>(namespace, path, {
      ...options,
      method: "POST",
      headers: isFormData
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
    });
  },

  delete<T>(namespace: ApiNamespace, path: string, options: RequestOptions = {}) {
    return request<T>(namespace, path, { ...options, method: "DELETE" });
  },
};
