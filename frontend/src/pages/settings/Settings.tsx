import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import logo from "../../assets/logo.png";
import {
  changeOwnPassword,
  changeUserPassword,
  fetchAllUsers,
  fetchCurrentUser,
  tokenStore,
  User,
} from "../../api/axios";
import { LogoutIcon } from "../../components/icons/Icons";
import { isValidPassword, PASSWORD_REQUIREMENTS } from "../../utils/passwordValidation";
import "./Settings.css";

type SettingsProps = {
  onLogout: () => void;
};

function Settings({ onLogout }: SettingsProps) {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const isAdmin = user?.role === "admin";
  const selectedUser = users.find((item) => item.id === selectedUserId) ?? null;

  useEffect(() => {
    const load = async () => {
      if (!tokenStore.getToken()) {
        onLogout();
        navigate("/login", { replace: true });
        return;
      }
      try {
        const currentUser = await fetchCurrentUser();
        setUser(currentUser);
        if (currentUser.role === "admin") {
          const allUsers = await fetchAllUsers();
          setUsers(allUsers);
        }
      } catch {
        tokenStore.clear();
        onLogout();
        navigate("/login", { replace: true });
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [navigate, onLogout]);

  const resetForm = () => {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setError("");
    setSuccess("");
  };

  const handleSelectUser = (userId: number) => {
    setSelectedUserId(userId);
    resetForm();
  };

  const validateNewPasswords = () => {
    if (!isValidPassword(newPassword)) {
      setError(PASSWORD_REQUIREMENTS);
      return false;
    }
    if (newPassword !== confirmPassword) {
      setError("New password and confirm password do not match.");
      return false;
    }
    return true;
  };

  const handleOwnPasswordChange = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (!validateNewPasswords()) return;

    setSubmitting(true);
    try {
      await changeOwnPassword( newPassword);
      setSuccess("Password updated successfully.");
      resetForm();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Could not update password.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleAdminPasswordChange = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedUserId) return;
    setError("");
    setSuccess("");
    if (!validateNewPasswords()) return;

    setSubmitting(true);
    try {
      await changeUserPassword(selectedUserId, newPassword);
      setSuccess(`Password updated for ${selectedUser?.name || selectedUser?.email}.`);
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((item) => item?.msg ?? "Invalid password.").join(" "));
      } else {
        setError(typeof detail === "string" ? detail : "Could not update password.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const logout = () => {
    tokenStore.clear();
    onLogout();
  };

  if (loading) {
    return <div className="settings-page">Loading…</div>;
  }

  return (
    <div className="settings-page">
      <aside className="settings-sidebar">
        <Link to="/" className="sidebar-brand">
          <img src={logo} alt="" className="sidebar-icon" />
          <span className="sidebar-brand-name">Chatpaper</span>
        </Link>

        <nav className="settings-nav">
          <Link to="/chat" className="settings-nav-link">Chat</Link>
          <Link to="/files" className="settings-nav-link">My Files</Link>
          <Link to="/settings" className="settings-nav-link settings-nav-link-active">Settings</Link>
        </nav>

        <div className="settings-sidebar-footer">
          <button type="button" className="sidebar-logout" onClick={logout}>
            <LogoutIcon width={15} height={15} />
            Logout
          </button>
        </div>
      </aside>

      <main className="settings-main">
        <header className="settings-header">
          <h1>Settings</h1>
          <p>{user?.name || user?.email}</p>
        </header>

        {isAdmin ? (
          <section className="settings-panel">
            <h2>User passwords</h2>
            <p className="settings-panel-subtitle">Select a user to set a new password.</p>
            <div className="settings-admin-layout">
              <div className="settings-user-list">
                {users.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`settings-user-item${item.id === selectedUserId ? " active" : ""}`}
                    onClick={() => handleSelectUser(item.id)}
                  >
                    <span className="settings-user-name">{item.name || "Unnamed user"}</span>
                    <span className="settings-user-email">{item.email}</span>
                  </button>
                ))}
              </div>

              <div className="settings-form-card">
                {selectedUser ? (
                  <form onSubmit={(event) => void handleAdminPasswordChange(event)}>
                    <h3>Change password for {selectedUser.name || selectedUser.email}</h3>
                    <label className="settings-label">
                      New password
                      <input
                        type="password"
                        className="settings-input"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        required
                        autoComplete="new-password"
                      />
                    </label>
                    <label className="settings-label">
                      Confirm new password
                      <input
                        type="password"
                        className="settings-input"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        required
                        autoComplete="new-password"
                      />
                    </label>
                    <p className="settings-hint">{PASSWORD_REQUIREMENTS}</p>
                    {error && <p className="settings-error">{error}</p>}
                    {success && <p className="settings-success">{success}</p>}
                    <button type="submit" className="settings-submit" disabled={submitting}>
                      {submitting ? "Saving…" : "Update password"}
                    </button>
                  </form>
                ) : (
                  <p className="settings-empty">Select a user from the list.</p>
                )}
              </div>
            </div>
          </section>
        ) : (
          <section className="settings-panel">
            <h2>Change password</h2>
            <form className="settings-form-card" onSubmit={(event) => void handleOwnPasswordChange(event)}>
              {/*<label className="settings-label">
                Current password
                <input
                  type="password"
                  className="settings-input"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
              </label>*/}
              <label className="settings-label">
                New password
                <input
                  type="password"
                  className="settings-input"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                />
              </label>
              <label className="settings-label">
                Confirm new password
                <input
                  type="password"
                  className="settings-input"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                />
              </label>
              <p className="settings-hint">{PASSWORD_REQUIREMENTS}</p>
              {error && <p className="settings-error">{error}</p>}
              {success && <p className="settings-success">{success}</p>}
              <button type="submit" className="settings-submit" disabled={submitting}>
                {submitting ? "Saving…" : "Update password"}
              </button>
            </form>
          </section>
        )}
      </main>
    </div>
  );
}

export default Settings;
