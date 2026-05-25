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
                  href={toFileUrl(file.filepath)}
                  target="_blank"
                  rel="noreferrer"
                >
                  {file.filename}
                </a>
                <span>{Math.round(file.filesize / 1024)} KB</span>

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
