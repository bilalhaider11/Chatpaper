import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  resetPassword,
  tokenStore,
  validatePasswordResetToken,
} from "../../api/axios";
import { isValidPassword, PASSWORD_REQUIREMENTS } from "../../utils/Validations";
import logo from "../../assets/logo.png";
import "./Login.css";

type ResetPasswordProps = {
  onLoginSuccess: () => void;
};

function ResetPassword({ onLoginSuccess }: ResetPasswordProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) {
      setValidating(false);
      setError("Missing reset token.");
      return;
    }

    validatePasswordResetToken(token)
      .then(() => setTokenValid(true))
      .catch(() => setError("This reset link is invalid or has expired."))
      .finally(() => setValidating(false));
  }, [token]);

  const handleSubmit = async (event: { preventDefault(): void }) => {
    event.preventDefault();
    setError("");

    if (!isValidPassword(password)) {
      setError(PASSWORD_REQUIREMENTS);
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const data = await resetPassword(token, password);
      tokenStore.setToken(data.access_token);
      onLoginSuccess();
      navigate("/", { replace: true });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail;
      setError(typeof detail === "string" ? detail : "Failed to reset password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-glow" />
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-brand">
          <img src={logo} alt="" className="login-logo" />
          <span className="login-brand-name">Chatpaper</span>
        </div>

        <p className="login-subtitle">
          {validating
            ? "Checking your reset link…"
            : tokenValid
              ? "Choose a new password for your account."
              : "Unable to reset your password."}
        </p>

        {tokenValid && !validating && (
          <div className="login-fields">
            <input
              type="password"
              placeholder="New password"
              className="login-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
            <input
              type="password"
              placeholder="Confirm new password"
              className="login-input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
            <p className="login-hint">{PASSWORD_REQUIREMENTS}</p>
          </div>
        )}

        {error && <p className="login-error">{error}</p>}

        {tokenValid && !validating && (
          <button type="submit" className="login-submit-btn" disabled={loading}>
            {loading ? "Saving…" : "Set new password"}
          </button>
        )}

        <p className="login-back-link">
          <Link to="/login">Back to sign in</Link>
        </p>
      </form>
    </div>
  );
}

export default ResetPassword;
