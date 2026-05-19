import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login, signup } from "../../api/axios";
import {tokenStore} from "../../api/axios";
import "./Login.css";

type LoginProps = {
  onLoginSuccess: () => void;
};

function Login({ onLoginSuccess }: LoginProps) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [login_signup,setlogin_signup] = useState(false);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (login_signup){
        const response = await signup(email, password);

      }
      const login_res = await login(email, password);  
      tokenStore.setToken(login_res.access_token);
      onLoginSuccess();
      navigate("/", { replace: true });
      
      
    } catch {
      setError("Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>Sign in</h1>
        <p>Authenticate to access file operations and chatbot workspace.</p>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error ? <p className="login-error">{error}</p> : null}
        <>
        <button onClick={() => setlogin_signup(false)} type="submit" disabled={loading}>
          {loading ? "Signing in..." : "Login"}
        </button>
        <button onClick={() => setlogin_signup(true)} type="submit" disabled={loading}>
          {loading ? "Signing up..." : "Signup"}
        </button>
        </>
      </form>
    </div>
  );
}

export default Login;
