import { Navigate, Route, Routes, useSearchParams } from "react-router-dom";
import { useState } from "react";
import Landing from "./pages/landing/Landing";
import Home from "./pages/home/Home";
import ForgotPassword from "./pages/login/ForgotPassword";
import Login from "./pages/login/Login";
import ResetPassword from "./pages/login/ResetPassword";
import Chatbot from "./pages/chatbot/Chatbot";
import Files from "./pages/files/Files";
import Settings from "./pages/settings/Settings";
import Logout from "./pages/logout/Logout";
import TermsOfService from "./pages/legal/TermsOfService";
import PrivacyPolicy from "./pages/legal/PrivacyPolicy";
import SharedConversation from "./pages/share/SharedConversation";
import NotFound from "./pages/notfound/NotFound";
import ProtectedRoute from "./components/ProtectedRoute";
import { tokenStore } from "./api/axios";

function AuthenticatedRedirect() {
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next");
  return <Navigate to={next?.startsWith("/") ? next : "/dashboard"} replace />;
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(
    Boolean(tokenStore.getToken())
  );

  const handleLogout = () => setIsAuthenticated(false);
  const hasSession = isAuthenticated && Boolean(tokenStore.getToken());

  return (
    <Routes>
      {/* Public landing page — always visible; authenticated users redirected to dashboard */}
      <Route
        path="/"
        element={hasSession ? <Navigate to="/dashboard" replace /> : <Landing />}
      />
      <Route
        path="/login"
        element={
          hasSession ? (
            <AuthenticatedRedirect />
          ) : (
            <Login onLoginSuccess={() => setIsAuthenticated(true)} />
          )
        }
      />
      <Route
        path="/forgot-password"
        element={
          hasSession ? <Navigate to="/dashboard" replace /> : <ForgotPassword />
        }
      />
      <Route
        path="/reset-password"
        element={
          hasSession ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <ResetPassword onLoginSuccess={() => setIsAuthenticated(true)} />
          )
        }
      />
      <Route path="/logout" element={<Logout onLogout={handleLogout} />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Home onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/chat"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Chatbot onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/chat/:conversationId"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Chatbot onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/files"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Files onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <Settings onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/conversation/share/:shareId"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <SharedConversation />
          </ProtectedRoute>
        }
      />
      {/* Public legal pages */}
      <Route path="/terms" element={<TermsOfService />} />
      <Route path="/privacy" element={<PrivacyPolicy />} />

      {/* Authenticated users hitting unknown routes go to dashboard; everyone else sees 404 */}
      <Route
        path="*"
        element={hasSession ? <NotFound /> : <Navigate to="/login" replace />}
      />
    </Routes>
  );
}

export default App;