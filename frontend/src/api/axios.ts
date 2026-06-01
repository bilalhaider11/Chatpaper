import axios from "axios";

/** Ensures browser requests hit FastAPI's `/api` router (see backend/api/router.py). */
export function normalizeApiBaseUrl(url: string): string {
  const trimmed = url.replace(/\/+$/, "");
  return trimmed.endsWith("/api") ? trimmed : `${trimmed}/api`;
}

export const API_BASE_URL = normalizeApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api"
);

/** Origin without the `/api` suffix (e.g. for WebSocket host). */
export function apiOrigin(): string {
  return API_BASE_URL.replace(/\/api$/, "");
}
const TOKEN_KEY = "auth_token";

export type User = {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
};

export const api = axios.create({
  baseURL: API_BASE_URL,
});

// Automatically attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});


export const tokenStore = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setToken: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export async function login(email: string, password: string) {
  const payload = new URLSearchParams();
  payload.set("username", email);
  payload.set("password", password);

  const response = await api.post<{ access_token: string; token_type: string }>(
    "/auth/login",
    payload,
    { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
  );

  return response.data;
}

export async function exchangeGoogleCode(code: string) {
  const response = await api.post<{ access_token: string; token_type: string }>(
    "/auth/exchange-code",
    { code }
  );
  return response.data;
}

export async function signup(email:string, password:string){
  const payload = {
  "email": email,
  "password": password
}
  const response = await api.post("/auth/users", payload);
  return response.data
}

export async function fetchCurrentUser() {
  const response = await api.get<User>("/auth/users/me");
  return response.data;
}

/** Build an absolute URL for an API path (e.g. `/files/1/download`). */
export function toApiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const withApiPrefix = normalized.startsWith("/api/")
    ? normalized
    : `/api${normalized}`;
  return `${apiOrigin()}${withApiPrefix}`;
}

/** Authenticated file download route. */
export function fileDownloadUrl(fileId: number): string {
  return toApiUrl(`/files/${fileId}/download`);
}

/** @deprecated Prefer {@link fileDownloadUrl} for downloads. */
export function toFileUrl(path: string) {
  return toApiUrl(path);
}
