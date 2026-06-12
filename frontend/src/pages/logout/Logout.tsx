import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { tokenStore } from "../../api/axios";

type LogoutProps = {
  onLogout: () => void;
};

export default function Logout({ onLogout }: LogoutProps) {
  useEffect(() => {
    tokenStore.clear();
    onLogout();
  }, [onLogout]);

  return <Navigate to="/" replace />;
}
