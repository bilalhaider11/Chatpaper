import { useCallback, useEffect, useRef } from "react";
import { getChatWebSocketUrl, ChatWsEvent } from "../services/conversation_api";

type UseChatWebSocketOptions = {
  chatListId: number | null;
  onEvent: (event: ChatWsEvent) => void;
  enabled?: boolean;
};

export function useChatWebSocket({
  chatListId,
  onEvent,
  enabled = true,
}: UseChatWebSocketOptions) {
  const socketRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const sendMessage = useCallback(
    (statement: string, userType: "user" | "system") => {
      if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
        return false;
      }
      socketRef.current.send(
        JSON.stringify({
          action: "send",
          statement,
          user_type: userType,
        })
      );
      return true;
    },
    []
  );

  useEffect(() => {
    if (!enabled || !chatListId) {
      return;
    }

    const url = getChatWebSocketUrl(chatListId);
    const socket = new WebSocket(url);
    socketRef.current = socket;

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as ChatWsEvent;
        onEventRef.current(payload);
      } catch {
        // ignore malformed payloads
      }
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [chatListId, enabled]);

  return { sendMessage };
}
