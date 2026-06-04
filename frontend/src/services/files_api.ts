import { api, toFileUrl } from "../api/axios";

export { toFileUrl };

export type FileRecord = {
  id: number;
  filename: string;
  filepath: string;
  filesize: number;
  description: string | null;
  is_active: boolean;
  ingestion_status: string | null;
  // Present only on the upload response (UploadResponse.conversation_id); absent on GET /files/
  conversation_id?: number;
};

export async function uploadFile(
  file: File,
  onProgress?: (pct: number) => void,
) {
  const form = new FormData();
  form.append("file", file);

  const response = await api.post<FileRecord>("/files/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded * 100) / event.total));
      }
    },
  });

  return response.data;
}

export async function getFiles() {
  const response = await api.get<FileRecord[]>("/files/");
  return response.data;
}

export async function deleteFile(id: number) {
  await api.delete(`/files/${id}`);
}

export function getApiErrorMessage(err: unknown, fallback: string): string {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const detail = (err as any)?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (typeof detail?.message === "string") return detail.message;
  return fallback;
}

export async function downloadFile(id: number, filename: string) {
  const response = await api.get(`/files/${id}/download`, { responseType: "blob" });
  const url = URL.createObjectURL(response.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
