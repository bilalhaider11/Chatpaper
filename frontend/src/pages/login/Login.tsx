import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { exchangeOAuthCode, login, signup } from "../../api/axios";
import { tokenStore } from "../../api/axios";
import { GoogleAuthButton } from "../../components/login/google_auth";
import logo from "../../assets/logo.png";
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
  const [mode, setMode] = useState<"login" | "signup">("login");

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

  const switchMode = (next: "login" | "signup") => {
    if (next === mode) return;
    setMode(next);
    setError("");
  };

  const handleSubmit = async (event: { preventDefault(): void }) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    const isSignup = mode === "signup";

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

  const isLogin = mode === "login";

  return (
    <div className="login-page">
      <div className="login-glow" />
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-brand">
          <img src={logo} alt="" className="login-logo" />
          <span className="login-brand-name">Chatpaper</span>
        </div>

        <div className="login-tabs">
          <button
            type="button"
            className={`login-tab${isLogin ? " login-tab-active" : ""}`}
            onClick={() => switchMode("login")}
            disabled={loading}
          >
            Sign in
          </button>
          <button
            type="button"
            className={`login-tab${!isLogin ? " login-tab-active" : ""}`}
            onClick={() => switchMode("signup")}
            disabled={loading}
          >
            Create account
          </button>
        </div>

        <p className="login-subtitle">
          {isLogin
            ? "Welcome back — sign in to continue."
            : "New here? Create your account in seconds."}
        </p>

        <div className="login-fields">
          <input
            type="email"
            placeholder="Email address"
            className="login-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          <input
            type="password"
            placeholder="Password"
            className="login-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete={isLogin ? "current-password" : "new-password"}
          />
        </div>

        {error && <p className="login-error">{error}</p>}

        <button type="submit" className="login-submit-btn" disabled={loading}>
          {loading
            ? isLogin ? "Signing in…" : "Creating account…"
            : isLogin ? "Sign in" : "Create account"}
        </button>

        <div className="login-divider">or</div>
        <GoogleAuthButton disabled={loading} />
      </form>
    </div>
  );
}

export default Login;
