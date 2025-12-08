/**
 * API Client - ALL DATA ACCESS
 *
 * SECURITY: All sensitive data (HR, compensation, PII) flows through this client
 * to our FastAPI backend. The backend:
 * - Validates JWT tokens
 * - Checks role-based permissions
 * - Logs all access for audit trails
 * - Applies business logic and data filtering
 *
 * NEVER query Supabase directly for data - always use this client.
 */

import { getAccessToken } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function getAuthHeader(): Promise<Record<string, string>> {
  const token = await getAccessToken();

  if (token) {
    return {
      Authorization: `Bearer ${token}`,
    };
  }

  return {};
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const authHeaders = await getAuthHeader();

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = "An error occurred";
    let details: unknown;

    try {
      const error = await response.json();
      message = error.detail || error.message || message;
      details = error;
    } catch {
      message = response.statusText;
    }

    // Handle specific auth errors
    if (response.status === 401) {
      // Token expired or invalid - redirect to login
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }

    throw new ApiError(response.status, message, details);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// Convenience methods - ALL data access goes through these
export const api = {
  get: <T>(endpoint: string) => apiClient<T>(endpoint, { method: "GET" }),

  post: <T>(endpoint: string, data?: unknown) =>
    apiClient<T>(endpoint, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    }),

  patch: <T>(endpoint: string, data: unknown) =>
    apiClient<T>(endpoint, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  put: <T>(endpoint: string, data: unknown) =>
    apiClient<T>(endpoint, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: <T>(endpoint: string) => apiClient<T>(endpoint, { method: "DELETE" }),

  upload: async <T>(endpoint: string, file: File, fieldName = "file"): Promise<T> => {
    const authHeaders = await getAuthHeader();
    const formData = new FormData();
    formData.append(fieldName, file);

    const response = await fetch(`${API_URL}${endpoint}`, {
      method: "POST",
      headers: authHeaders,
      body: formData,
    });

    if (!response.ok) {
      let message = "Upload failed";
      try {
        const error = await response.json();
        message = error.detail || message;
      } catch {
        message = response.statusText;
      }
      throw new ApiError(response.status, message);
    }

    return response.json();
  },
};
