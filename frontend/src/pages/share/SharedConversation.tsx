import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { importSharedConversation } from "../../services/conversation_api";
import "./SharedConversation.css";

export default function SharedConversation() {
  const { shareId } = useParams<{ shareId: string }>();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = Number(shareId);
    if (!shareId || Number.isNaN(id)) {
      setError("Invalid share link.");
      return;
    }

    let cancelled = false;

    importSharedConversation(id)
      .then((result) => {
        if (cancelled) return;
        navigate(`/chat/${result.conversation_list.id}`, { replace: true });
      })
      .catch((err: { response?: { data?: { detail?: string } } }) => {
        if (cancelled) return;
        const detail = err?.response?.data?.detail;
        setError(typeof detail === "string" ? detail : "Unable to open this shared conversation.");
      });

    return () => {
      cancelled = true;
    };
  }, [shareId, navigate]);

  if (error) {
    return (
      <div className="shared-conversation-page">
        <div className="shared-conversation-card shared-conversation-card--error">
          <h1>Shared conversation unavailable</h1>
          <p>{error}</p>
          <button type="button" onClick={() => navigate("/chat", { replace: true })}>
            Go to chats
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="shared-conversation-page">
      <div className="shared-conversation-card">
        <div className="shared-conversation-spinner" aria-hidden />
        <h1>Opening shared conversation…</h1>
        <p>Importing messages into your account.</p>
      </div>
    </div>
  );
}
