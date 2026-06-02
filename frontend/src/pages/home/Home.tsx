import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import FileUpload from "../../components/fileUpload/FileUpload";
import { fetchCurrentUser, tokenStore, User } from "../../api/axios";

type HomeProps = {
  onLogout: () => void;
};

const actionBtnClass =
  "rounded-lg border border-slate-400/30 bg-slate-900/70 px-3 py-2 text-sm text-slate-200 no-underline cursor-pointer hover:bg-slate-800/80";

function Home({ onLogout }: HomeProps) {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

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
        navigate("/login", { replace: true });
      } finally {
        setLoading(false);
      }
    };

    void bootstrap();
  }, [navigate]);

  const handleStartChat = () => {
    navigate("/chatbot");
  };

  const logout = () => {
    tokenStore.clear();
    onLogout();
    navigate("/login", { replace: true });
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 p-6 text-slate-200">
        Loading...
      </div>
    );
  }

  return (
    <div className="box-border flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 p-6 sm:p-10">
      <div className="grid w-full max-w-[1050px] overflow-hidden rounded-3xl border border-slate-400/25 bg-slate-900/80 shadow-[0_30px_60px_rgba(2,6,23,0.5)] md:grid-cols-[1.2fr_1fr]">
        <div className="p-6 sm:p-10">
          <div className="mb-4 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
            <span className="inline-block rounded-full border border-blue-500/45 bg-blue-500/15 px-3.5 py-2 text-xs font-semibold text-blue-300">
              File Processing Platform
            </span>
            <div className="flex flex-wrap items-center gap-2.5">
              <button type="button" className={actionBtnClass} onClick={() => void handleStartChat()}>
                Start chat
              </button>
              <Link to="/chatbot" className={actionBtnClass}>
                Open chatbot
              </Link>
              <button type="button" className={actionBtnClass} onClick={logout}>
                Logout
              </button>
            </div>
          </div>

          <h1 className="mb-4 text-[clamp(1.9rem,4vw,2.9rem)] leading-tight text-slate-50">
            Welcome to <span className="text-blue-400">Celestial Technologies</span>
          </h1>
          <p className="text-sm text-blue-300">Logged in as: {user?.email}</p>

          <p className="mt-4 text-base leading-relaxed text-slate-300">
            We build secure and scalable digital solutions that help businesses
            automate workflows, process files efficiently, and deliver reliable
            modern user experiences.
          </p>

          <ul className="mt-5 flex flex-col gap-2.5">
            {[
              "Secure file uploads with trusted workflows",
              "Fast cloud-ready processing pipeline",
              "Enterprise-grade architecture and support",
            ].map((item) => (
              <li
                key={item}
                className="relative pl-5 text-[0.95rem] leading-relaxed text-slate-200 before:absolute before:left-0 before:top-[0.46em] before:h-2 before:w-2 before:rounded-full before:bg-blue-400 before:content-['']"
              >
                {item}
              </li>
            ))}
          </ul>

          {message ? <p className="mt-4 text-sm text-blue-300">{message}</p> : null}
        </div>

       { /*<div className="flex items-center border-t border-slate-400/20 p-6 sm:border-t-0 sm:border-l sm:p-10">
          <FileUpload
            variant="embedded"
            showFileList
            subtitle="Upload a file on the chatbot page to start a conversation. Each chat requires its own upload."
          /> 
        </div>*/}
      </div>
    </div>
  );
}

export default Home;
