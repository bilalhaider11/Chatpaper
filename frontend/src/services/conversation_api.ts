import { api } from "../api/axios";

export type Conversation = {
  id: number;
  chat_id: number;
  user_type: string;
  statement: string;
};

export type ConversationListItem = {
  id: number;
  conversation_title: string;
  is_active: boolean;
};

export type ConversationPayload = {
  statement: string;
  user_type: string;
};

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

export async function createConversationList() {
  const response = await api.post<ConversationListItem>(
    "/conversation/inconversationlist"
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

export async function deleteConversationList(conversationListid:number){

  const response = await api.delete(`/conversation/delete_list/${conversationListid}`)
  return response.data;
}

export async function editConversationListTitle(list_id:number, title:string){
  
  const response = await api.patch(`/conversation/conversation-title/${list_id}`,{title} )
  return response.data;
}