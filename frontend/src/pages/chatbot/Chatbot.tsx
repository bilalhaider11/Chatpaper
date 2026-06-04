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

const sidebarBtnClass =
  "w-full cursor-pointer rounded-[10px] border border-white/10 bg-transparent px-3 py-2.5 text-[0.95rem] text-[#ececec] transition-colors hover:bg-blue-900/10 disabled:cursor-not-allowed disabled:opacity-60";

function Chatbot() {
  const { conversationId: urlId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const openUploadOnLoad =
    (location.state as { openUpload?: boolean } | null)?.openUpload === true;

  const [editingId, setEditingId] = useState(0);
  const [editTitle, setEditTitle] = useState("");
  const [isopen, setisopen] = useState(openUploadOnLoad);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [user, setUser] = useState<User | null>(null);
  const [input, setInput] = useState("");
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);
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
              ? { ...m, statement: m.statement + event.chunk, streaming: true }
              : m
          );
        }
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
      setLiveMessages((prev) => prev.filter((m) => !m.streaming && !m.pending));
    }
  }, []);

  const { sendMessage: sendWsMessage, status: wsStatus } = useChatWebSocket({
    chatListId: selectedConversationId,
    onEvent: handleWsEvent,
    enabled: !loading,
  });

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

  useEffect(() => {
    if (loading) return;

    const parsedId = urlId !== undefined ? parseInt(urlId, 10) : null;
    if (parsedId !== null && isNaN(parsedId)) {
      navigate("/chat", { replace: true });
      return;
    }

    const run = async () => {
      if (parsedId !== null) {
        if (selectedConvRef.current === parsedId) return;
        try {
          setSelectedConversationId(parsedId);
          const page = await getConversation(parsedId);
          setMessages(page.messages);
          setLiveMessages([]);
        } catch {
          navigate("/chat", { replace: true });
        }
      } else if (conversations.length > 0) {
        navigate(`/chat/${conversations[0].id}`, { replace: true });
      }
    };

    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlId, loading, navigate]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [displayedMessages]);

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
        const files = await getFiles();
        const fileId = files[0]?.id;
        if (!fileId) {
          setisopen(true);
          return;
        }
        const newConversation = await createConversationList(fileId);
        setConversations((prev) => [newConversation, ...prev]);
        conversationListId = newConversation.id;
        setSelectedConversationId(newConversation.id);
        selectedConvRef.current = newConversation.id;
        navigate(`/chat/${newConversation.id}`, { replace: true });
      } finally {
        setCreatingChat(false);
      }
    }

    if (!conversationListId) return;

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
        {
          tempId: "pending-ai",
          user_type: "system" as const,
          statement: "",
          streaming: true,
          pending: true,
        },
      ]);
    }
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
    <div className="grid h-screen overflow-hidden bg-[#1a1b27] text-[#ececec] md:grid-cols-[minmax(260px,26vw)_1fr]">
      <aside className="hidden min-h-0 flex-col overflow-hidden border-r border-white/10 bg-[#1b2338] p-4 md:flex">
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

        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto overflow-x-hidden pr-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {conversations.length === 0 ? (
            <p className="m-0 px-2.5 py-2.5 text-sm text-[#8e8ea0]">
              No conversations yet. Start a new chat.
            </p>
          ) : (
            conversations.map((conversation) => {
              const isActive = conversation.id === selectedConversationId;
              return (
                <div
                  key={conversation.id}
                  role="button"
                  tabIndex={0}
                  className={`group flex w-full cursor-pointer items-center gap-2.5 rounded-[10px] px-3 py-2.5 text-left transition-colors ${
                    isActive
                      ? "bg-blue-300/10"
                      : "bg-transparent hover:bg-sky-200/10"
                  }`}
                  onClick={() => handleSelectConversation(conversation.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ")
                      handleSelectConversation(conversation.id);
                  }}
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
                      <div
                        className={`ml-auto flex shrink-0 items-center gap-1 transition-opacity ${
                          isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                        }`}
                      >
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
                </div>
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

      <main className="grid min-h-0 grid-rows-[auto_1fr_auto] overflow-hidden">
        <header className="flex items-center justify-between gap-4 border-b border-white/10 px-6 py-4">
          <div>
            <h1 className="m-0 text-[1.05rem] font-semibold">
              {activeConversation?.conversation_title ?? "Assistant"}
            </h1>
            <span className="text-sm text-[#8e8ea0]">{user?.email}</span>
          </div>
          <div className="flex items-center gap-2">
            {wsStatus === "failed" && (
              <span className="rounded-full bg-red-900/40 px-2.5 py-1 text-xs text-red-300">
                Connection lost
              </span>
            )}
            {wsStatus === "connecting" && (
              <span className="rounded-full bg-amber-900/40 px-2.5 py-1 text-xs text-amber-200">
                Connecting…
              </span>
            )}
          </div>
        </header>

        <section className="flex min-h-0 flex-col gap-5 overflow-y-auto p-7 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
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
              <p className="mb-5">
                Start a new chat or select a conversation from the sidebar.
              </p>
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
                    {isUser ? "You" : "Assistant"}
                  </div>
                  <div
                    className={`break-words rounded-[14px] px-3.5 py-3 leading-relaxed ${
                      isUser
                        ? "rounded-tr-sm bg-[#031055] text-white"
                        : "rounded-tl-sm bg-[#2f2f2f]"
                    } ${message.streaming ? "border border-[#6994e6]/35" : ""}`}
                  >
                    {message.pending ? (
                      <span className="inline-flex gap-1.5">
                        <span className="size-2 animate-bounce rounded-full bg-[#8e8ea0] [animation-delay:0ms]" />
                        <span className="size-2 animate-bounce rounded-full bg-[#8e8ea0] [animation-delay:150ms]" />
                        <span className="size-2 animate-bounce rounded-full bg-[#8e8ea0] [animation-delay:300ms]" />
                      </span>
                    ) : (
                      <>
                        {message.statement}
                        {message.streaming ? (
                          <span className="ml-0.5 inline-block animate-blink">▍</span>
                        ) : null}
                      </>
                    )}
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
              placeholder={
                wsStatus === "failed"
                  ? "Connection lost — refresh to reconnect"
                  : wsStatus !== "connected"
                    ? "Connecting…"
                    : "Type your message…"
              }
              value={input}
              onChange={(event) => setInput(event.target.value)}
              disabled={isStreaming || creatingChat || wsStatus !== "connected"}
              className="flex-1 rounded-full border border-white/10 bg-[#2f2f2f] px-[18px] py-3.5 text-[#ececec] outline-none focus:border-sky-200/60 disabled:opacity-55"
            />
            <button
              type="submit"
              disabled={
                !input.trim() ||
                isStreaming ||
                creatingChat ||
                wsStatus !== "connected"
              }
              className="cursor-pointer rounded-full border-0 bg-[#052b72] px-[22px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-55"
            >
              {wsStatus === "connecting" || wsStatus === "disconnected"
                ? "Connecting…"
                : "Send"}
            </button>
          </form>
        </footer>
      </main>
    </div>
  );
}

export default Chatbot;
