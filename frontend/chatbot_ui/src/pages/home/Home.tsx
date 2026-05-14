import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  deleteFile,

  FileRecord,
  getFiles,
  toFileUrl,
  uploadFile,
  User,
} from "../../services/files_api";
import "./Home.css";
import { fetchCurrentUser, tokenStore } from '../../api/axios'
type HomeProps = {
  onLogout: () => void;
};

function Home({ onLogout }: HomeProps) {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");

  const loadFiles = async () => {
    const fileList = await getFiles();
    setFiles(fileList);
  };

  useEffect(() => {
    const bootstrap = async () => {
      console.log("tokenStore.getToken(): ", tokenStore.getToken())
      if (!tokenStore.getToken()) {
        navigate("/login", { replace: true });
        return;
      }
      try {
        const currentUser = await fetchCurrentUser();
        setUser(currentUser);
        await loadFiles();
      } catch {
        tokenStore.clear();
        navigate("/login", { replace: true });
      } finally {
        setLoading(false);
      }
    };

    void bootstrap();
  }, [navigate]);

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setMessage("");
    try {
      await uploadFile(selectedFile, description);
      setSelectedFile(null);
      setDescription("");
      setMessage("File uploaded successfully.");
      await loadFiles();
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

  const logout = () => {
    tokenStore.clear();
    onLogout();
    navigate("/login", { replace: true });
  };

  if (loading) {
    return <div className="home-page">Loading...</div>;
  }

  return (
    <div className="home-page">
      <div className="home-shell">
        <div className="home-left">
          <div className="home-topbar">
            <div className="home-badge">File Processing Platform</div>
            <div className="home-actions">
              <Link to="/chatbot">Chatbot UI</Link>
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
          <div className="upload-card">
            <h2 className="upload-card-title">Upload your file</h2>
            <p className="upload-card-subtitle">
              Files are saved in backend `/files` and metadata is stored in DB.
            </p>

            <input
              placeholder="file"

              type="file"
              onChange={(event) =>
                setSelectedFile(event.target.files?.[0] ?? null)
              }
            />
            <input
              type="text"
              placeholder="Description (optional)"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
            <button onClick={handleUpload} disabled={!selectedFile || uploading}>
              {uploading ? "Uploading..." : "Upload"}
            </button>
            {message ? <p className="upload-message">{message}</p> : null}

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

                    <button onClick={() => void handleDelete(file.id)}>
                      Delete
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Home;