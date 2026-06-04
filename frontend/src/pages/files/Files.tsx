import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import logo from "../../assets/logo.png";
import { tokenStore } from "../../api/axios";
import FileUpload from "../../components/fileUpload/FileUpload";
import { deleteFile, downloadFile, FileRecord, getFiles } from "../../services/files_api";
import { getConversationList } from "../../services/conversation_api";
import { ACCEPTED_FILE_TYPES } from "../../services/file_config";
import { ChatBubbleIcon, CheckCircleIcon, DownloadIcon, FileIcon, LogoutIcon, SearchIcon, TrashIcon, UploadIcon } from "../../components/icons/Icons";
import "./Files.css";

function fileIcon(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  let cls = "ficon-default";
  if (ext === "pdf") cls = "ficon-pdf";
  else if (ext === "docx" || ext === "doc") cls = "ficon-docx";
  else if (ext === "xlsx" || ext === "xls" || ext === "csv") cls = "ficon-xlsx";
  else if (ext === "png" || ext === "jpg" || ext === "jpeg") cls = "ficon-img";
  return <FileIcon className={`ficon ${cls}`} strokeWidth={1.5} />;
}

function StatusBadge({ status }: { status: string | null }) {
  if (!status || status === "QUEUED")
    return <span className="fbadge fbadge-queued">Queued</span>;
  if (status.startsWith("STAGE_")) {
    const n = status.split("_")[1];
    return (
      <span className="fbadge fbadge-processing">
        <span className="fbadge-pulse" aria-hidden="true" />
        Processing {n}/6
      </span>
    );
  }
  if (status === "COMPLETE") return <span className="fbadge fbadge-complete">Ready</span>;
  if (status === "FAILED_RETRYABLE") return <span className="fbadge fbadge-retrying">Retrying</span>;
  return <span className="fbadge fbadge-failed">Failed</span>;
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
}

