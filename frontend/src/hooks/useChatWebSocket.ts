import { useCallback, useEffect, useRef, useState } from "react";
import { tokenStore } from "../api/axios";
import { ChatWsEvent, getChatWebSocketUrl } from "../services/conversation_api";

export type WsStatus = "disconnected" | "connecting" | "connected" | "failed";

type Options = {
  chatListId: number | null;
  onEvent: (event: ChatWsEvent) => void;
  enabled?: boolean;
};

const MAX_ATTEMPTS = 10;

export function useChatWebSocket({ chatListId, onEvent, enabled = true }: Options) {
  const wsRef = useRef<WebSocket | null>(null);
  const attemptsRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onEventRef = useRef(onEvent);
  const [status, setStatus] = useState<WsStatus>("disconnected");

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!enabled || !chatListId) return;

    let intentionalClose = false;

    const connect = () => {
      const token = tokenStore.getToken();
      if (!token) return;

      setStatus("connecting");
      const ws = new WebSocket(getChatWebSocketUrl(chatListId));
      wsRef.current = ws;

      ws.onopen = () => {
        attemptsRef.current = 0;
        ws.send(JSON.stringify({ action: "auth", token }));
        setStatus("connected");
      };

      ws.onmessage = (event) => {
        let data: ChatWsEvent;
        try {
          data = JSON.parse(event.data as string) as ChatWsEvent;
        } catch {
          return;
        }
        if (data.type === "ping") return;
        onEventRef.current(data);
      };

      ws.onclose = () => {
        // Guard: a newer connection may already own wsRef — don't overwrite it
        if (wsRef.current === ws) wsRef.current = null;
        if (intentionalClose) return;
        if (attemptsRef.current >= MAX_ATTEMPTS) {
          setStatus("failed");
          return;
        }
        setStatus("disconnected");
        // Exponential backoff: 1s → 2s → 4s → … → 30s max
        const delay = Math.min(1000 * 2 ** attemptsRef.current, 30_000);
        attemptsRef.current += 1;
        retryTimerRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        // onclose fires after onerror; reconnect logic lives there
      };
    };

    connect();

    return () => {
      intentionalClose = true;
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
      attemptsRef.current = 0;
      setStatus("disconnected");
    };
  }, [chatListId, enabled]);

  const sendMessage = useCallback((statement: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "send", statement }));
      return true;
    }
    return false;
  }, []);

  return { sendMessage, status };
}
