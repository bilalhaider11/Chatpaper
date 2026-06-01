import axios from "axios";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";
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

export async function exchangeOAuthCode(code: string) {
  const response = await api.post<{ access_token: string; token_type: string }>(
    "/auth/exchange-token",
    { code }
  );
  return response.data;
}

export async function signup(email:string, password:string){
  const payload = {
  "email": email,
  "password": password
}
  const response = await api.post(
    "auth/users",
    payload

  )
  return response.data
}

export async function fetchCurrentUser() {
  const response = await api.get<User>("/auth/users/me");
  return response.data;
}

export function toFileUrl(path: string) {
  return `http://127.0.0.1:8000${path}`;
}
