import { api, toFileUrl } from "../api/axios";

export { toFileUrl };

export type FileRecord = {
  id: number;
  filename: string;
  filepath: string;
  filesize: number;
  description: string | null;
  is_active: boolean;
};

export async function uploadFile(
  file: File,
  description: string
) {
  const form = new FormData();

  form.append("file", file);
  form.append("description", description);

  const response = await api.post<FileRecord>(
    "/files/upload",
    form,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );

  return response.data;
}

export async function getFiles() {
  const response = await api.get<FileRecord[]>("/files/");
  return response.data;
}

export async function deleteFile(id: number) {
  await api.delete(`/files/${id}`);
}
