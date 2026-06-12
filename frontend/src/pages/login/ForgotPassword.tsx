import { useState } from "react";
import { Link } from "react-router-dom";
import { requestPasswordReset } from "../../api/axios";
import logo from "../../assets/logo.png";
import "./Login.css";

function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  const handleSubmit = async (event: { preventDefault(): void }) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch {
      setError("Something went wrong. Please try again.");
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
          {sent
            ? "If an account exists with that email, a reset link has been sent. Check the server logs for the link during development."
            : "Enter your email and we'll send you a link to reset your password."}
        </p>

        {!sent && (
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
          </div>
        )}

        {error && <p className="login-error">{error}</p>}

        {!sent && (
          <button type="submit" className="login-submit-btn" disabled={loading}>
            {loading ? "Sending…" : "Send reset link"}
          </button>
        )}

        <p className="login-back-link">
          <Link to="/login">Back to sign in</Link>
        </p>
      </form>
    </div>
  );
}

export default ForgotPassword;
