import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import logo from "../../assets/logo.png";
import { fetchCurrentUser, tokenStore, User } from "../../api/axios";
import { FileRecord, getFiles } from "../../services/files_api";
import FileUpload from "../../components/fileUpload/FileUpload";
import { LogoutIcon } from "../../components/icons/Icons";
import "./Home.css";

type HomeProps = {
  onLogout: () => void;
};

type Panel =
  | { kind: "loading" }
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
        <Link to="/chat" className="hp-tracking-link">Open Chat</Link>
        <Link to="/files" className="hp-tracking-link hp-tracking-link-secondary">My Files</Link>
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
        <Link to="/chat" className="hp-panel-btn hp-panel-btn-secondary">Open Chat</Link>
      </div>
    </div>
  );
}

function Home({ onLogout }: HomeProps) {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [panel, setPanel] = useState<Panel>({ kind: "loading" });
  const [showUpload, setShowUpload] = useState(false);

  const isTerminal = (s: string | null) =>
    s === "COMPLETE" || s === "FAILED_PERMANENT";

  useEffect(() => {
    const bootstrap = async () => {
      if (!tokenStore.getToken()) {
        navigate("/login", { replace: true });
        return;
      }
      try {
        const [currentUser] = await Promise.all([fetchCurrentUser(), getFiles()]);
        setUser(currentUser);
        setPanel({ kind: "files" });
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
    onLogout(); // sets isAuthenticated=false in App → route guard redirects to /login
  };

  if (loading) return <div className="home-page">Loading…</div>;

  const renderPanel = () => {
    switch (panel.kind) {
      case "loading":
        return <div className="upload-card"><p className="upload-card-subtitle">Loading…</p></div>;
      case "tracking":
        return <TrackingPanel file={panel.file} />;
      case "files":
        return <FilesPanel />;
    }
  };

  return (
    <div className="home-page">
      {showUpload && (
        <FileUpload
          variant="modal"
          onClose={() => setShowUpload(false)}
          onUploadSuccess={(file) => {
            if (file.conversation_id) {
              navigate(`/chat/${file.conversation_id}`);
            } else {
              setPanel({ kind: "tracking", file });
            }
          }}
        />
      )}

      <nav className="home-navbar">
        <img src={logo} alt="Chatpaper" className="home-logo" />
        <button type="button" className="home-nav-logout" onClick={logout}>
          <LogoutIcon width={14} height={14} />
          Logout
        </button>
      </nav>

      <div className="home-content">
        <div className="home-hero">
          <div className="home-glow" />
          <p className="home-greeting">Welcome back</p>
          <h1 className="home-title">
            Hello, <span>{user?.email?.split("@")[0]}</span>
          </h1>
          <p className="home-subtitle">
            Your documents are ready to chat. Ask questions, find answers, and surface insights, instantly.
          </p>
          <div className="home-ctas">
            <Link to="/chat" className="home-cta-primary">Open Chat →</Link>
            <button
              type="button"
              className="home-cta-secondary"
              onClick={() => setShowUpload(true)}
            >
              Upload Document
            </button>
          </div>
        </div>

        <div className="home-panel">
          {renderPanel()}
        </div>
      </div>
    </div>
  );
}

export default Home;
