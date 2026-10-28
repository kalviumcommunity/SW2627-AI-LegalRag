/**
 * Configurable API Client for FastAPI backend.
 * Reads VITE_API_BASE_URL (defaults to http://localhost:8000/api/v1).
 */

export const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/+$/, '');
  }
  return 'http://localhost:8000/api/v1';
};

export class ApiError extends Error {
  public status: number;
  public details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

let inMemoryToken: string | null = null;

export const setAuthToken = (token: string | null): void => {
  inMemoryToken = token;
  try {
    if (token) {
      sessionStorage.setItem('propertyintel_auth_token', token);
    } else {
      sessionStorage.removeItem('propertyintel_auth_token');
    }
  } catch {
    // Non-browser or storage restricted environment
  }
};

export const getAuthToken = (): string | null => {
  if (inMemoryToken) return inMemoryToken;
  try {
    const stored = sessionStorage.getItem('propertyintel_auth_token');
    if (stored) {
      inMemoryToken = stored;
      return stored;
    }
  } catch {
    // Storage restricted
  }
  return null;
};

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const { timeoutMs = 30000, headers = {}, ...restOptions } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const isFormData = restOptions.body instanceof FormData;
    const token = getAuthToken();
    const finalHeaders: Record<string, string> = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...((headers as Record<string, string>) || {}),
    };

    const response = await fetch(url, {
      ...restOptions,
      headers: finalHeaders,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;
      let errorData: unknown = null;

      try {
        const text = await response.text();
        if (text) {
          try {
            errorData = JSON.parse(text);
            if (typeof errorData === 'object' && errorData !== null) {
              const obj = errorData as Record<string, unknown>;
              if (typeof obj.detail === 'string') {
                errorMessage = obj.detail;
              } else if (Array.isArray(obj.detail)) {
                errorMessage = obj.detail
                  .map((d: { msg?: string }) => d.msg || JSON.stringify(d))
                  .join(', ');
              } else if (typeof obj.message === 'string') {
                errorMessage = obj.message;
              }
            }
          } catch {
            errorMessage = text;
          }
        }
      } catch {
        // Fallback to HTTP error
      }

      throw new ApiError(errorMessage, response.status, errorData);
    }

    // 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (error: unknown) {
    clearTimeout(timeoutId);
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('Request timed out. Please try again.', 504);
    }
    const message =
      error instanceof Error
        ? error.message
        : 'Network connection failed. Ensure the FastAPI backend is running.';
    throw new ApiError(message, 0);
  }
}
