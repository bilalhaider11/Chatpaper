import "./Chatbot.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { fetchCurrentUser, tokenStore, User } from "../../api/axios";
import FileUpload from "../../components/fileUpload/FileUpload";
import { DeleteIcon, EditIcon } from "../../components/icons/ActionIcons";
import { useChatWebSocket } from "../../hooks/useChatWebSocket";
import { getFiles } from "../../services/files_api";
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
  const [hasUploadedFile, setHasUploadedFile] = useState(false);
  const [messages, setMessages] = useState<Conversation[]>([]);
  const [liveMessages, setLiveMessages] = useState<LiveMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [creatingChat, setCreatingChat] = useState(false);

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
        if (list.length > 0) {
          setHasUploadedFile(true);
        } else {
          const files = await getFiles();
          setHasUploadedFile(files.length > 0);
          setisopen(true);
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
        } catch {
          // conv not found or belongs to another user
          navigate("/chat", { replace: true });
        }
      } else if (conversations.length > 0) {
        // No ID in URL — redirect to first conversation
        navigate(`/chat/${conversations[0].id}`, { replace: true });
      }
      // No URL ID and no conversations: stay at /chat, upload modal is open
    };

    void run();
    // conversations is accessed here but intentionally not a dep: it is read
    // only in the "no URL ID" branch which fires on the same render batch as
    // init (when loading flips to false), so it is never stale in that path.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlId, loading, navigate]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [displayedMessages]);

  // Selecting a conversation = update the URL; the Loader handles the rest
  const handleSelectConversation = (conversationListId: number) => {
    navigate(`/chat/${conversationListId}`);
  };

  const handleStartChat = () => {
    setisopen(true);
  };

  const handleSend = async (event?: { preventDefault(): void }) => {
    event?.preventDefault();
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

  const handleUploadSuccess = async () => {
    try {
      setHasUploadedFile(true);
      const list = await loadConversationList();
      if (list.length > 0) {
        setisopen(false);
        navigate(`/chat/${list[0].id}`);
      }
    } catch (error) {
      console.error("Failed to start chat after upload:", error);
      throw error;
    }
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
          {!selectedConversationId && displayedMessages.length === 0 ? (
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
          <div ref={messagesEndRef} />
        </section>

        <footer className="chatbot-input">
          <form onSubmit={(event) => void handleSend(event)}>
            <input
              placeholder={
                wsStatus === "failed" ? "Connection lost — refresh to reconnect" :
                wsStatus !== "connected" ? "Connecting…" :
                "Type your message…"
              }
              value={input}
              onChange={(event) => setInput(event.target.value)}
              disabled={isStreaming || creatingChat || wsStatus !== "connected"}
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming || creatingChat || wsStatus !== "connected"}
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
