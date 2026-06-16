import { useEffect } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { performLogout } from "../../hooks/useLogout";

type LogoutProps = {
  onLogout: () => void;
};

export default function Logout({ onLogout }: LogoutProps) {
  const navigate = useNavigate();

  useEffect(() => {
    performLogout(onLogout, navigate);
  }, [navigate, onLogout]);

  return <Navigate to="/" replace />;
}
