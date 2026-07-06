import axios from "axios";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";
const TOKEN_KEY = "auth_token";

export type User = {
  id: number;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  auth_provider?: string;
  credits?: number;
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

export async function signup(email: string, password: string, name: string) {
  const response = await api.post("/auth/users", {
    email,
    password,
    name,
  });
  return response.data;
}

export async function fetchAllUsers() {
  const response = await api.get<User[]>("/auth/users");
  return response.data;
}

export async function changePassword(
  newPassword: string,
  options?: { currentPassword?: string; userId?: number }
) {
  await api.patch("/auth/change-password", {
    new_password: newPassword,
    ...(options?.currentPassword ? { current_password: options.currentPassword } : {}),
    ...(options?.userId !== undefined ? { user_id: options.userId } : {}),
  });
}

export async function updateName(name: string, userId?: number) {
  const response = await api.patch<User>("/auth/update-name", {
    name,
    ...(userId !== undefined ? { user_id: userId } : {}),
  });
  return response.data;
}

export async function fetchCurrentUser() {
  const response = await api.get<User>("/auth/users/me");
  return response.data;
}

export async function requestPasswordReset(email: string) {
  const response = await api.post<{ message: string }>("/auth/forgot-password", {
    email,
  });
  return response.data;
}

export async function validatePasswordResetToken(token: string) {
  const response = await api.get<{ message: string }>("/auth/reset-password/validate", {
    params: { token },
  });
  return response.data;
}

export async function resetPassword(token: string, newPassword: string) {
  const response = await api.post<{ access_token: string; token_type: string }>(
    "/auth/reset-password",
    { token, new_password: newPassword }
  );
  return response.data;
}

export function toFileUrl(fileId: number) {
  return `${API_BASE_URL}/files/${fileId}/download`;
}
