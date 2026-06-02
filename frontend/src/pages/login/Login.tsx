import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { exchangeOAuthCode, login, signup } from "../../api/axios";
import { tokenStore } from "../../api/axios";
import { GoogleAuthButton } from "../../components/login/google_auth";
import "./Login.css";

type LoginProps = {
  onLoginSuccess: () => void;
};

function Login({ onLoginSuccess }: LoginProps) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  // Ref instead of state: read synchronously inside handleSubmit before re-render.
  const actionRef = useRef<"login" | "signup">("login");

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code) return;

    setLoading(true);
    setSearchParams({}, { replace: true });
    exchangeOAuthCode(code)
      .then((data) => {
        tokenStore.setToken(data.access_token);
        onLoginSuccess();
        navigate("/", { replace: true });
      })
      .catch(() => setError("Google sign-in failed. Please try again."))
      .finally(() => setLoading(false));
  }, [searchParams, setSearchParams, onLoginSuccess, navigate]);

  const handleSubmit = async (event: { preventDefault(): void }) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    const isSignup = actionRef.current === "signup";

    try {
      if (isSignup) {
        await signup(email, password);
      }
      const login_res = await login(email, password);
      tokenStore.setToken(login_res.access_token);
      onLoginSuccess();
      navigate("/", { replace: true });
    } catch (err: any) {
      const status = err?.response?.status;
      if (isSignup && status === 400) {
        setError("Email already registered.");
      } else if (isSignup && status === 403) {
        setError("Registration is currently closed.");
      } else {
        setError("Invalid credentials. Please try again.");
      }
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
        <button type="submit" onClick={() => { actionRef.current = "login"; }} disabled={loading}>
          {loading ? "Signing in..." : "Login"}
        </button>
        <button type="submit" onClick={() => { actionRef.current = "signup"; }} disabled={loading}>
          {loading ? "Signing up..." : "Signup"}
        </button>
        <div className="login-divider">or</div>
        <GoogleAuthButton disabled={loading} />
        </>
      </form>
    </div>
  );
}

export default Login;
