import { useEffect, useState } from "react";
import FileUploadButton from "./FileUploadButton";
import {
  deleteFile,
  FileRecord,
  getFiles,
  toFileUrl,
  uploadFile,
} from "../../services/files_api";
import "./FileUpload.css";

type FileUploadProps = {
  variant?: "embedded" | "modal";
  onClose?: () => void;
  showFileList?: boolean;
  subtitle?: string;
};

function FileUpload({
  variant = "embedded",
  onClose,
  showFileList = false,
  subtitle = "Choose a document to start secure processing.",
}: FileUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");

  const loadFiles = async () => {
    const fileList = await getFiles();
    setFiles(fileList);
  };

  useEffect(() => {
    if (showFileList) {
      void loadFiles();
    }
  }, [showFileList]);

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setMessage("");
    try {
      await uploadFile(selectedFile, description);
      setSelectedFile(null);
      setDescription("");
      setMessage("File uploaded successfully.");
      if (showFileList) {
        await loadFiles();
      }
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
      {variant === "modal" ? (
        <div className="upload-card-header">
          <h2 id="upload-dialog-title" className="upload-card-title">
            Upload your file
          </h2>
          <button
            type="button"
            className="upload-modal-close"
            onClick={onClose}
            aria-label="Close upload dialog"
          >
            ×
          </button>
        </div>
      ) : (
        <h2 className="upload-card-title">Upload your file</h2>
      )}

      <p className="upload-card-subtitle">{subtitle}</p>

      <FileUploadButton onFileSelect={setSelectedFile} />

      {selectedFile ? (
        <p className="selected-file">
          Selected file: <strong>{selectedFile.name}</strong>
        </p>
      ) : null}

      <input
        type="text"
        className="upload-description-input"
        placeholder="Description (optional)"
        value={description}
        onChange={(event) => setDescription(event.target.value)}
      />

      <button
        type="button"
        className="upload-submit-btn"
        onClick={() => void handleUpload()}
        disabled={!selectedFile || uploading}
      >
        {uploading ? "Uploading..." : "Upload"}
      </button>

      {message ? <p className="upload-message">{message}</p> : null}

      {showFileList ? (
        <div className="file-list">
          <h3>Files</h3>
          {files.length === 0 ? (
            <p className="upload-card-subtitle">No files uploaded yet.</p>
          ) : (
            files.map((file) => (
              <div key={file.id} className="file-row">
                <a href={toFileUrl(file.filepath)} target="_blank" rel="noreferrer">
                  {file.filename}
                </a>
                <span>{Math.round(file.filesize / 1024)} KB</span>
                <span>{file.is_active ? "Active" : "Inactive"}</span>
                <button type="button" onClick={() => void handleDelete(file.id)}>
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );

  if (variant === "modal") {
    return (
      <div className="upload-modal-overlay" onClick={onClose}>
        <div
          className="upload-modal-panel"
          onClick={(event) => event.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-labelledby="upload-dialog-title"
        >
          {card}
        </div>
      </div>
    );
  }

  return card;
}

export default FileUpload;
