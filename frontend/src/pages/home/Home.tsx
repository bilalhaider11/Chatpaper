import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import { fetchCurrentUser, tokenStore, User } from "../../api/axios";
import { ACCEPTED_FILE_TYPES } from "../../services/file_config";
import { FileRecord, getApiErrorMessage, getFiles, uploadFile } from "../../services/files_api";
import "./Home.css";

type HomeProps = {
  onLogout: () => void;
};

type Panel =
  | { kind: "loading" }
  | { kind: "upload" }
  | { kind: "progress"; filename: string; percent: number }
  | { kind: "tracking"; file: FileRecord }
  | { kind: "files" };

function StatusBadge({ status }: { status: string | null }) {
  if (!status || status === "QUEUED") return <span className="hp-badge hp-badge-queued">Queued</span>;
  if (status.startsWith("STAGE_")) {
    const n = status.split("_")[1];
    return <span className="hp-badge hp-badge-processing">Processing {n}/6</span>;
  }
  if (status === "COMPLETE") return <span className="hp-badge hp-badge-complete">Ready</span>;
  if (status === "FAILED_RETRYABLE") return <span className="hp-badge hp-badge-retrying">Retrying</span>;
  return <span className="hp-badge hp-badge-failed">Failed</span>;
}

function UploadPanel({ onUploaded }: { onUploaded: (file: FileRecord) => void }) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState("");
  const inFlightRef = useRef(false);

  const onDrop = useCallback((accepted: File[]) => {
    setSelectedFile(accepted[0] ?? null);
    setError("");
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: ACCEPTED_FILE_TYPES,
  });

  const handleUpload = async () => {
    if (!selectedFile || inFlightRef.current) return;
    inFlightRef.current = true;
    setUploading(true);
    setProgress(0);
    setError("");
    try {
      const record = await uploadFile(selectedFile, setProgress);
      onUploaded(record);
    } catch (err) {
      setError(getApiErrorMessage(err, "Upload failed. Please try again."));
      setUploading(false);
      setProgress(null);
      inFlightRef.current = false;
    }
  };

  if (uploading) {
    return (
      <div className="upload-card">
        <h2 className="upload-card-title">Uploading…</h2>
        <p className="upload-card-subtitle">{selectedFile?.name}</p>
        <div className="upload-progress">
          <div className="upload-progress-track">
            <div className="upload-progress-fill" style={{ width: `${progress ?? 0}%` }} />
          </div>
          <span className="upload-progress-label">{progress ?? 0}%</span>
        </div>
      </div>
    );
  }

  return (
    <div className="upload-card">
      <h2 className="upload-card-title">Upload your file</h2>
      <p className="upload-card-subtitle">Upload a document to start chatting with it.</p>

      <div {...getRootProps()} className="dropzone">
        <input {...getInputProps()} />
        <p>{isDragActive ? "Drop the file here…" : "Drag & drop file here, or click to select"}</p>
      </div>

      {selectedFile && (
        <p className="selected-file">Selected: <strong>{selectedFile.name}</strong></p>
      )}

      <button
        type="button"
        className="upload-submit-btn"
        onClick={() => void handleUpload()}
        disabled={!selectedFile}
      >
        Upload
      </button>

      {error && <p className="upload-message">{error}</p>}
    </div>
  );
}

function TrackingPanel({ file }: { file: FileRecord }) {
  const isTerminal = (s: string | null) =>
    s === "COMPLETE" || s === "FAILED_PERMANENT";

  return (
    <div className="upload-card hp-tracking">
      <h2 className="upload-card-title">File uploaded</h2>
      <p className="upload-card-subtitle">Processing your document…</p>
      <div className="hp-tracking-row">
        <span className="hp-tracking-name" title={file.filename}>{file.filename}</span>
        <StatusBadge status={file.ingestion_status} />
      </div>
      {!isTerminal(file.ingestion_status) && (
        <p className="hp-tracking-hint">This may take a moment. You can start chatting once it's ready.</p>
      )}
      <div className="hp-tracking-actions">
        <Link to="/chat" state={{ openUpload: false }} className="hp-tracking-link">
          Open Chat
        </Link>
        <Link to="/files" className="hp-tracking-link hp-tracking-link-secondary">
          My Files
        </Link>
      </div>
    </div>
  );
}

