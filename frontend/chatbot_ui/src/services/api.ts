import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:8000/api";
const TOKEN_KEY = "auth_token";

export type User = {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
};

export type FileRecord = {
  id: number;
  filename: string;
  filepath: string;
  filesize: number;
  description: string | null;
  is_active: boolean;
};

const api = axios.create({
  baseURL: API_BASE_URL,
});

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

export async function fetchCurrentUser() {
  const response = await api.get<User>("/auth/users/me");
  return response.data;
}

export async function uploadFile(file: File, description: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("description", description);
  const response = await api.post<FileRecord>("/files/upload", form);
  return response.data;
}

export async function getFiles() {
  const response = await api.get<FileRecord[]>("/files/");
  return response.data;
}


export async function deleteFile(id: number) {
  await api.delete(`/files/${id}`);
}

export function toFileUrl(path: string) {
  return `http://127.0.0.1:8000${path}`;
}
