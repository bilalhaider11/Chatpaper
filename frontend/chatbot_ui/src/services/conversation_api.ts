import axios from "axios";
import {api} from "../api/axios"
const API_BASE_URL = "http://127.0.0.1:8000/api";
const TOKEN_KEY = "auth_token";

export type Conversation = {
  id: number;
  chat_id:number;
  user_type: string;
  statement: string;
};

export type conversationList = {
  id: number;
  conversation_title: string;
  is_active: boolean;
};


export async function getConversationList() {
  const response = await api.get<conversationList[]>("/conversation/get_conversation_list");
  return response.data;
}

export async function getConversation(chat_list_id:number){
    const response = await api.get<Conversation[]>(`/conversation/get-conversation/${chat_list_id}`);
    return response.data

}