function Files({ onLogout }: { onLogout: () => void }) {
  const navigate = useNavigate();
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [search, setSearch] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isTerminal = (s: string | null) =>
    s === "COMPLETE" || s === "FAILED_PERMANENT" || s == null;

  const loadFiles = async () => {
    const list = await getFiles();
    setFiles(list);
    return list;
  };

  useEffect(() => {
    if (!tokenStore.getToken()) {
      onLogout();
      return;
    }
    void loadFiles().finally(() => setLoading(false));
  }, []);

  const hasPending = files.some((f) => !isTerminal(f.ingestion_status));
  useEffect(() => {
    if (!hasPending) return;
    const id = setInterval(() => void loadFiles(), 3000);
    return () => clearInterval(id);
  }, [hasPending]);

  const showToast = (msg: string) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast(msg);
    toastTimerRef.current = setTimeout(() => setToast(null), 3000);
  };

  const requestDelete = (id: number) => {
    if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
    setConfirmDeleteId(id);
    confirmTimerRef.current = setTimeout(() => setConfirmDeleteId(null), 5000);
  };

  const cancelDelete = () => {
    setConfirmDeleteId(null);
    if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
  };

  const handleDelete = async (id: number) => {
    cancelDelete();
    await deleteFile(id);
    await loadFiles();
    showToast("File deleted");
  };

  const handleUploadSuccess = async () => {
    await loadFiles();
    setShowUpload(false);
  };

  const logout = () => {
    tokenStore.clear();
    onLogout();
  };

  const handleChatClick = async (fileId: number) => {
    try {
      const convs = await getConversationList();
      const match = convs.find((c) => c.file_id === fileId);
      navigate(match ? `/chat/${match.id}` : "/chat");
    } catch {
      navigate("/chat");
    }
  };

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length > 0 && !showUpload) setShowUpload(true);
    },
    [showUpload],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: ACCEPTED_FILE_TYPES,
    noClick: true,
    disabled: showUpload,
  });

  const filteredFiles = files.filter((f) =>
    f.filename.toLowerCase().includes(search.toLowerCase()),
  );

  if (loading) return <div className="files-page files-loading">Loading…</div>;

  return (
    <div className="files-page" {...getRootProps()}>
      <input {...getInputProps()} />

      {isDragActive && (
        <div className="files-drag-overlay">
          <div className="files-drag-box">
            <UploadIcon strokeWidth={1.5} width={44} height={44} />
            <span>Drop to upload</span>
          </div>
        </div>
      )}

      {showUpload && (
        <FileUpload
          variant="modal"
          onClose={() => setShowUpload(false)}
          onUploadSuccess={handleUploadSuccess}
        />
      )}

      {toast && (
        <div className="files-toast" role="status" aria-live="polite">
          <CheckCircleIcon width={14} height={14} />
          {toast}
        </div>
      )}

      {/* ── Navbar ── */}
      <nav className="files-navbar">
        <Link to="/" className="files-nav-brand">
          <img src={logo} alt="" className="files-nav-icon" />
          <span className="files-nav-brand-name">Chatpaper</span>
        </Link>
        <div className="files-nav-right">
          <Link to="/chat" className="files-nav-link">Chat</Link>
          <button type="button" className="files-nav-logout" onClick={logout}>
            <LogoutIcon width={14} height={14} />
            Logout
          </button>
        </div>
      </nav>

      {/* ── Main content ── */}
      <div className="files-content">
        <div className="files-shell">

          {/* Header */}
          <div className="files-header">
            <div className="files-header-left">
              <h1 className="files-title">
                My Files
                <span className="files-count-chip">
                  {files.length} {files.length === 1 ? "file" : "files"}
                </span>
              </h1>
            </div>
            <div className="files-header-right">
              <div className="files-search-wrap">
                <SearchIcon className="files-search-icon" />
                <input
                  className="files-search"
                  type="search"
                  placeholder="Search files…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  aria-label="Search files"
                />
              </div>
              <button
                type="button"
                className="files-upload-btn"
                onClick={() => setShowUpload(true)}
              >
                <UploadIcon width={14} height={14} />
                Upload New
              </button>
            </div>
          </div>

          {/* Empty state — no files */}
          {files.length === 0 ? (
            <div className="files-empty">
              <svg
                className="files-empty-icon"
                viewBox="0 0 80 80"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <rect x="10" y="6" width="46" height="58" rx="4" strokeWidth="1.5" stroke="rgba(148,163,184,0.35)" />
                <line x1="22" y1="22" x2="44" y2="22" strokeWidth="1.2" stroke="rgba(148,163,184,0.25)" />
                <line x1="22" y1="30" x2="44" y2="30" strokeWidth="1.2" stroke="rgba(148,163,184,0.25)" />
                <line x1="22" y1="38" x2="36" y2="38" strokeWidth="1.2" stroke="rgba(148,163,184,0.25)" />
                <circle cx="58" cy="58" r="18" fill="rgba(37,99,235,0.1)" stroke="rgba(37,99,235,0.45)" strokeWidth="1.5" />
                <polyline points="50 60 55 54 62 62" stroke="#60a5fa" strokeWidth="2" />
                <line x1="55" y1="54" x2="55" y2="67" stroke="#60a5fa" strokeWidth="2" />
              </svg>
              <h2 className="files-empty-heading">No files yet</h2>
              <p className="files-empty-sub">
                Upload a document to start chatting with it instantly.
              </p>
              <button
                type="button"
                className="files-upload-btn"
                onClick={() => setShowUpload(true)}
              >
                Upload your first file
              </button>
            </div>

          /* Empty state — no search results */
          ) : filteredFiles.length === 0 ? (
            <div className="files-empty">
              <svg
                className="files-empty-icon"
                viewBox="0 0 80 80"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <circle cx="36" cy="36" r="22" strokeWidth="1.5" stroke="rgba(148,163,184,0.35)" />
                <line x1="52" y1="52" x2="70" y2="70" strokeWidth="3" stroke="rgba(148,163,184,0.35)" />
                <line x1="28" y1="36" x2="44" y2="36" strokeWidth="1.5" stroke="rgba(148,163,184,0.5)" />
              </svg>
              <h2 className="files-empty-heading">No results for "{search}"</h2>
              <button
                type="button"
                className="files-clear-btn"
                onClick={() => setSearch("")}
              >
                Clear search
              </button>
            </div>

          /* File table */
          ) : (
            <>
              <div className="files-table">
                <div className="files-table-head">
                  <span aria-hidden="true" />
                  <span>Filename</span>
                  <span>Size</span>
                  <span>Status</span>
                  <span>Actions</span>
                </div>
                {filteredFiles.map((file) => (
                  <div
                    key={file.id}
                    className={`files-table-row${confirmDeleteId === file.id ? " row-confirm" : ""}`}
                  >
                    <span className="files-icon-cell">{fileIcon(file.filename)}</span>
                    <span className="files-filename" title={file.filename}>
                      {file.filename}
                    </span>
                    <span className="files-size">{formatSize(file.filesize)}</span>
                    <StatusBadge status={file.ingestion_status} />

                    <div className="files-actions">
                      {confirmDeleteId === file.id ? (
                        <>
                          <span className="files-confirm-label">Delete?</span>
                          <button
                            type="button"
                            className="files-action-btn files-confirm-yes"
                            onClick={() => void handleDelete(file.id)}
                          >
                            Yes
                          </button>
                          <button
                            type="button"
                            className="files-action-btn files-confirm-no"
                            onClick={cancelDelete}
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          {file.ingestion_status === "COMPLETE" && (
                            <button
                              type="button"
                              className="files-action-btn files-chat"
                              onClick={() => void handleChatClick(file.id)}
                            >
                              <ChatBubbleIcon />
                              <span className="btn-label">Chat</span>
                            </button>
                          )}
                          <button
                            type="button"
                            className="files-action-btn files-download"
                            onClick={() => void downloadFile(file.id, file.filename)}
                            aria-label={`Download ${file.filename}`}
                          >
                            <DownloadIcon />
                            <span className="btn-label">Download</span>
                          </button>
                          <button
                            type="button"
                            className="files-action-btn files-delete"
                            onClick={() => requestDelete(file.id)}
                            aria-label={`Delete ${file.filename}`}
                          >
                            <TrashIcon />
                            <span className="btn-label">Delete</span>
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {search && (
                <p className="files-search-count">
                  {filteredFiles.length} of {files.length} files
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default Files;
