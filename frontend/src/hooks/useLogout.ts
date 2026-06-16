import { useCallback } from "react";
import { flushSync } from "react-dom";
import { useNavigate } from "react-router-dom";
import { tokenStore } from "../api/axios";

export function performLogout(
  onLogout: () => void,
  navigate: (path: string, options?: { replace?: boolean }) => void
) {
  tokenStore.clear();
  flushSync(() => {
    onLogout();
  });
  navigate("/", { replace: true });
}

export function useLogout(onLogout: () => void) {
  const navigate = useNavigate();
  return useCallback(() => {
    performLogout(onLogout, navigate);
  }, [navigate, onLogout]);
}
