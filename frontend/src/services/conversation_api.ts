import { api, API_BASE_URL } from "../api/axios";

export type Conversation = {
  id: number;
  chat_id?: number;
  user_type: string;
  statement: string;
};

export type ConversationListItem = {
  id: number;
  conversation_title: string;
  is_active: boolean;
  conversation_type: string;
  file_id: number | null;
  shared_conversation_id: number | null;
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
    }
  | {
      type: "chunk";
      temp_id: string;
      user_type: "system";
      chunk: string;
      chat_id: number;
    }
  | {
      type: "done";
      temp_id: string;
      user_type: "system";
      statement: string;
      citations: Citation[];
      chat_id: number;
      id?: number;
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
  /** True while waiting for the first chunk — shows typing indicator */
  pending?: boolean;
};

export function getChatWebSocketUrl(chatListId: number) {
  const wsBase = API_BASE_URL.replace(/^http/, "ws").replace(/\/api$/, "");
  return `${wsBase}/api/conversation/ws/${chatListId}`;
}

export function normalizeUserType(userType: string): "user" | "system" {
  const value = userType.toLowerCase();
  if (value === "system" || value === "assistant") return "system";
  return "user";
}

export async function getConversationList() {
  const response = await api.get<ConversationListItem[]>(
    "/conversation/get_conversation_list"
  );
  return response.data;
}

export async function getConversation(conversationListId: number) {
  const response = await api.get<Conversation[]>(
    `/conversation/get-conversation/${conversationListId}`
  );
  return response.data;
}

export type CreateConversationListPayload = {
  conversation_title?: string;
  conversation_type: "global";
};

export async function createConversationList(
  payload: CreateConversationListPayload = { conversation_type: "global" }
) {
  const response = await api.post<ConversationListItem>(
    "/conversation/inconversationlist",
    payload
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
    { title }
  );
  return response.data;
}

export async function shareConversation(conversationListId: number) {
  const response = await api.post<{ share_url: string; shared_id: number }>(
    `/conversation/share/${conversationListId}`
  );
  return response.data;
}

export type ImportSharedConversationResponse = {
  conversation_list: ConversationListItem;
  already_imported: boolean;
  messages_imported: number;
};

export async function importSharedConversation(sharedId: number) {
  const response = await api.get<ImportSharedConversationResponse>(
    `/conversation/shared/${sharedId}`
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