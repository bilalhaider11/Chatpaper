import { useCallback, useEffect, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";

import { ACCEPTED_FILE_TYPES } from "../../services/file_config";
import {
  deleteFile,
  FileRecord,
  getFiles,
  fileDownloadUrl,
  uploadFile,
} from "../../services/files_api";
import FilePreview from "./FilePreview";

type FileUploadProps = {
  variant?: "embedded" | "modal";
  onClose?: () => void;
  onUploadSuccess?: () => Promise<void> | void;
  showFileList?: boolean;
  subtitle?: string;
};

const fieldClass =
  "rounded-lg border border-slate-400/30 bg-[#0b1325] px-2.5 py-2 text-[0.95rem] text-slate-200 outline-none focus:border-blue-500/50";

function FileUpload({
  variant = "embedded",
  onClose,
  onUploadSuccess,
  showFileList = false,
  subtitle = "Choose a document to start secure processing.",
}: FileUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const uploadInFlightRef = useRef(false);

  const loadFiles = async () => {
    const fileList = await getFiles();
    setFiles(fileList);
  };

  useEffect(() => {
    if (showFileList) {
      void loadFiles();
    }
  }, [showFileList]);

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(null);
      return;
    }

    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [selectedFile]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setSelectedFile(acceptedFiles[0] ?? null);
    setMessage("");
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    accept: ACCEPTED_FILE_TYPES,
  });

  const handleUpload = async () => {
    if (!selectedFile || uploadInFlightRef.current) return;

    uploadInFlightRef.current = true;
    setUploading(true);
    setMessage("");

    let uploaded = false;

    try {
      await uploadFile(selectedFile, description);
      uploaded = true;
      setMessage("File uploaded successfully.");
      setSelectedFile(null);
      setDescription("");
    } catch {
      setMessage("Failed to upload file.");
    } finally {
      uploadInFlightRef.current = false;
      setUploading(false);
    }

    if (!uploaded) return;

    if (showFileList) {
      void loadFiles();
    }

    try {
      await onUploadSuccess?.();
      if (variant === "modal") {
        onClose?.();
      }
    } catch {
      setMessage("Failed to upload file.");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    await deleteFile(id);
    await loadFiles();
  };

  const card = (
    <div className="box-border flex w-full flex-col gap-3.5 rounded-2xl border border-slate-400/25 bg-slate-900/70 p-7">
      <h2 className="m-0 text-[1.4rem] font-bold text-slate-50">Upload your file</h2>

      <p className="m-0 text-[0.95rem] leading-relaxed text-slate-300">{subtitle}</p>

      <div
        {...getRootProps()}
        className="cursor-pointer rounded-xl border-2 border-dashed border-slate-500 p-10 text-center text-slate-200 transition-colors hover:border-slate-400"
      >
        <input {...getInputProps()} />

        {isDragActive ? (
          <p className="m-0">Drop the file here...</p>
        ) : (
          <p className="m-0">Drag & drop file here, or click to select</p>
        )}
      </div>

      {selectedFile && (
        <p className="m-0 break-words text-sm text-slate-200">
          Selected: <strong className="text-white">{selectedFile.name}</strong>
        </p>
      )}

      {previewUrl && selectedFile ? (
        <FilePreview
          fileUrl={previewUrl}
          fileType={selectedFile.type}
          fileName={selectedFile.name}
        />
      ) : null}

      <input
        type="text"
        className={fieldClass}
        placeholder="Description (optional)"
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        disabled={uploading}
      />

      <button
        type="button"
        className="w-fit cursor-pointer rounded-lg border border-slate-400/30 bg-[#0b1325] px-2.5 py-2 text-[0.95rem] text-slate-200 disabled:cursor-not-allowed disabled:opacity-70"
        onClick={() => void handleUpload()}
        disabled={!selectedFile || uploading}
      >
        {uploading ? "Uploading..." : "Upload"}
      </button>

      {message && <p className="m-0 text-sm text-blue-300">{message}</p>}

      {showFileList && (
        <div className="mt-1.5 flex flex-col gap-2">
          <h3 className="m-0 text-slate-50">Files</h3>
          {files.length === 0 ? (
            <p className="m-0 text-slate-300">No files uploaded.</p>
          ) : (
            files.map((file) => (
              <div
                key={file.id}
                className="grid grid-cols-1 items-center gap-1.5 border-b border-slate-400/15 pb-2 sm:grid-cols-[1fr_auto_auto] sm:gap-2 sm:border-b-0 sm:pb-0"
              >
                <a
                  href={fileDownloadUrl(file.id)}
                  target="_blank"
                  rel="noreferrer"
                  className="truncate text-blue-300 no-underline hover:underline"
                >
                  {file.filename}
                </a>
                <span className="text-sm text-slate-300">
                  {Math.round(file.filesize / 1024)} KB
                </span>

                <button
                  type="button"
                  className="cursor-pointer rounded-lg border border-slate-400/30 bg-[#0b1325] px-2 py-1.5 text-sm text-slate-200 hover:bg-slate-800"
                  onClick={() => void handleDelete(file.id)}
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );

  if (variant === "modal") {
    return (
      <div
        className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-950/72 p-6 backdrop-blur-sm"
        onClick={onClose}
      >
        <div
          className="w-full max-w-[480px]"
          onClick={(e) => e.stopPropagation()}
        >
          {card}
        </div>
      </div>
    );
  }

  return card;
}

export default FileUpload;
