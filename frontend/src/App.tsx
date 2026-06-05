import { Navigate, Route, Routes } from "react-router-dom";
import { useState } from "react";
import Home from "./pages/home/Home";
import Login from "./pages/login/Login";
import Chatbot from "./pages/chatbot/Chatbot";
import Files from "./pages/files/Files";
import Settings from "./pages/settings/Settings";
import { tokenStore } from "./api/axios";

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(
    Boolean(tokenStore.getToken())
  );

  const handleLogout = () => setIsAuthenticated(false);

  return (
    <Routes>
      <Route
        path="/login"
        element={
          isAuthenticated ? (
            <Navigate to="/" replace />
          ) : (
            <Login onLoginSuccess={() => setIsAuthenticated(true)} />
          )
        }
      />
      <Route
        path="/"
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
      <Route
        path="*"
        element={<Navigate to={isAuthenticated ? "/" : "/login"} replace />}
      />
    </Routes>
  );
}

export default App;