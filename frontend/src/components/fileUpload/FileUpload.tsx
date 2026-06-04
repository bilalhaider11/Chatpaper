import { useCallback, useEffect, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";

import { ACCEPTED_FILE_TYPES } from "../../services/file_config";
import {
  deleteFile,
  downloadFile,
  FileRecord,
  getApiErrorMessage,
  getFiles,
  uploadFile,
} from "../../services/files_api";
import { CloudUploadIcon, FileIcon, UploadIcon } from "../icons/Icons";
import FilePreview from "./FilePreview";
import "./FileUpload.css";

const StatusBadge = ({ status }: { status: string | null }) => {
  let label: string;
  let cls: string;

  if (!status || status === "QUEUED") {
    label = "Queued"; cls = "badge-queued";
  } else if (status.startsWith("STAGE_")) {
    const n = status.split("_")[1];
    label = `Processing ${n}/6`; cls = "badge-processing";
  } else if (status === "COMPLETE") {
    label = "Ready"; cls = "badge-complete";
  } else if (status === "FAILED_RETRYABLE") {
    label = "Retrying"; cls = "badge-retrying";
  } else {
    label = "Failed"; cls = "badge-failed";
  }

  return <span className={`ingestion-badge ${cls}`}>{label}</span>;
};

function fileTypeIcon(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return "ftype-pdf";
  if (ext === "docx" || ext === "doc") return "ftype-docx";
  if (ext === "xlsx" || ext === "xls" || ext === "csv") return "ftype-xlsx";
  return "ftype-default";
}

type FileUploadProps = {
  variant?: "embedded" | "modal";
  onClose?: () => void;
  onUploadSuccess?: (file: FileRecord) => Promise<void> | void;
  showFileList?: boolean;
  subtitle?: string;
};

function FileUpload({
  variant = "embedded",
  onClose,
  onUploadSuccess,
  showFileList = false,
  subtitle = "Upload a document to start chatting with it.",
}: FileUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [rejectMsg, setRejectMsg] = useState("");
  const rejectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const uploadInFlightRef = useRef(false);

  const loadFiles = async () => {
    const fileList = await getFiles();
    setFiles(fileList);
  };

  const isTerminal = (status: string | null) =>
    status === "COMPLETE" || status === "FAILED_PERMANENT" || status == null;

  const hasPending = files.some((f) => !isTerminal(f.ingestion_status));

  useEffect(() => {
    if (!showFileList || !hasPending) return;
    const id = setInterval(() => void loadFiles(), 3000);
    return () => clearInterval(id);
  }, [showFileList, hasPending]);

  useEffect(() => {
    if (showFileList) void loadFiles();
  }, [showFileList]);

  // Escape key closes modal
  useEffect(() => {
    if (variant !== "modal") return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [variant, onClose]);

  useEffect(() => {
    if (!selectedFile) { setPreviewUrl(null); return; }
    const url = URL.createObjectURL(selectedFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [selectedFile]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setSelectedFile(acceptedFiles[0] ?? null);
    setMessage("");
    setRejectMsg("");
  }, []);

  const onDropRejected = useCallback(() => {
    if (rejectTimerRef.current) clearTimeout(rejectTimerRef.current);
    setRejectMsg("Unsupported file type. Use PDF, DOCX, TXT, CSV, or XLSX.");
    rejectTimerRef.current = setTimeout(() => setRejectMsg(""), 3500);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    multiple: false,
    accept: ACCEPTED_FILE_TYPES,
  });

  const clearSelection = (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedFile(null);
    setMessage("");
  };

  const handleUpload = async () => {
    if (!selectedFile || uploadInFlightRef.current) return;

    uploadInFlightRef.current = true;
    setUploading(true);
    setUploadProgress(0);
    setMessage("");

    let record: FileRecord | null = null;

    try {
      record = await uploadFile(selectedFile, setUploadProgress);
      setMessage("File uploaded successfully.");
      setSelectedFile(null);
    } catch (err) {
      setMessage(getApiErrorMessage(err, "Failed to upload file."));
    } finally {
      uploadInFlightRef.current = false;
      setUploading(false);
      setUploadProgress(null);
    }

    if (!record) return;

    if (showFileList) void loadFiles();

    try {
      await onUploadSuccess?.(record);
      if (variant === "modal") onClose?.();
    } catch (err) {
      setMessage(getApiErrorMessage(err, "Failed to upload file."));
    }
  };

  const handleDelete = async (id: number) => {
    await deleteFile(id);
    await loadFiles();
  };

  const card = (
    <div className="upload-card">
      <div className="upload-card-header">
        <div>
          <h2 className="upload-card-title">Upload a document</h2>
          <p className="upload-card-subtitle">{subtitle}</p>
        </div>
        {variant === "modal" && onClose && (
          <button type="button" className="upload-modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        )}
      </div>

      <div
        {...getRootProps()}
        className={`dropzone${isDragActive ? " dropzone-active" : ""}${selectedFile ? " dropzone-has-file" : ""}`}
      >
        <input {...getInputProps()} />

        {selectedFile ? (
          <div className="dropzone-file-selected">
            <FileIcon className={`dropzone-file-icon ${fileTypeIcon(selectedFile.name)}`} strokeWidth={1.5} />
            <span className="dropzone-filename">{selectedFile.name}</span>
            <span className="dropzone-filesize">{(selectedFile.size / 1024).toFixed(0)} KB</span>
            <button type="button" className="dropzone-clear" onClick={clearSelection} aria-label="Remove file">×</button>
          </div>
        ) : (
          <>
            <CloudUploadIcon className="dropzone-upload-icon" strokeWidth={1.5} />
            <p className="dropzone-text">{isDragActive ? "Drop it here…" : "Drag & drop your document"}</p>
            <p className="dropzone-hint">or click to browse</p>
          </>
        )}
      </div>

      {previewUrl && selectedFile && (
        <div className="upload-preview-wrap">
          <FilePreview fileUrl={previewUrl} fileType={selectedFile.type} fileName={selectedFile.name} />
        </div>
      )}

      <div className="upload-format-chips">
        {["PDF", "DOCX", "TXT", "CSV", "XLSX"].map((fmt) => (
          <span key={fmt} className="upload-format-chip">{fmt}</span>
        ))}
      </div>

      {rejectMsg && <p className="upload-message upload-message-error">{rejectMsg}</p>}

      {uploading ? (
        <div className="upload-progress-wrap">
          <div className="upload-progress-track">
            <div className="upload-progress-fill" style={{ width: `${uploadProgress ?? 0}%` }} />
          </div>
          <span className="upload-progress-label">{uploadProgress ?? 0}%</span>
        </div>
      ) : (
        <button
          type="button"
          className="upload-submit-btn"
          onClick={() => void handleUpload()}
          disabled={!selectedFile}
        >
          <UploadIcon width={14} height={14} />
          Upload document
        </button>
      )}

      {message && <p className="upload-message">{message}</p>}

      {showFileList && (
        <div className="file-list">
          <h3>Files</h3>
          {files.length === 0 ? (
            <p>No files uploaded.</p>
          ) : (
            files.map((file) => (
              <div key={file.id} className="file-row">
                <button
                  type="button"
                  className="file-download-btn"
                  onClick={() => void downloadFile(file.id, file.filename)}
                >
                  {file.filename}
                </button>
                <span>{Math.round(file.filesize / 1024)} KB</span>
                <StatusBadge status={file.ingestion_status} />
                <button type="button" onClick={() => void handleDelete(file.id)}>
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
      <div className="upload-modal-overlay" onClick={onClose}>
        <div className="upload-modal-panel" onClick={(e) => e.stopPropagation()}>
          {card}
        </div>
      </div>
    );
  }

  return card;
}

export default FileUpload;
