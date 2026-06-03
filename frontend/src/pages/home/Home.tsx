import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import FileUpload from "../../components/fileUpload/FileUpload";
import "./Home.css";
import { fetchCurrentUser, tokenStore, User } from "../../api/axios";

type HomeProps = {
  onLogout: () => void;
};

function Home({ onLogout }: HomeProps) {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const bootstrap = async () => {
      if (!tokenStore.getToken()) {
        navigate("/login", { replace: true });
        return;
      }
      try {
        const currentUser = await fetchCurrentUser();
        setUser(currentUser);
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
          <FileUpload
            variant="embedded"
            showFileList
            subtitle="Files are saved in backend `/files` and metadata is stored in DB."
          />
        </div>
      </div>
    </div>
  );
}

export default Home;
