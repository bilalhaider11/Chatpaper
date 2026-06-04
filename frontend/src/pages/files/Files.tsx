import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchCurrentUser, tokenStore } from "../../api/axios";
import FileUpload from "../../components/fileUpload/FileUpload";
import { deleteFile, downloadFile, FileRecord, getFiles } from "../../services/files_api";
import "./Files.css";

function StatusBadge({ status }: { status: string | null }) {
  if (!status || status === "QUEUED") return <span className="fbadge fbadge-queued">Queued</span>;
  if (status.startsWith("STAGE_")) {
    const n = status.split("_")[1];
    return <span className="fbadge fbadge-processing">Processing {n}/6</span>;
  }
  if (status === "COMPLETE") return <span className="fbadge fbadge-complete">Ready</span>;
  if (status === "FAILED_RETRYABLE") return <span className="fbadge fbadge-retrying">Retrying</span>;
  return <span className="fbadge fbadge-failed">Failed</span>;
}

function Files() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);

  const isTerminal = (s: string | null) =>
    s === "COMPLETE" || s === "FAILED_PERMANENT" || s == null;

  const loadFiles = async () => {
    const list = await getFiles();
    setFiles(list);
    return list;
  };

  useEffect(() => {
    if (!tokenStore.getToken()) {
      navigate("/login", { replace: true });
      return;
    }
    void loadFiles().finally(() => setLoading(false));
  }, [navigate]);

  const hasPending = files.some((f) => !isTerminal(f.ingestion_status));

  useEffect(() => {
    if (!hasPending) return;
    const id = setInterval(() => void loadFiles(), 3000);
    return () => clearInterval(id);
  }, [hasPending]);

  const handleDelete = async (id: number) => {
    await deleteFile(id);
    await loadFiles();
  };

  const handleUploadSuccess = async () => {
    await loadFiles();
    setShowUpload(false);
  };

  if (loading) return <div className="files-page files-loading">Loading…</div>;

  return (
    <div className="files-page">
      {showUpload && (
        <FileUpload
          variant="modal"
          onClose={() => setShowUpload(false)}
          onUploadSuccess={handleUploadSuccess}
        />
      )}

      <div className="files-shell">
        <div className="files-header">
          <div className="files-header-left">
            <Link to="/" className="files-back">← Home</Link>
            <h1 className="files-title">My Files</h1>
          </div>
          <button
            type="button"
            className="files-upload-btn"
            onClick={() => setShowUpload(true)}
          >
            + Upload New
          </button>
        </div>

        {files.length === 0 ? (
          <div className="files-empty">
            <p>No files uploaded yet.</p>
            <button
              type="button"
              className="files-upload-btn"
              onClick={() => setShowUpload(true)}
            >
              Upload your first file
            </button>
          </div>
        ) : (
          <div className="files-table">
            <div className="files-table-head">
              <span>Filename</span>
              <span>Size</span>
              <span>Status</span>
              <span>Actions</span>
            </div>
            {files.map((file) => (
              <div key={file.id} className="files-table-row">
                <span className="files-filename" title={file.filename}>
                  {file.filename}
                </span>
                <span className="files-size">
                  {Math.round(file.filesize / 1024)} KB
                </span>
                <StatusBadge status={file.ingestion_status} />
                <div className="files-actions">
                  <button
                    type="button"
                    className="files-action-btn files-download"
                    onClick={() => void downloadFile(file.id, file.filename)}
                  >
                    Download
                  </button>
                  <button
                    type="button"
                    className="files-action-btn files-delete"
                    onClick={() => void handleDelete(file.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default Files;
