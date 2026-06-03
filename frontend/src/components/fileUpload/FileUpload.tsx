import { useCallback, useEffect, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";

import { ACCEPTED_FILE_TYPES } from "../../services/file_config";
import {
  deleteFile,
  FileRecord,
  getFiles,
  toFileUrl,
  uploadFile,
} from "../../services/files_api";
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
}

type FileUploadProps = {
  variant?: "embedded" | "modal";
  onClose?: () => void;
  onUploadSuccess?: () => Promise<void> | void;
  showFileList?: boolean;
  subtitle?: string;
};

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
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const uploadInFlightRef = useRef(false);

  const loadFiles = async () => {
    const fileList = await getFiles();
    setFiles(fileList);
  };

  const isTerminal = (status: string | null) =>
    status === "COMPLETE" || status === "FAILED_PERMANENT" || status == null;

  const hasPending = files.some((f) => !isTerminal(f.ingestion_status));

  // Poll every 3 s while any file is still being ingested, then stop.
  useEffect(() => {
    if (!showFileList || !hasPending) return;
    const id = setInterval(() => void loadFiles(), 3000);
    return () => clearInterval(id);
  }, [showFileList, hasPending]);

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
    multiple: false,
    accept: ACCEPTED_FILE_TYPES,
  });

  const handleUpload = async () => {
    if (!selectedFile || uploadInFlightRef.current) return;

    uploadInFlightRef.current = true;
    setUploading(true);
    setUploadProgress(0);
    setMessage("");

    let uploaded = false;

    try {
      await uploadFile(selectedFile, description, setUploadProgress);
      uploaded = true;
      setMessage("File uploaded successfully.");
      setSelectedFile(null);
      setDescription("");
    } catch {
      setMessage("Failed to upload file.");
    } finally {
      uploadInFlightRef.current = false;
      setUploading(false);
      setUploadProgress(null);
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
    <div className="upload-card">
      <h2 className="upload-card-title">Upload your file</h2>

      <p className="upload-card-subtitle">{subtitle}</p>

      <div {...getRootProps()} className="dropzone">
        <input {...getInputProps()} />

        {isDragActive ? (
          <p>Drop the file here...</p>
        ) : (
          <p>Drag & drop file here, or click to select</p>
        )}
      </div>

      {selectedFile && (
        <p className="selected-file">
          Selected: <strong>{selectedFile.name}</strong>
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
        className="upload-description-input"
        placeholder="Description (optional)"
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        disabled={uploading}
      />

      <button
        type="button"
        className="upload-submit-btn"
        onClick={() => void handleUpload()}
        disabled={!selectedFile || uploading}
      >
        {uploading ? "Uploading..." : "Upload"}
      </button>

      {uploadProgress !== null && (
        <div className="upload-progress">
          <div className="upload-progress-track">
            <div
              className="upload-progress-fill"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
          <span className="upload-progress-label">{uploadProgress}%</span>
        </div>
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
                <a
                  href={toFileUrl(file.id)}
                  target="_blank"
                  rel="noreferrer"
                >
                  {file.filename}
                </a>
                <span>{Math.round(file.filesize / 1024)} KB</span>
                <StatusBadge status={file.ingestion_status} />
                <button
                  type="button"
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
      <div className="upload-modal-overlay" onClick={onClose}>
        <div
          className="upload-modal-panel"
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
