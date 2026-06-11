import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { exchangeOAuthCode, login, signup, tokenStore } from "../../api/axios";
import { GoogleAuthButton } from "../../components/login/google_auth";
import { isValidName, NAME_REQUIREMENTS, normalizeName } from "../../utils/Validations";
import { isValidPassword, PASSWORD_REQUIREMENTS } from "../../utils/Validations";
import logo from "../../assets/logo.png";
import "./Login.css";

type LoginProps = {
  onLoginSuccess: () => void;
};

type FieldErrors = { name: string; email: string; password: string; general: string };
const NO_ERRORS: FieldErrors = { name: "", email: "", password: "", general: "" };

function Login({ onLoginSuccess }: LoginProps) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>(NO_ERRORS);
  const [mode, setMode] = useState<"login" | "signup">(
    () => new URLSearchParams(window.location.search).get("mode") === "signup" ? "signup" : "login"
  );

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code) return;

    setLoading(true);
    setSearchParams({}, { replace: true });
    exchangeOAuthCode(code)
      .then((data) => {
        tokenStore.setToken(data.access_token);
        onLoginSuccess();
        navigate("/dashboard", { replace: true });
      })
      .catch(() => setErrors({ ...NO_ERRORS, general: "Google sign-in failed. Please try again." }))
      .finally(() => setLoading(false));
  }, [searchParams, setSearchParams, onLoginSuccess, navigate]);

  const switchMode = (next: "login" | "signup") => {
    if (next === mode) return;
    setMode(next);
    setName("");
    setEmail("");
    setPassword("");
    setErrors(NO_ERRORS);
  };

  const handleSubmit = async (event: { preventDefault(): void }) => {
    event.preventDefault();
    const isSignup = mode === "signup";
    const next: FieldErrors = { ...NO_ERRORS };

    if (isSignup) {
      if (!name.trim()) {
        next.name = "Name is required.";
      } else if (!isValidName(name)) {
        next.name = NAME_REQUIREMENTS;
      }
    }

    if (!email.trim()) {
      next.email = "Email is required.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      next.email = "Please enter a valid email address.";
    }

    if (!password) {
      next.password = "Password is required.";
    } else if (isSignup && !isValidPassword(password)) {
      next.password = PASSWORD_REQUIREMENTS;
    }

    if (next.name || next.email || next.password) {
      setErrors(next);
      return;
    }

    setLoading(true);
    setErrors(NO_ERRORS);

    try {
      if (isSignup) {
        await signup(email, password, normalizeName(name));
      }
      const login_res = await login(email, password);
      tokenStore.setToken(login_res.access_token);
      onLoginSuccess();
      navigate("/dashboard", { replace: true });
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      let msg: string;
      if (isSignup && Array.isArray(detail)) {
        msg = detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(" ") || "Invalid signup details.";
      } else if (isSignup && typeof detail === "string") {
        msg = detail;
      } else if (isSignup && status === 400) {
        msg = "Email already registered.";
      } else if (isSignup && status === 403) {
        msg = "Registration is currently closed.";
      } else {
        msg = "Invalid credentials. Please try again.";
      }
      setErrors({ ...NO_ERRORS, general: msg });
    } finally {
      setLoading(false);
    }
  };

  const isLogin = mode === "login";

  return (
    <div className="login-page">
      <div className="login-glow" />
      <form className="login-card" onSubmit={handleSubmit} noValidate>
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

        <p className="login-tagline">AI-powered chat for your documents</p>
        <p className="login-subtitle">
          {isLogin
            ? "Welcome back. Your documents are waiting."
            : "Start chatting with your documents — free to try."}
        </p>

        <div className="login-fields">
          {!isLogin && (
            <div className="login-field-wrap">
              <input
                type="text"
                placeholder="Full name"
                className={`login-input${errors.name ? " login-input-error" : ""}`}
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
              />
              {errors.name && <p className="login-field-error">{errors.name}</p>}
            </div>
          )}
          <div className="login-field-wrap">
            <input
              type="email"
              placeholder="Email address"
              className={`login-input${errors.email ? " login-input-error" : ""}`}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
            {errors.email && <p className="login-field-error">{errors.email}</p>}
          </div>
          <div className="login-field-wrap">
            <input
              type="password"
              placeholder="Password"
              className={`login-input${errors.password ? " login-input-error" : ""}`}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isLogin ? "current-password" : "new-password"}
            />
            {errors.password && <p className="login-field-error">{errors.password}</p>}
          </div>
        </div>

        {errors.general && <p className="login-error">{errors.general}</p>}

        <button type="submit" className="login-submit-btn" disabled={loading}>
          {loading
            ? isLogin ? "Signing in…" : "Creating account…"
            : isLogin ? "Sign in" : "Create account"}
        </button>

        <div className="login-divider">or</div>
        <GoogleAuthButton disabled={loading} />

        <a href="/" className="login-back-link">← Back to home</a>
      </form>
    </div>
  );
}

export default Login;
