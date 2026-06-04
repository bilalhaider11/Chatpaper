import { api, apiOrigin, tokenStore } from "../api/axios";

export type Conversation = {
  id: number | null;
  chat_id?: number | null;
  temp_id?: string | null;
  created_at?: string | null;
  user_type: string;
  statement: string;
  streaming?: boolean;
};

export type ConversationListItem = {
  id: number;
  file_id: number;
  conversation_title: string;
  is_active: boolean;
};

export type ConversationPayload = {
  statement: string;
  user_type: "user" | "system";
};

export type ChatWsEvent =
  | { type: "ping" }
  | {
      type: "message";
      temp_id: string;
      user_type: "user" | "system";
      statement: string;
      chat_id: number;
      id?: number;
      created_at?: string;
    }
  | {
      type: "chunk";
      temp_id: string;
      user_type: "system";
      chunk: string;
      chat_id: number;
      created_at?: string;
    }
  | {
      type: "done";
      temp_id: string;
      user_type: "system";
      statement: string;
      citations: Citation[];
      chat_id: number;
      id?: number;
      created_at?: string;
    }
  | {
      type: "error";
      detail: string;
    };

export type LiveMessage = {
  tempId: string;
  id?: number;
  user_type: "user" | "system";
  statement: string;
  streaming?: boolean;
  created_at?: string;
  /** True while waiting for the first chunk — shows typing indicator */
  pending?: boolean;
};

export function getChatWebSocketUrl(chatListId: number) {
  const wsBase = apiOrigin().replace(/^http/, "ws");
  const token = tokenStore.getToken();
  return `${wsBase}/api/conversation/ws/${chatListId}?token=${encodeURIComponent(token ?? "")}`;
}

export function normalizeUserType(userType: string): "user" | "system" {
  const value = userType.toLowerCase();
  if (value === "system" || value === "assistant") return "system";
  return "user";
}

export type ConversationPageResponse = {
  messages: Conversation[];
  next_cursor_id: number | null;
};

export async function getConversationList() {
  const response = await api.get<ConversationListItem[]>(
    "/conversation/get_conversation_list"
  );
  return response.data;
}

export async function getConversation(
  conversationListId: number,
  cursorId?: number | null,
  limit: number = 25
) {
  const response = await api.get<ConversationPageResponse>(
    `/conversation/get-conversation/${conversationListId}`,
    {
      params: {
        cursor_id: cursorId ?? undefined,
        limit,
      },
    }
  );
  return response.data;
}

export async function postConversationChat(
  conversationListId: number,
  chat: ConversationPayload
) {
  const response = await api.post<Conversation>(
    `/conversation/conversation/${conversationListId}`,
    chat
  );
  return response.data;
}

export async function createConversationList(fileId: number) {
  const response = await api.post<ConversationListItem>(
    "/conversation/inconversationlist",
    { file_id: fileId }
  );
  return response.data;
}

export async function updateConversationTitle(
  conversationId: number,
  conversationTitle: string
) {
  const response = await api.patch(
    `/conversation/conversation-title/${conversationId}`,
    { conversation_title: conversationTitle }
  );
  return response.data;
}

export async function deleteConversationList(conversationListid: number) {
  const response = await api.delete(
    `/conversation/delete_list/${conversationListid}`
  );
  return response.data;
}

export async function editConversationListTitle(list_id: number, title: string) {
  const response = await api.patch(
    `/conversation/conversation-title/${list_id}`,
    { conversation_title: title }
  );
  return response.data;
}

export type Citation = {
  file_id: number;
  filename: string;
  page_start: number | null;
  page_end: number | null;
  content_preview: string;
};

export type AskResponse = {
  answer: string;
  citations: Citation[];
  conversation_id: number;
};

export async function askQuestion(conversationId: number, question: string) {
  const response = await api.post<AskResponse>(`/chat/${conversationId}/ask`, { question });
  return response.data;
}
