import "./Chatbot.css";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchCurrentUser, tokenStore, User } from "../../api/axios";
import {
  Conversation,
  ConversationListItem,
  createConversationList,
  getConversation,
  getConversationList,
  postConversationChat,
  deleteConversationList,
  editConversationListTitle
} from "../../services/conversation_api";

function Chatbot() {

  // Inside your component:
  const [editingId, setEditingId] = useState(Number);
  const [editTitle, setEditTitle] = useState("");

  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [user, setUser] = useState<User | null>(null);
  const [input, setInput] = useState("");
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(
    null
  );
  const [messages, setMessages] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [creatingChat, setCreatingChat] = useState(false);
  const [sending, setSending] = useState(false);

  const loadConversationList = async () => {
    const list = await getConversationList();
    setConversations(list);
    return list;
  };

  const loadMessages = async (conversationListId: number) => {
    const data = await getConversation(conversationListId);
    setMessages(data);
  };

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
          setSelectedConversationId(list[0].id);
          await loadMessages(list[0].id);
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
  }, [messages]);

  const handleSelectConversation = async (conversationListId: number) => {
    setSelectedConversationId(conversationListId);
    await loadMessages(conversationListId);
  };

  const handleStartChat = async () => {
    setCreatingChat(true);
    try {
      const newConversation = await createConversationList();
      setConversations((prev) => [newConversation, ...prev]);
      setSelectedConversationId(newConversation.id);
      setMessages([]);
    } finally {
      setCreatingChat(false);
    }
  };

  const handleSend = async (event?: FormEvent) => {
    event?.preventDefault();

    const text = input.trim();
    if (!text || sending) return;

    let conversationListId = selectedConversationId;

    if (!conversationListId) {
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

    setSending(true);
    setInput("");

    try {
      await postConversationChat(conversationListId!, {
        statement: text,
        user_type: "client",
      });
      await loadMessages(conversationListId!);
      await loadConversationList();
    } catch {
      setInput(text);
    } finally {
      setSending(false);
    }
  };

  const logout = () => {
    tokenStore.clear();
    navigate("/login", { replace: true });
  };

  const handleDelete = (id: number) => {

    deleteConversationList(id);
  };


  const handleStartEdit = (conversation) => {
    setEditingId(conversation.id);
    setEditTitle(conversation.conversation_title || "New chat");
  };

  // Saves the input and closes the form
  const handleSaveEdit = async (e, id:number) => {
    e.preventDefault();

    if (!editTitle.trim()) return;

    try {
      editConversationListTitle(editingId,editTitle)
      setConversations(prev =>
        prev.map(item => item.id === id ? { ...item, conversation_title: editTitle } : item)
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
                  /* Inline 1-Field Edit Form */
                  <form
                    onSubmit={(e) => handleSaveEdit(e, conversation.id)}
                    onClick={(e) => e.stopPropagation()} // Prevents selecting the conversation while typing
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
                    <button type="button" onClick={(e) => { e.stopPropagation(); setEditingId(0); }}>Cancel</button>
                  </form>
                ) : (
                  /* Normal View Mode */
                  <>
                    <span className="conversation-title">
                      {conversation.conversation_title || "New chat"}
                    </span>
                    <div className="action-buttons" style={{ display: 'flex', marginLeft: 'auto' }}>
                      <span className="delete-button" onClick={(e) => { e.stopPropagation(); handleDelete(conversation.id); }}>  Delete  </span>
                      <span className="edit-button" onClick={(e) => { e.stopPropagation(); handleStartEdit(conversation); }}> Edit </span>
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
        </header>

        <section className="chatbot-messages">
          {!selectedConversationId && messages.length === 0 ? (
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
          ) : messages.length === 0 ? (
            <div className="chatbot-empty-state compact">
              <p>Send a message to begin this conversation.</p>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`chat-msg ${message.user_type === "client" ? "assistant" : "client"
                  }`}
              >

                <div className="chat-msg-content">{message.statement}</div>
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
    </div>
  );
}

export default Chatbot;