function FilesPanel() {
  return (
    <div className="upload-card hp-files-panel">
      <h2 className="upload-card-title">Your files</h2>
      <p className="upload-card-subtitle">Manage your uploaded documents and start chatting.</p>
      <div className="hp-panel-actions">
        <Link to="/files" className="hp-panel-btn hp-panel-btn-primary">View My Files</Link>
        <Link to="/chat" className="hp-panel-btn hp-panel-btn-secondary">
          Open Chat
        </Link>
      </div>
    </div>
  );
}

function Home({ onLogout }: HomeProps) {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [panel, setPanel] = useState<Panel>({ kind: "loading" });

  const isTerminal = (s: string | null) =>
    s === "COMPLETE" || s === "FAILED_PERMANENT";

  useEffect(() => {
    const bootstrap = async () => {
      if (!tokenStore.getToken()) {
        navigate("/login", { replace: true });
        return;
      }
      try {
        const [currentUser, files] = await Promise.all([fetchCurrentUser(), getFiles()]);
        setUser(currentUser);
        setPanel(files.length > 0 ? { kind: "files" } : { kind: "upload" });
      } catch {
        tokenStore.clear();
        onLogout();
        navigate("/login", { replace: true });
      } finally {
        setLoading(false);
      }
    };
    void bootstrap();
  }, [navigate]);

  // Poll while tracking ingestion status of just-uploaded file
  useEffect(() => {
    if (panel.kind !== "tracking") return;
    if (isTerminal(panel.file.ingestion_status)) {
      setPanel({ kind: "files" });
      return;
    }
    const id = setInterval(async () => {
      try {
        const files = await getFiles();
        const updated = files.find((f) => f.id === (panel as { kind: "tracking"; file: FileRecord }).file.id);
        if (!updated || isTerminal(updated.ingestion_status)) {
          setPanel({ kind: "files" });
        } else {
          setPanel({ kind: "tracking", file: updated });
        }
      } catch {
        // ignore transient poll errors
      }
    }, 3000);
    return () => clearInterval(id);
  }, [panel]);

  const logout = () => {
    tokenStore.clear();
    onLogout();
    navigate("/login", { replace: true });
  };

  if (loading) return <div className="home-page">Loading…</div>;

  const renderPanel = () => {
    switch (panel.kind) {
      case "loading":
        return <div className="upload-card"><p className="upload-card-subtitle">Loading…</p></div>;
      case "upload":
        return <UploadPanel onUploaded={(file) => setPanel({ kind: "tracking", file })} />;
      case "progress":
        return (
          <div className="upload-card">
            <h2 className="upload-card-title">Uploading…</h2>
            <div className="upload-progress">
              <div className="upload-progress-track">
                <div className="upload-progress-fill" style={{ width: `${panel.percent}%` }} />
              </div>
              <span className="upload-progress-label">{panel.percent}%</span>
            </div>
          </div>
        );
      case "tracking":
        return <TrackingPanel file={panel.file} />;
      case "files":
        return <FilesPanel />;
    }
  };

  return (
    <div className="home-page">
      <div className="home-shell">
        <div className="home-left">
          <div className="home-topbar">
            <div className="home-badge">File Processing Platform</div>
            <div className="home-actions">
              <Link to="/chat" state={{ openUpload: true }}>Open chatbot</Link>
              <button onClick={logout}>Logout</button>
            </div>
          </div>

          <h1 className="home-title">
            Welcome to <span>Celestial Technologies</span>
          </h1>
          <p className="home-user">Logged in as: {user?.email}</p>

          <p className="home-description">
            We build secure and scalable digital solutions that help businesses
            automate workflows, process files efficiently, and deliver reliable
            modern user experiences.
          </p>

          <ul className="home-highlights">
            <li>Secure file uploads with trusted workflows</li>
            <li>Fast cloud-ready processing pipeline</li>
            <li>Enterprise-grade architecture and support</li>
          </ul>
        </div>

        <div className="home-right">
          {renderPanel()}
        </div>
      </div>
    </div>
  );
}

export default Home;
