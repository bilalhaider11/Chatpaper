import { Navigate, Route, Routes } from "react-router-dom";
import { useState } from "react";
import Home from "./pages/home/Home";
import Login from "./pages/login/Login";
import Chatbot from "./pages/chatbot/Chatbot";
import { tokenStore } from "./api/axios";

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(
    Boolean(tokenStore.getToken())
  );

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
        element={<Home onLogout={() => setIsAuthenticated(false)} />}
      />
      <Route
        path="/chat"
        element={isAuthenticated ? <Chatbot /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/chat/:conversationId"
        element={isAuthenticated ? <Chatbot /> : <Navigate to="/login" replace />}
      />
      <Route
        path="*"
        element={<Navigate to={isAuthenticated ? "/" : "/login"} replace />}
      />
    </Routes>
  );
}

export default App;