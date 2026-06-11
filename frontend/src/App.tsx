import { Navigate, Route, Routes } from "react-router-dom";
import { useState } from "react";
import Landing from "./pages/landing/Landing";
import Home from "./pages/home/Home";
import ForgotPassword from "./pages/login/ForgotPassword";
import Login from "./pages/login/Login";
import ResetPassword from "./pages/login/ResetPassword";
import Chatbot from "./pages/chatbot/Chatbot";
import Files from "./pages/files/Files";
import Settings from "./pages/settings/Settings";
import TermsOfService from "./pages/legal/TermsOfService";
import PrivacyPolicy from "./pages/legal/PrivacyPolicy";
import NotFound from "./pages/notfound/NotFound";
import { tokenStore } from "./api/axios";

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(
    Boolean(tokenStore.getToken())
  );

  const handleLogout = () => setIsAuthenticated(false);

  return (
    <Routes>
      {/* Public landing page — always visible; authenticated users redirected to dashboard */}
      <Route
        path="/"
        element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Landing />}
      />
      <Route
        path="/login"
        element={
          isAuthenticated ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <Login onLoginSuccess={() => setIsAuthenticated(true)} />
          )
        }
      />
      <Route
        path="/forgot-password"
        element={
          isAuthenticated ? <Navigate to="/dashboard" replace /> : <ForgotPassword />
        }
      />
      <Route
        path="/reset-password"
        element={
          isAuthenticated ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <ResetPassword onLoginSuccess={() => setIsAuthenticated(true)} />
          )
        }
      />
      <Route
        path="/forgot-password"
        element={
          isAuthenticated ? <Navigate to="/dashboard" replace /> : <ForgotPassword />
        }
      />
      
      <Route
        path="/reset-password"
        element={
          isAuthenticated ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <ResetPassword onLoginSuccess={() => setIsAuthenticated(true)} />
          )
        }
      />
      <Route
        path="/dashboard"
        element={isAuthenticated ? <Home onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/chat"
        element={isAuthenticated ? <Chatbot onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/chat/:conversationId"
        element={isAuthenticated ? <Chatbot onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/files"
        element={isAuthenticated ? <Files onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/settings"
        element={isAuthenticated ? <Settings onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      {/* Public legal pages */}
      <Route path="/terms" element={<TermsOfService />} />
      <Route path="/privacy" element={<PrivacyPolicy />} />

      {/* Authenticated users hitting unknown routes go to dashboard; everyone else sees 404 */}
      <Route
        path="*"
        element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <NotFound />}
      />
    </Routes>
  );
}

export default App;