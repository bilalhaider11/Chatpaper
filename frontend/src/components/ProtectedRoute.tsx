import { Navigate, useLocation } from "react-router-dom";

type ProtectedRouteProps = {
  isAuthenticated: boolean;
  children: React.ReactNode;
};

export default function ProtectedRoute({ isAuthenticated, children }: ProtectedRouteProps) {
  const location = useLocation();

  if (isAuthenticated) {
    return <>{children}</>;
  }

  const next = `${location.pathname}${location.search}`;
  return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
}
