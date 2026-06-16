import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import logo from "../../assets/logo.png";
import {
  changePassword,
  fetchAllUsers,
  fetchCurrentUser,
  tokenStore,
  updateName,
  User,
} from "../../api/axios";
import { ChatBubbleIcon, FileIcon, LogoutIcon, SettingsIcon } from "../../components/icons/Icons";
import { useLogout } from "../../hooks/useLogout";
import { isValidName, NAME_REQUIREMENTS, normalizeName } from "../../utils/Validations";
import { isValidPassword, PASSWORD_REQUIREMENTS } from "../../utils/Validations";
import "./Settings.css";

type SettingsProps = {
  onLogout: () => void;
};

function Settings({ onLogout }: SettingsProps) {
  const navigate = useNavigate();
  const logout = useLogout(onLogout);
  const [user, setUser] = useState<User | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [profileError, setProfileError] = useState("");
  const [profileSuccess, setProfileSuccess] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [adminError, setAdminError] = useState("");
  const [adminSuccess, setAdminSuccess] = useState("");
  const [profileName, setProfileName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [nameSubmitting, setNameSubmitting] = useState(false);

  const isAdmin = user?.role === "admin";
  const selectedUser = users.find((item) => item.id === selectedUserId) ?? null;
  const isChangingOwnAccount = selectedUserId === user?.id;
  const isGoogleAuth = (authProvider?: string) => authProvider === "google";
  const requiresCurrentPassword = !isGoogleAuth(user?.auth_provider);
  const adminRequiresCurrentPassword =
    isChangingOwnAccount && !isGoogleAuth(selectedUser?.auth_provider ?? user?.auth_provider);

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
        setProfileName(currentUser.name ?? "");
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

  const resetPasswordForm = () => {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setPasswordError("");
    setPasswordSuccess("");
  };

  const handleSelectUser = (userId: number) => {
    const selected = users.find((item) => item.id === userId);
    setSelectedUserId(userId);
    setProfileName(selected?.name ?? "");
    resetPasswordForm();
    setAdminError("");
    setAdminSuccess("");
  };

  const getErrorMessage = (err: unknown, fallback: string) => {
    const detail = (err as { response?: { data?: { detail?: string | Array<{ msg?: string }> } } })
      ?.response?.data?.detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item?.msg ?? fallback).join(" ");
    }
    return typeof detail === "string" ? detail : fallback;
  };

  const handleOwnNameUpdate = async (event: FormEvent) => {
    event.preventDefault();
    setProfileError("");
    setProfileSuccess("");

    if (!isValidName(profileName)) {
      setProfileError(NAME_REQUIREMENTS);
      return;
    }
    const trimmedName = normalizeName(profileName);

    setNameSubmitting(true);
    try {
      const updated = await updateName(trimmedName);
      setUser(updated);
      setProfileName(updated.name ?? trimmedName);
      setProfileSuccess("Name updated successfully.");
    } catch (err: unknown) {
      setProfileError(getErrorMessage(err, "Could not update name."));
    } finally {
      setNameSubmitting(false);
    }
  };

  const handleAdminNameUpdate = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedUserId) return;
    setAdminError("");
    setAdminSuccess("");

    if (!isValidName(profileName)) {
      setAdminError(NAME_REQUIREMENTS);
      return;
    }
    const trimmedName = normalizeName(profileName);

    setNameSubmitting(true);
    try {
      const updated = await updateName(trimmedName, selectedUserId);
      setUsers((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setProfileName(updated.name ?? trimmedName);
      setAdminSuccess(`Name updated for ${updated.name || updated.email}.`);
    } catch (err: unknown) {
      setAdminError(getErrorMessage(err, "Could not update name."));
    } finally {
      setNameSubmitting(false);
    }
  };

  const handleOwnPasswordChange = async (event: FormEvent) => {
    event.preventDefault();
    setPasswordError("");
    setPasswordSuccess("");

    if (requiresCurrentPassword && !currentPassword) {
      setPasswordError("Current password is required.");
      return;
    }
    if (!isValidPassword(newPassword)) {
      setPasswordError(PASSWORD_REQUIREMENTS);
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirm password do not match.");
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(newPassword, {
        ...(requiresCurrentPassword ? { currentPassword } : {}),
      });
      if (isGoogleAuth(user?.auth_provider)) {
        setUser((prev) => (prev ? { ...prev, auth_provider: "password" } : prev));
      }
      setPasswordSuccess("Password updated successfully.");
      resetPasswordForm();
    } catch (err: unknown) {
      setPasswordError(getErrorMessage(err, "Could not update password."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleAdminPasswordChange = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedUserId) return;
    setAdminError("");
    setAdminSuccess("");
    if (!isValidPassword(newPassword)) {
      setAdminError(PASSWORD_REQUIREMENTS);
      return;
    }
    if (newPassword !== confirmPassword) {
      setAdminError("New password and confirm password do not match.");
      return;
    }
    if (adminRequiresCurrentPassword && !currentPassword) {
      setAdminError("Current password is required.");
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(newPassword, {
        userId: selectedUserId,
        ...(adminRequiresCurrentPassword ? { currentPassword } : {}),
      });
      if (isGoogleAuth(selectedUser?.auth_provider)) {
        setUsers((prev) =>
          prev.map((item) =>
            item.id === selectedUserId ? { ...item, auth_provider: "password" } : item
          )
        );
        if (isChangingOwnAccount) {
          setUser((prev) => (prev ? { ...prev, auth_provider: "password" } : prev));
        }
      }
      setAdminSuccess(`Password updated for ${selectedUser?.name || selectedUser?.email}.`);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      setAdminError(getErrorMessage(err, "Could not update password."));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="settings-page">Loading…</div>;
  }

  return (
    <div className="settings-page">
      <aside className="settings-sidebar">
        <Link to="/dashboard" className="sidebar-brand">
          <img src={logo} alt="" className="sidebar-icon" />
          <span className="sidebar-brand-name">Chatpaper</span>
        </Link>

        <nav className="settings-nav">
          <Link to="/chat" className="settings-nav-link">
            <ChatBubbleIcon width={16} height={16} />
            Chat
          </Link>
          <Link to="/files" className="settings-nav-link">
            <FileIcon width={16} height={16} />
            My Files
          </Link>
          <Link to="/settings" className="settings-nav-link settings-nav-link-active">
            <SettingsIcon width={16} height={16} />
            Settings
          </Link>
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
            <h2>Manage users</h2>
            <p className="settings-panel-subtitle">Select a user to update their name or password.</p>
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
                  <>
                    <form onSubmit={(event) => void handleAdminNameUpdate(event)}>
                      <h3>Update name for {selectedUser.name || selectedUser.email}</h3>
                      <label className="settings-label">
                        Name
                        <input
                          type="text"
                          className="settings-input"
                          value={profileName}
                          onChange={(e) => setProfileName(e.target.value)}
                          required
                          autoComplete="name"
                        />
                      </label>
                      <p className="settings-hint">{NAME_REQUIREMENTS}</p>
                      <button type="submit" className="settings-submit" disabled={nameSubmitting}>
                        {nameSubmitting ? "Saving…" : "Update name"}
                      </button>
                    </form>

                    <form className="settings-password-form" onSubmit={(event) => void handleAdminPasswordChange(event)}>
                      <h3>Change password for {selectedUser.name || selectedUser.email}</h3>
                      {adminRequiresCurrentPassword && (
                        <label className="settings-label">
                          Current password
                          <input
                            type="password"
                            className="settings-input"
                            value={currentPassword}
                            onChange={(e) => setCurrentPassword(e.target.value)}
                            required
                            autoComplete="current-password"
                          />
                        </label>
                      )}
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
                      <button type="submit" className="settings-submit" disabled={submitting}>
                        {submitting ? "Saving…" : "Update password"}
                      </button>
                    </form>
                  </>
                ) : (
                  <p className="settings-empty">Select a user from the list.</p>
                )}
                {adminError && <p className="settings-error">{adminError}</p>}
                {adminSuccess && <p className="settings-success">{adminSuccess}</p>}
              </div>
            </div>
          </section>
        ) : (
          <>
            <section className="settings-panel">
              <h2>Profile</h2>
              <form className="settings-form-card" onSubmit={(event) => void handleOwnNameUpdate(event)}>
                <label className="settings-label">
                  Name
                  <input
                    type="text"
                    className="settings-input"
                    value={profileName}
                    onChange={(e) => setProfileName(e.target.value)}
                    required
                    autoComplete="name"
                  />
                </label>
                <p className="settings-hint">{NAME_REQUIREMENTS}</p>
                {profileError && <p className="settings-error">{profileError}</p>}
                {profileSuccess && <p className="settings-success">{profileSuccess}</p>}
                <button type="submit" className="settings-submit" disabled={nameSubmitting}>
                  {nameSubmitting ? "Saving…" : "Update name"}
                </button>
              </form>
            </section>

            <section className="settings-panel">
              <h2>Change password</h2>
              <form className="settings-form-card" onSubmit={(event) => void handleOwnPasswordChange(event)}>
                {requiresCurrentPassword && (
                  <label className="settings-label">
                    Current password
                    <input
                      type="password"
                      className="settings-input"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      required
                      autoComplete="current-password"
                    />
                  </label>
                )}
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
                {passwordError && <p className="settings-error">{passwordError}</p>}
                {passwordSuccess && <p className="settings-success">{passwordSuccess}</p>}
                <button type="submit" className="settings-submit" disabled={submitting}>
                  {submitting ? "Saving…" : "Update password"}
                </button>
              </form>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default Settings;
