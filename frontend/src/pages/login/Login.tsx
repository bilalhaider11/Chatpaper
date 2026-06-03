import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { exchangeOAuthCode, login, signup } from "../../api/axios";
import { tokenStore } from "../../api/axios";
import { GoogleAuthButton } from "../../components/login/google_auth";

type LoginProps = {
  onLoginSuccess: () => void;
};

const inputClass =
  "rounded-[10px] border border-slate-400/30 bg-[#0b1325] px-3 py-2.5 text-slate-200 outline-none focus:border-blue-500/50";

function Login({ onLoginSuccess }: LoginProps) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [login_signup, setlogin_signup] = useState(false);
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
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 p-5">
      <form
        className="flex w-full max-w-[420px] flex-col gap-3 rounded-2xl border border-slate-400/25 bg-slate-900/80 p-7"
        onSubmit={handleSubmit}
      >
        <h1 className="m-0 text-slate-50">Sign in</h1>
        <p className="m-0 mb-1 text-slate-300">
          Authenticate to access file operations and chatbot workspace.
        </p>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={inputClass}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={inputClass}
          required
        />
        {error ? <p className="m-0 text-sm text-red-300">{error}</p> : null}
        <button
          onClick={() => {
            actionRef.current = "login";
            setlogin_signup(false);
          }}
          type="submit"
          disabled={loading}
          className="mt-1 cursor-pointer rounded-[10px] border-0 bg-gradient-to-br from-blue-600 to-blue-700 px-3 py-2.5 font-semibold text-white disabled:cursor-wait disabled:opacity-75"
        >
          {loading ? "Signing in..." : "Login"}
        </button>
        <button
          onClick={() => {
            actionRef.current = "signup";
            setlogin_signup(true);
          }}
          type="submit"
          disabled={loading}
          className="cursor-pointer rounded-[10px] border-0 bg-gradient-to-br from-blue-600 to-blue-700 px-3 py-2.5 font-semibold text-white disabled:cursor-wait disabled:opacity-75"
        >
          {loading ? "Signing up..." : "Signup"}
        </button>
        <div className="my-2 flex items-center gap-3 text-sm text-slate-400">
          <span className="h-px flex-1 bg-slate-400/25" />
          <span>or</span>
          <span className="h-px flex-1 bg-slate-400/25" />
        </div>
        <GoogleAuthButton disabled={loading} />
      </form>
    </div>
  );
}

export default Login;
