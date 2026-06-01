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

const sidebarBtnClass =
  "w-full cursor-pointer rounded-[10px] border border-white/10 bg-transparent px-3 py-2.5 text-[0.95rem] text-[#ececec] transition-colors hover:bg-blue-900/10 disabled:cursor-not-allowed disabled:opacity-60";

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
        const index = prev.findIndex((item) => item.tempId === event.temp_id);
        if (index >= 0) {
          const next = [...prev];
          next[index] = {
            ...next[index],
            user_type: normalizeUserType(event.user_type),
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
    return (
      <div className="grid min-h-screen place-items-center bg-[#162438] text-[#ececec]">
        Loading...
      </div>
    );
  }

  const activeConversation = conversations.find(
    (item) => item.id === selectedConversationId
  );

  return (
    <div className="grid min-h-screen bg-[#1a1b27] text-[#ececec] md:grid-cols-[260px_1fr]">
      <aside className="hidden min-h-screen flex-col border-r border-white/10 bg-[#1b2338] p-3 md:flex">
        <div className="mb-3">
          <button
            type="button"
            className={sidebarBtnClass}
            onClick={() => void handleStartChat()}
            disabled={creatingChat}
          >
            + New Chat
          </button>
        </div>

        <div className="px-2.5 pb-1.5 pt-2 text-xs uppercase tracking-wider text-[#8e8ea0]">
          Conversations
        </div>

        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto pr-0.5">
          {conversations.length === 0 ? (
            <p className="m-0 px-2.5 py-2.5 text-sm text-[#8e8ea0]">
              No conversations yet. Start a new chat.
            </p>
          ) : (
            conversations.map((conversation) => {
              const isActive = conversation.id === selectedConversationId;
              return (
                <button
                  key={conversation.id}
                  type="button"
                  className={`flex w-full cursor-pointer items-center gap-2.5 rounded-[10px] border-0 px-3 py-2.5 text-left transition-colors ${
                    isActive
                      ? "bg-blue-300/10"
                      : "bg-transparent hover:bg-sky-200/10"
                  }`}
                  onClick={() => void handleSelectConversation(conversation.id)}
                >
                  {editingId === conversation.id ? (
                    <form
                      onSubmit={(e) => handleSaveEdit(e, conversation.id)}
                      onClick={(e) => e.stopPropagation()}
                      className="flex w-full items-center gap-1.5"
                    >
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        autoFocus
                        className="min-w-0 flex-1 rounded-md border border-white/15 bg-[#2f2f2f] px-2 py-1 text-sm text-[#ececec] outline-none"
                      />
                      <button
                        type="submit"
                        className="cursor-pointer rounded-md border border-white/10 bg-transparent px-2 py-1 text-xs text-[#ececec]"
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        className="cursor-pointer rounded-md border border-white/10 bg-transparent px-2 py-1 text-xs text-[#ececec]"
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
                      <span className="min-w-0 flex-1 truncate text-sm">
                        {conversation.conversation_title || "New chat"}
                      </span>
                      <div className="ml-auto flex shrink-0 items-center gap-1">
                        <button
                          type="button"
                          className="inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-md border-0 bg-transparent p-0 text-[#6994e6] hover:bg-white/10 hover:text-[#93b4f5]"
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
                          className="inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-md border-0 bg-transparent p-0 text-[#e57373] hover:bg-white/10 hover:text-[#ef9a9a]"
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
              );
            })
          )}
        </nav>

        <div className="mt-3 flex flex-col gap-2 border-t border-sky-700/10 pt-3">
          <Link
            to="/"
            className="rounded-lg px-2.5 py-2 text-left text-sm text-[#c5c5d2] no-underline hover:bg-white/10"
          >
            Home
          </Link>
          <button
            type="button"
            className="cursor-pointer rounded-lg border-0 bg-transparent px-2.5 py-2 text-left text-sm text-[#c5c5d2] hover:bg-white/10"
            onClick={logout}
          >
            Logout
          </button>
        </div>
      </aside>

      <main className="grid min-h-screen grid-rows-[auto_1fr_auto]">
        <header className="flex items-center justify-between gap-4 border-b border-white/10 px-6 py-4">
          <div>
            <h1 className="m-0 text-[1.05rem] font-semibold">
              {activeConversation?.conversation_title ?? "Assistant"}
            </h1>
            <span className="text-sm text-[#8e8ea0]">{user?.email}</span>
          </div>
          <button
            type="button"
            className="cursor-pointer whitespace-nowrap rounded-[10px] border border-[#6994e6]/45 bg-[#052b72]/35 px-3.5 py-2 text-sm text-[#c9dcff] hover:bg-[#052b72]/60 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => setSystemModalOpen(true)}
            disabled={!selectedConversationId || creatingChat}
          >
            System message
          </button>
        </header>

        <section className="flex flex-col gap-4 overflow-y-auto p-6">
          {isopen ? (
            <FileUpload
              variant="modal"
              onClose={() => setisopen(false)}
              onUploadSuccess={handleUploadSuccess}
              subtitle="Upload a document to use with this chat session."
            />
          ) : null}
          {!selectedConversationId && displayedMessages.length === 0 ? (
            <div className="m-auto max-w-[420px] text-center text-[#c5c5d2]">
              <h2 className="mb-2 text-2xl text-[#ececec]">How can I help you today?</h2>
              <p className="mb-5">Start a new chat or select a conversation from the sidebar.</p>
              <button
                type="button"
                className={`${sidebarBtnClass} mx-auto min-w-[140px] w-auto`}
                onClick={() => void handleStartChat()}
                disabled={creatingChat}
              >
                Start chat
              </button>
            </div>
          ) : displayedMessages.length === 0 ? (
            <div className="mx-auto mt-10 max-w-[420px] text-center text-[#c5c5d2]">
              <p>Send a message to begin this conversation.</p>
            </div>
          ) : (
            displayedMessages.map((message) => {
              const isUser = message.user_type === "user";
              return (
                <div
                  key={message.key}
                  className={`flex max-w-[72%] flex-col gap-1 sm:max-w-[90%] ${
                    isUser ? "self-end" : "self-start"
                  }`}
                >
                  <div
                    className={`px-1 text-xs text-[#8e8ea0] ${
                      isUser ? "text-right" : "text-left"
                    }`}
                  >
                    {isUser ? "You" : "System"}
                  </div>
                  <div
                    className={`break-words rounded-[14px] px-3.5 py-3 leading-relaxed ${
                      isUser
                        ? "rounded-tr-sm bg-[#031055] text-white"
                        : "rounded-tl-sm bg-[#2f2f2f]"
                    } ${message.streaming ? "border border-[#6994e6]/35" : ""}`}
                  >
                    {message.statement}
                    {message.streaming ? (
                      <span className="ml-0.5 inline-block animate-blink">▍</span>
                    ) : null}
                  </div>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </section>

        <footer className="border-t border-white/10 bg-[#212121] px-6 pb-6 pt-4">
          <form
            onSubmit={(event) => void handleSend(event)}
            className="mx-auto flex max-w-[900px] gap-2.5"
          >
            <input
              placeholder="Type your message..."
              value={input}
              onChange={(event) => setInput(event.target.value)}
              disabled={sending || creatingChat}
              className="flex-1 rounded-full border border-white/10 bg-[#2f2f2f] px-[18px] py-3.5 text-[#ececec] outline-none focus:border-sky-200/60"
            />
            <button
              type="submit"
              disabled={!input.trim() || sending || creatingChat}
              className="cursor-pointer rounded-full border-0 bg-[#052b72] px-[22px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-55"
            >
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
