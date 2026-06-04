import "./Chatbot.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { fetchCurrentUser, tokenStore, User } from "../../api/axios";
import FileUpload from "../../components/fileUpload/FileUpload";
import { DeleteIcon, EditIcon, ErrorIcon } from "../../components/icons/ActionIcons";
import { useChatWebSocket } from "../../hooks/useChatWebSocket";
import { FileRecord, getFiles } from "../../services/files_api";
import {
  ChatWsEvent,
  Conversation,
  ConversationListItem,
  LiveMessage,
  createConversationList,
  deleteConversationList,
  editConversationListTitle,
  getConversation,
  getConversationList,
  normalizeUserType,
} from "../../services/conversation_api";

const PROCESSING_KEY = "chatpaper_processing_file";

function Chatbot() {
  const { conversationId: urlId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const openUploadOnLoad = (location.state as { openUpload?: boolean } | null)?.openUpload === true;

  const [editingId, setEditingId] = useState(0);
  const [editTitle, setEditTitle] = useState("");
  const [isopen, setisopen] = useState(openUploadOnLoad);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [user, setUser] = useState<User | null>(null);
  const [input, setInput] = useState("");
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);
  // Ref mirrors selectedConversationId so the Loader can check without stale closure
  const selectedConvRef = useRef<number | null>(null);
  // Stable ref holding the per-file conversation_id for the file currently being ingested.
  // Lives in a ref (not state) so it's never stale inside the polling closure.
  const processingConvIdRef = useRef<number | null>(null);
  const [hasUploadedFile, setHasUploadedFile] = useState(false);
  const [processingFile, setProcessingFile] = useState<FileRecord | null>(null);
  // File status for the currently selected per-file conversation
  const [activeFileStatus, setActiveFileStatus] = useState<FileRecord | null>(null);
  const [messages, setMessages] = useState<Conversation[]>([]);
  const [liveMessages, setLiveMessages] = useState<LiveMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [creatingChat, setCreatingChat] = useState(false);
  const [wsError, setWsError] = useState<string | null>(null);

  const isStreaming = liveMessages.some((m) => m.streaming);

  useEffect(() => {
    selectedConvRef.current = selectedConversationId;
  }, [selectedConversationId]);

  const loadConversationList = async () => {
    const list = await getConversationList();
    setConversations(list);
    return list;
  };

  const displayedMessages = useMemo(() => {
    const stripCitations = (text: string) => text.replace(/\s*\[\d+\]/g, "");

    const persisted = messages.map((message) => ({
      key: `db-${message.id}`,
      user_type: normalizeUserType(message.user_type),
      statement: stripCitations(message.statement),
      streaming: false,
      pending: false,
    }));

    const live = liveMessages.map((message) => ({
      key: message.tempId,
      user_type: message.user_type,
      statement: stripCitations(message.statement),
      streaming: Boolean(message.streaming),
      pending: Boolean(message.pending),
    }));

    return [...persisted, ...live];
  }, [messages, liveMessages]);

  const handleWsEvent = useCallback((event: ChatWsEvent) => {
    if (event.type === "chunk") {
      setLiveMessages((prev) => {
        const existing = prev.find((m) => m.tempId === event.temp_id);
        if (existing) {
          return prev.map((m) =>
            m.tempId === event.temp_id
              ? { ...m, statement: event.chunk }
              : m
          );
        }
        // First chunk — remove pending placeholder, create streaming message
        return [
          ...prev.filter((m) => !m.pending),
          {
            tempId: event.temp_id,
            user_type: "system" as const,
            statement: event.chunk,
            streaming: true,
          },
        ];
      });
    } else if (event.type === "done") {
      setLiveMessages((prev) =>
        prev.map((m) =>
          m.tempId === event.temp_id
            ? { ...m, statement: event.statement, streaming: false }
            : m
        )
      );
    } else if (event.type === "error") {
      setLiveMessages((prev) => prev.filter((m) => !m.streaming));
      setWsError("Something went wrong — please try again.");
    }
  }, []);

  const { sendMessage: sendWsMessage, status: wsStatus } = useChatWebSocket({
    chatListId: selectedConversationId,
    onEvent: handleWsEvent,
    enabled: !loading,
  });

  // Phase 1 — runs once on mount: auth, user, conversation list
  useEffect(() => {
    const init = async () => {
      if (!tokenStore.getToken()) {
        navigate("/login", { replace: true });
        return;
      }
      try {
        const currentUser = await fetchCurrentUser();
        setUser(currentUser);
        const list = await getConversationList();
        setConversations(list);

        // Restore in-progress or failed upload state across reloads
        const savedJson = sessionStorage.getItem(PROCESSING_KEY);
        let restoredFromStorage = false;
        if (savedJson) {
          try {
            const saved = JSON.parse(savedJson) as FileRecord;
            const files = await getFiles();
            const current = files.find((f) => f.id === saved.id);
            if (current && current.ingestion_status !== "COMPLETE") {
              // Restore conversation_id from the saved upload response
              processingConvIdRef.current = saved.conversation_id ?? null;
              setProcessingFile(current);
              // Persist with conversation_id so future reloads can also recover it
              sessionStorage.setItem(PROCESSING_KEY, JSON.stringify({ ...current, conversation_id: processingConvIdRef.current }));
              setHasUploadedFile(true);
              restoredFromStorage = true;
            } else {
              sessionStorage.removeItem(PROCESSING_KEY);
            }
          } catch {
            sessionStorage.removeItem(PROCESSING_KEY);
          }
        }

        if (!restoredFromStorage) {
          if (list.length > 0) {
            setHasUploadedFile(true);
          } else {
            const files = await getFiles();
            setHasUploadedFile(files.length > 0);
            setisopen(true);
          }
        }
      } catch {
        tokenStore.clear();
        navigate("/login", { replace: true });
      } finally {
        setLoading(false);
      }
    };
    void init();
  }, [navigate]);

  // Phase 2 — runs when URL param or init-loading state changes
  // Validates the conversation and loads its messages; redirects on 404 / wrong user.
  // When no conversationId in URL, auto-navigates to the first conversation.
  useEffect(() => {
    if (loading) return;

    const parsedId = urlId !== undefined ? parseInt(urlId, 10) : null;
    if (parsedId !== null && isNaN(parsedId)) {
      navigate("/chat", { replace: true });
      return;
    }

    const run = async () => {
      if (parsedId !== null) {
        if (selectedConvRef.current === parsedId) return; // already on this conv
        try {
          setSelectedConversationId(parsedId);
          const data = await getConversation(parsedId);
          setMessages(data);
          setLiveMessages([]);
          setWsError(null);
        } catch {
          // conv not found or belongs to another user
          navigate("/chat", { replace: true });
        }
      } else if (conversations.length > 0 && !processingFile && !processingConvIdRef.current) {
        navigate(`/chat/${conversations[0].id}`, { replace: true });
      }
      // No URL ID and no conversations: stay at /chat, upload modal is open
    };

    void run();
    // conversations is accessed here but intentionally not a dep: it is read
    // only in the "no URL ID" branch which fires on the same render batch as
    // init (when loading flips to false), so it is never stale in that path.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlId, loading, navigate, processingFile]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [displayedMessages]);

  const isFileTerminal = (s: string | null) =>
    s === "COMPLETE" || s === "FAILED_PERMANENT";

  // When the selected conversation changes, check if its file is ready to chat
  useEffect(() => {
    if (!selectedConversationId) { setActiveFileStatus(null); return; }
    const conv = conversations.find((c) => c.id === selectedConversationId);
    if (!conv?.file_id) { setActiveFileStatus(null); return; }
    const check = async () => {
      try {
        const files = await getFiles();
        const file = files.find((f) => f.id === conv.file_id);
        setActiveFileStatus(file && file.ingestion_status !== "COMPLETE" ? file : null);
      } catch { /* ignore */ }
    };
    void check();
    // conversations read inside but not a dep — it's always current when selectedConversationId changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedConversationId]);

  // Poll the active conversation's file status until it reaches a terminal state
  useEffect(() => {
    if (!activeFileStatus || isFileTerminal(activeFileStatus.ingestion_status)) return;
    const id = setInterval(async () => {
      try {
        const files = await getFiles();
        const updated = files.find((f) => f.id === activeFileStatus.id);
        if (!updated) { setActiveFileStatus(null); return; }
        setActiveFileStatus(updated.ingestion_status === "COMPLETE" ? null : updated);
      } catch { /* ignore */ }
    }, 3000);
    return () => clearInterval(id);
  }, [activeFileStatus]);

  // Poll ingestion status after upload; navigate to the per-file conv when ready
  useEffect(() => {
    if (!processingFile || isFileTerminal(processingFile.ingestion_status)) return;
    const id = setInterval(async () => {
      try {
        const files = await getFiles();
        const updated = files.find((f) => f.id === processingFile.id);
        if (!updated) {
          // File was deleted
          processingConvIdRef.current = null;
          setProcessingFile(null);
          sessionStorage.removeItem(PROCESSING_KEY);
          return;
        }
        if (updated.ingestion_status === "COMPLETE") {
          const convId = processingConvIdRef.current;
          // Keep ref non-null until after navigate so Phase 2 doesn't redirect to
          // conversations[0] in the gap between setProcessingFile(null) and navigate.
          setProcessingFile(null);
          sessionStorage.removeItem(PROCESSING_KEY);
          await loadConversationList();
          navigate(convId ? `/chat/${convId}` : "/chat");
          processingConvIdRef.current = null;
          return;
        }
        if (updated.ingestion_status === "FAILED_PERMANENT") {
          // Keep the card visible showing the error; stop polling by updating status
          setProcessingFile(updated);
          sessionStorage.setItem(PROCESSING_KEY, JSON.stringify({ ...updated, conversation_id: processingConvIdRef.current }));
          return;
        }
        // Still processing — update badge stage (preserve conversation_id in storage)
        setProcessingFile(updated);
        sessionStorage.setItem(PROCESSING_KEY, JSON.stringify({ ...updated, conversation_id: processingConvIdRef.current }));
      } catch {
        // ignore transient poll errors
      }
    }, 3000);
    return () => clearInterval(id);
  }, [processingFile, navigate]);

  // Selecting a conversation = update the URL; the Loader handles the rest
  const handleSelectConversation = (conversationListId: number) => {
    navigate(`/chat/${conversationListId}`);
  };

  const handleStartChat = () => {
    setisopen(true);
  };

  const handleSend = async (event?: { preventDefault(): void }) => {
    event?.preventDefault();
    setWsError(null);
    const text = input.trim();
    if (!text || isStreaming || creatingChat) return;

    let conversationListId = selectedConversationId;

    if (!conversationListId) {
      if (!hasUploadedFile) {
        setisopen(true);
        return;
      }
      setCreatingChat(true);
      try {
        const newConversation = await createConversationList();
        setConversations((prev) => [newConversation, ...prev]);
        conversationListId = newConversation.id;
        // Set state directly so the WS hook reconnects immediately,
        // and update the ref so the Loader skips re-loading this conv.
        setSelectedConversationId(newConversation.id);
        selectedConvRef.current = newConversation.id;
        navigate(`/chat/${newConversation.id}`, { replace: true });
      } finally {
        setCreatingChat(false);
      }
    }

    const userTempId = `user-${crypto.randomUUID()}`;
    setLiveMessages((prev) => [
      ...prev,
      { tempId: userTempId, user_type: "user" as const, statement: text },
    ]);
    setInput("");

    const sent = sendWsMessage(text);
    if (!sent) {
      setLiveMessages((prev) => prev.filter((m) => m.tempId !== userTempId));
      setInput(text);
    } else {
      setLiveMessages((prev) => [
        ...prev,
        { tempId: "pending-ai", user_type: "system" as const, statement: "", streaming: true, pending: true },
      ]);
    }
  };

  // System messages still use HTTP (no streaming pattern needed)
  const logout = () => {
    tokenStore.clear();
    navigate("/login", { replace: true });
  };

  const handleDelete = async (id: number) => {
    await deleteConversationList(id);
    const list = await loadConversationList();
    if (selectedConversationId === id) {
      const nextId = list[0]?.id ?? null;
      if (nextId) {
        navigate(`/chat/${nextId}`, { replace: true });
      } else {
        navigate("/chat", { replace: true });
        setMessages([]);
        setLiveMessages([]);
        const files = await getFiles();
        setHasUploadedFile(files.length > 0);
        setisopen(files.length === 0);
      }
    }
  };

  const handleStartEdit = (conversation: ConversationListItem) => {
    setEditingId(conversation.id);
    setEditTitle(conversation.conversation_title || "New chat");
  };

  const handleUploadSuccess = async (file: FileRecord) => {
    setHasUploadedFile(true);
    setisopen(false);
    const convId = file.conversation_id ?? null;
    await loadConversationList();
    if (convId) navigate(`/chat/${convId}`);
  };

  const handleSaveEdit = async (e: { preventDefault(): void }, id: number) => {
    e.preventDefault();
    if (!editTitle.trim()) return;
    try {
      await editConversationListTitle(editingId, editTitle);
      setConversations((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, conversation_title: editTitle } : item
        )
      );
      setEditingId(0);
    } catch (error) {
      console.error("Failed to update title:", error);
    }
  };

  if (loading) {
    return <div className="chatbot-loading">Loading...</div>;
  }

  const activeConversation = conversations.find(
    (item) => item.id === selectedConversationId
  );

  return (
    <div className="chatbot-page">
      <aside className="chatbot-sidebar">
        <div className="sidebar-top">
          <button
            type="button"
            className="new-chat-btn"
            onClick={() => void handleStartChat()}
            disabled={creatingChat}
          >
            + New Chat
          </button>
        </div>

        <div className="sidebar-section-label">Conversations</div>

        <nav className="conversation-list">
          {conversations.length === 0 ? (
            <p className="sidebar-empty">No conversations yet. Start a new chat.</p>
          ) : (
            conversations.map((conversation) => (
              <div
                key={conversation.id}
                role="button"
                tabIndex={0}
                className={`conversation-item${conversation.id === selectedConversationId ? " active" : ""}`}
                onClick={() => handleSelectConversation(conversation.id)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") handleSelectConversation(conversation.id); }}
              >
                {editingId === conversation.id ? (
                  <form
                    onSubmit={(e) => handleSaveEdit(e, conversation.id)}
                    onClick={(e) => e.stopPropagation()}
                    className="edit-form"
                  >
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      autoFocus
                      className="edit-input"
                    />
                    <button type="submit">Save</button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingId(0);
                      }}
                    >
                      Cancel
                    </button>
                  </form>
                ) : (
                  <>
                    <span className="conversation-title">
                      {conversation.conversation_title || "New chat"}
                    </span>
                    <div className="conversation-actions">
                      <button
                        type="button"
                        className="conversation-icon-btn edit"
                        aria-label="Edit conversation title"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStartEdit(conversation);
                        }}
                      >
                        <EditIcon />
                      </button>
                      <button
                        type="button"
                        className="conversation-icon-btn delete"
                        aria-label="Delete conversation"
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleDelete(conversation.id);
                        }}
                      >
                        <DeleteIcon />
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </nav>

        <div className="sidebar-footer">
          <Link to="/" className="sidebar-link">
            Home
          </Link>
          <button type="button" className="sidebar-logout" onClick={logout}>
            Logout
          </button>
        </div>
      </aside>

      <main className="chatbot-main">
        <header className="chatbot-header">
          <div>
            <h1>{activeConversation?.conversation_title ?? "Assistant"}</h1>
            <span>{user?.email}</span>
          </div>
          <div className="chatbot-header-actions">
            {wsStatus === "failed" && (
              <span className="ws-status-badge ws-failed">Connection lost</span>
            )}
            {wsStatus === "connecting" && (
              <span className="ws-status-badge ws-reconnecting">Connecting…</span>
            )}
          </div>
        </header>

        <section className="chatbot-messages">
          {isopen ? (
            <FileUpload
              variant="modal"
              onClose={() => setisopen(false)}
              onUploadSuccess={handleUploadSuccess}
              subtitle="Upload a document to use with this chat session."
            />
          ) : null}
          {processingFile && !selectedConversationId ? (
            <div className="chatbot-empty-state">
              <div className={`file-processing-card${processingFile.ingestion_status === "FAILED_PERMANENT" ? " file-processing-card--failed" : ""}`}>
                <p className="file-processing-name" title={processingFile.filename}>
                  {processingFile.filename}
                </p>
                <span className={`file-processing-badge${processingFile.ingestion_status === "FAILED_PERMANENT" ? " file-processing-badge--failed" : ""}`}>
                  {processingFile.ingestion_status === "FAILED_PERMANENT"
                    ? "Ingestion Failed"
                    : processingFile.ingestion_status?.startsWith("STAGE_")
                    ? `Processing ${processingFile.ingestion_status.split("_")[1]}/6…`
                    : "Processing…"}
                </span>
                <p className="file-processing-hint">
                  {processingFile.ingestion_status === "FAILED_PERMANENT"
                    ? "This file could not be processed. Delete it from My Files and try uploading again."
                    : "Your file is being ingested. Chat will open automatically when it’s ready."}
                </p>
                {processingFile.ingestion_status === "FAILED_PERMANENT" && (
                  <button
                    type="button"
                    className="file-processing-dismiss"
                    onClick={() => {
                      processingConvIdRef.current = null;
                      setProcessingFile(null);
                      sessionStorage.removeItem(PROCESSING_KEY);
                    }}
                  >
                    Dismiss
                  </button>
                )}
              </div>
            </div>
          ) : activeFileStatus ? (
            <div className="chatbot-empty-state">
              <div className={`file-processing-card${activeFileStatus.ingestion_status === "FAILED_PERMANENT" ? " file-processing-card--failed" : ""}`}>
                <p className="file-processing-name" title={activeFileStatus.filename}>
                  {activeFileStatus.filename}
                </p>
                <span className={`file-processing-badge${activeFileStatus.ingestion_status === "FAILED_PERMANENT" ? " file-processing-badge--failed" : ""}`}>
                  {activeFileStatus.ingestion_status === "FAILED_PERMANENT"
                    ? "Ingestion Failed"
                    : activeFileStatus.ingestion_status?.startsWith("STAGE_")
                    ? `Processing ${activeFileStatus.ingestion_status.split("_")[1]}/6…`
                    : "Processing…"}
                </span>
                <p className="file-processing-hint">
                  {activeFileStatus.ingestion_status === "FAILED_PERMANENT"
                    ? "This file could not be processed. Delete it from My Files and try uploading again."
                    : "This file is still being processed. Chat will be available when it’s ready."}
                </p>
                {activeFileStatus.ingestion_status === "FAILED_PERMANENT" && (
                  <button
                    type="button"
                    className="file-processing-dismiss"
                    onClick={() => setActiveFileStatus(null)}
                  >
                    Dismiss
                  </button>
                )}
              </div>
            </div>
          ) : !selectedConversationId && displayedMessages.length === 0 ? (
            <div className="chatbot-empty-state">
              <h2>How can I help you today?</h2>
              <p>Start a new chat or select a conversation from the sidebar.</p>
              <button
                type="button"
                className="start-chat-btn"
                onClick={() => void handleStartChat()}
                disabled={creatingChat}
              >
                Start chat
              </button>
            </div>
          ) : displayedMessages.length === 0 ? (
            <div className="chatbot-empty-state compact">
              <p>Send a message to begin this conversation.</p>
            </div>
          ) : (
            displayedMessages.map((message) => (
              <div
                key={message.key}
                className={`chat-msg ${message.user_type === "user" ? "user" : "system"}${message.streaming ? " streaming" : ""}`}
              >
                <div className="chat-msg-label">
                  {message.user_type === "user" ? "You" : "Assistant"}
                </div>
                <div className="chat-msg-content">
                  {message.pending ? (
                    <span className="typing-dots">
                      <span /><span /><span />
                    </span>
                  ) : (
                    <>
                      {message.statement}
                      {message.streaming ? <span className="stream-cursor">▍</span> : null}
                    </>
                  )}
                </div>
              </div>
            ))
          )}
          {wsError && (
            <div className="ws-error-banner">
              <ErrorIcon className="ws-error-icon" />
              {wsError}
            </div>
          )}
          <div ref={messagesEndRef} />
        </section>

        <footer className="chatbot-input">
          <form onSubmit={(event) => void handleSend(event)}>
            <input
              placeholder={
                processingFile || activeFileStatus ? "Waiting for file to finish processing…" :
                wsStatus === "failed" ? "Connection lost — refresh to reconnect" :
                wsStatus !== "connected" ? "Connecting…" :
                "Type your message…"
              }
              value={input}
              onChange={(event) => setInput(event.target.value)}
              disabled={!!processingFile || !!activeFileStatus || isStreaming || creatingChat || wsStatus !== "connected"}
            />
            <button
              type="submit"
              disabled={!!processingFile || !!activeFileStatus || !input.trim() || isStreaming || creatingChat || wsStatus !== "connected"}
            >
              {wsStatus === "connecting" || wsStatus === "disconnected" ? "Connecting…" : "Send"}
            </button>
          </form>
        </footer>
      </main>

    </div>
  );
}

export default Chatbot;
