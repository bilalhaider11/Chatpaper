import "./Chatbot.css";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchCurrentUser, tokenStore, User } from "../../api/axios";
import SystemMessageModal from "../../components/chatbot/SystemMessageModal";
import FileUpload from "../../components/fileUpload/FileUpload";
import { DeleteIcon, EditIcon } from "../../components/icons/ActionIcons";
import { useChatWebSocket } from "../../hooks/useChatWebSocket";
import { getFiles } from "../../services/files_api";
import {
  ChatWsEvent,
  Conversation,
  ConversationListItem,
  createConversationList,
  getConversation,
  getConversationList,
  LiveMessage,
  normalizeUserType,
  deleteConversationList,
  editConversationListTitle,
} from "../../services/conversation_api";

function Chatbot() {
  const [editingId, setEditingId] = useState(0);
  const [editTitle, setEditTitle] = useState("");
  const [isopen, setisopen] = useState(false);
  const [systemModalOpen, setSystemModalOpen] = useState(false);
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [user, setUser] = useState<User | null>(null);
  const [input, setInput] = useState("");
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(
    null
  );
  const [hasUploadedFile, setHasUploadedFile] = useState(false);
  const [messages, setMessages] = useState<Conversation[]>([]);
  const [liveMessages, setLiveMessages] = useState<LiveMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [creatingChat, setCreatingChat] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendingSystem, setSendingSystem] = useState(false);

  const loadConversationList = async () => {
    const list = await getConversationList();
    setConversations(list);
    return list;
  };

  const loadMessages = async (conversationListId: number) => {
    const data = await getConversation(conversationListId);
    setMessages(data);
    setLiveMessages([]);
  };

  const handleWsEvent = useCallback((event: ChatWsEvent) => {
    if (event.type === "error") return;

    if (event.type === "message") {
      setLiveMessages((prev) => {
        if (prev.some((item) => item.tempId === event.temp_id)) return prev;
        return [
          ...prev,
          {
            tempId: event.temp_id,
            user_type: normalizeUserType(event.user_type),
            statement: event.statement,
          },
        ];
      });
      return;
    }

    if (event.type === "chunk") {
      setLiveMessages((prev) => {
        const index = prev.findIndex((item) => item.tempId === event.temp_id);
        if (index >= 0) {
          const next = [...prev];
          next[index] = {
            ...next[index],
            statement: next[index].statement + event.chunk,
            streaming: true,
          };
          return next;
        }
        return [
          ...prev,
          {
            tempId: event.temp_id,
            user_type: "system",
            statement: event.chunk,
            streaming: true,
          },
        ];
      });
      return;
    }

    if (event.type === "done") {
      setLiveMessages((prev) => {
        const index = prev.findIndex((item) => item.tempId === event.temp_id);
        if (index >= 0) {
          const next = [...prev];
          next[index] = {
            ...next[index],
            statement: event.statement,
            streaming: false,
            id: event.id,
          };
          return next;
        }
        return [
          ...prev,
          {
            tempId: event.temp_id,
            user_type: "system",
            statement: event.statement,
          },
        ];
      });
    }
  }, []);

  const { sendMessage: sendWsMessage } = useChatWebSocket({
    chatListId: selectedConversationId,
    onEvent: handleWsEvent,
    enabled: Boolean(selectedConversationId),
  });

  const displayedMessages = useMemo(() => {
    const persisted = messages.map((message) => ({
      key: `db-${message.id}`,
      user_type: normalizeUserType(message.user_type),
      statement: message.statement,
      streaming: false,
    }));

    const live = liveMessages.map((message) => ({
      key: message.tempId,
      user_type: message.user_type,
      statement: message.statement,
      streaming: Boolean(message.streaming),
    }));

    return [...persisted, ...live];
  }, [messages, liveMessages]);

  useEffect(() => {
    const bootstrap = async () => {
      if (!tokenStore.getToken()) {
        navigate("/login", { replace: true });
        return;
      }

      try {
        const currentUser = await fetchCurrentUser();
        setUser(currentUser);
        const list = await loadConversationList();
        if (list.length > 0) {
          setHasUploadedFile(true);
          setisopen(false);
          setSelectedConversationId(list[0].id);
          await loadMessages(list[0].id);
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

    void bootstrap();
  }, [navigate]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [displayedMessages]);

  const handleSelectConversation = async (conversationListId: number) => {
    setSelectedConversationId(conversationListId);
    await loadMessages(conversationListId);
  };

  const handleStartChat = async () => {
    if (!hasUploadedFile) {
      setisopen(true);
      return;
    }

    setCreatingChat(true);
    try {
      const newConversation = await createConversationList();
      setConversations((prev) => [newConversation, ...prev]);
      setSelectedConversationId(newConversation.id);
      setMessages([]);
      setLiveMessages([]);
    } finally {
      setCreatingChat(false);
    }
  };

  const sendChatMessage = async (
    text: string,
    userType: "user" | "system",
    setBusy: (value: boolean) => void
  ) => {
    if (!text.trim() || sending || sendingSystem) return;

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
        setSelectedConversationId(newConversation.id);
      } finally {
        setCreatingChat(false);
      }
    }

    setBusy(true);

    const sent = sendWsMessage(text, userType);
    if (!sent) {
      setBusy(false);
      return;
    }

    if (userType === "user") {
      setInput("");
    }

    setBusy(false);
  };

  const handleSend = async (event?: FormEvent) => {
    event?.preventDefault();
    const text = input.trim();
    if (!text) return;
    await sendChatMessage(text, "user", setSending);
  };

  const handleSystemSend = async (text: string) => {
    await sendChatMessage(text, "system", setSendingSystem);
  };

  const logout = () => {
    tokenStore.clear();
    navigate("/login", { replace: true });
  };

  const handleDelete = async (id: number) => {
    await deleteConversationList(id);
    const list = await loadConversationList();
    if (selectedConversationId === id) {
      const nextId = list[0]?.id ?? null;
      setSelectedConversationId(nextId);
      if (nextId) {
        await loadMessages(nextId);
      } else {
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
        setSelectedConversationId(list[0].id);
        setMessages([]);
        setLiveMessages([]);
        await loadMessages(list[0].id);
        setisopen(false);
      }
    } catch (error) {
      console.error("Failed to start chat after upload:", error);
      throw error;
    }
  };

  const handleSaveEdit = async (e: React.FormEvent, id: number) => {
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
              <button
                key={conversation.id}
                type="button"
                className={`conversation-item${conversation.id === selectedConversationId ? " active" : ""}`}
                onClick={() => void handleSelectConversation(conversation.id)}
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
              </button>
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
          <button
            type="button"
            className="system-msg-btn"
            onClick={() => setSystemModalOpen(true)}
            disabled={!selectedConversationId || creatingChat}
          >
            System message
          </button>
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
                className={`chat-msg ${message.user_type === "user" ? "user" : "system"}${message.streaming ? " streaming" : ""
                  }`}
              >
                <div className="chat-msg-label">
                  {message.user_type === "user" ? "You" : "System"}
                </div>
                <div className="chat-msg-content">
                  {message.statement}
                  {message.streaming ? <span className="stream-cursor">▍</span> : null}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </section>

        <footer className="chatbot-input">
          <form onSubmit={(event) => void handleSend(event)}>
            <input
              placeholder="Type your message..."
              value={input}
              onChange={(event) => setInput(event.target.value)}
              disabled={sending || creatingChat}
            />
            <button type="submit" disabled={!input.trim() || sending || creatingChat}>
              Send
            </button>
          </form>
        </footer>
      </main>

      <SystemMessageModal
        open={systemModalOpen}
        onClose={() => setSystemModalOpen(false)}
        onSend={handleSystemSend}
        sending={sendingSystem}
      />
    </div>
  );
}

export default Chatbot;
