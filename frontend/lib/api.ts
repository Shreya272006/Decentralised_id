import axios, { AxiosInstance, AxiosError } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem("access_token");
}

export function setStoredTokens(accessToken: string, refreshToken: string) {
  window.sessionStorage.setItem("access_token", accessToken);
  window.sessionStorage.setItem("refresh_token", refreshToken);
}

export function clearStoredTokens() {
  window.sessionStorage.removeItem("access_token");
  window.sessionStorage.removeItem("refresh_token");
}

// Tokens are kept in sessionStorage (not localStorage) to limit exposure
// window, and never persisted in a JS-readable cookie — this mitigates
// (but does not eliminate) token theft via XSS; a production deployment
// should move to httpOnly, Secure, SameSite=Strict cookies issued by the
// backend and drop client-readable token storage entirely.
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
});

apiClient.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      clearStoredTokens();
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as any)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.message).join(", ");
    return error.message;
  }
  return "An unexpected error occurred.";
}
