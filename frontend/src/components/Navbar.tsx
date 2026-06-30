import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import logo from "../assets/logo.png";
import { tokenStore } from "../api/axios";
import { ChatBubbleIcon, FileIcon, SettingsIcon } from "./icons/Icons";
import { LogoutButton } from "./LogoutButton";
import "./Navbar.css";

export type NavbarVariant =
  | "auto"
  | "public"
  | "pricing"
  | "dashboard"
  | "files"
  | "chat"
  | "settings"
  | "legal";

type NavbarProps = {
  variant?: NavbarVariant;
  onLogout?: () => void;
  sidebarHeader?: ReactNode;
  children?: ReactNode;
};

function resolveVariant(
  path: string,
  variant: NavbarVariant = "auto"
): Exclude<NavbarVariant, "auto"> {
  if (variant !== "auto") return variant;
  if (path === "/terms" || path === "/privacy") return "legal";
  if (path.startsWith("/chat")) return "chat";
  if (path.startsWith("/settings")) return "settings";
  if (path === "/dashboard") return "dashboard";
  if (path === "/files") return "files";
  if (path === "/pricing") return "pricing";
  return "public";
}

function PricingButton({ className }: { className: string }) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      className={className}
      onClick={() => navigate("/pricing")}
    >
      Pricing
    </button>
  );
}

function MarketingNavbar({ onPricingPage }: { onPricingPage?: boolean }) {
  const isLoggedIn = Boolean(tokenStore.getToken());

  return (
    <nav className="navbar navbar--marketing">
      <div className="navbar-marketing-inner">
        <Link to="/" className="navbar-marketing-brand">
          <img src={logo} alt="Chatpaper logo" className="navbar-marketing-logo" />
          <span className="navbar-marketing-brand-name">Chatpaper</span>
        </Link>
        <div className="navbar-marketing-actions">
          {!onPricingPage && (
            <PricingButton className="navbar-marketing-pricing" />
          )}
          {isLoggedIn ? (
            <Link to="/dashboard" className="navbar-marketing-cta">
              Dashboard
            </Link>
          ) : (
            <>
              <Link to="/login" className="navbar-marketing-link">
                Sign in
              </Link>
              <Link to="/login?mode=signup" className="navbar-marketing-cta">
                {onPricingPage ? "Get Started" : "Get Started Free"}
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

function TopbarNavbar({
  page,
  onLogout,
}: {
  page: "dashboard" | "files";
  onLogout: () => void;
}) {
  return (
    <nav className={`navbar navbar--topbar navbar--topbar-${page}`}>
      {page === "dashboard" ? (
        <img src={logo} alt="Chatpaper" className="navbar-topbar-logo" />
      ) : (
        <Link to="/dashboard" className="navbar-topbar-brand">
          <img src={logo} alt="" className="navbar-topbar-icon" />
          <span className="navbar-topbar-brand-name">Chatpaper</span>
        </Link>
      )}
      <div className="navbar-topbar-actions">
        {page === "dashboard" && (
          <PricingButton className="navbar-topbar-pricing" />
        )}
        {page === "files" && (
          <Link to="/chat" className="navbar-topbar-link">
            Chat
          </Link>
        )}
        <LogoutButton onLogout={onLogout} variant="topbar" />
      </div>
    </nav>
  );
}

function ChatSidebar({
  onLogout,
  sidebarHeader,
  children,
}: {
  onLogout: () => void;
  sidebarHeader?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <aside className="navbar-sidebar navbar-sidebar--chat chatbot-sidebar">
      <div className="navbar-sidebar-header">
        <Link to="/dashboard" className="navbar-sidebar-brand">
          <img src={logo} alt="" className="navbar-sidebar-icon" />
          <span className="navbar-sidebar-brand-name">Chatpaper</span>
        </Link>
        {sidebarHeader}
      </div>
      <div className="navbar-sidebar-body">{children}</div>
      <div className="navbar-sidebar-footer">
        <Link to="/settings" className="navbar-sidebar-link">
          <SettingsIcon width={15} height={15} />
          Settings
        </Link>
        <LogoutButton onLogout={onLogout} variant="sidebar" />
      </div>
    </aside>
  );
}

function SettingsSidebar({ onLogout }: { onLogout: () => void }) {
  const { pathname } = useLocation();

  return (
    <aside className="navbar-sidebar navbar-sidebar--settings settings-sidebar">
      <Link to="/dashboard" className="navbar-sidebar-brand">
        <img src={logo} alt="" className="navbar-sidebar-icon" />
        <span className="navbar-sidebar-brand-name">Chatpaper</span>
      </Link>

      <nav className="navbar-settings-nav">
        <Link
          to="/chat"
          className={`navbar-settings-link${pathname.startsWith("/chat") ? " navbar-settings-link--active" : ""}`}
        >
          <ChatBubbleIcon width={16} height={16} />
          Chat
        </Link>
        <Link
          to="/files"
          className={`navbar-settings-link${pathname.startsWith("/files") ? " navbar-settings-link--active" : ""}`}
        >
          <FileIcon width={16} height={16} />
          My Files
        </Link>
        <Link
          to="/settings"
          className={`navbar-settings-link${pathname.startsWith("/settings") ? " navbar-settings-link--active" : ""}`}
        >
          <SettingsIcon width={16} height={16} />
          Settings
        </Link>
      </nav>

      <div className="navbar-settings-footer">
        <LogoutButton onLogout={onLogout} variant="sidebar" />
      </div>
    </aside>
  );
}

function LegalNavbar() {
  return (
    <nav className="navbar navbar--legal">
      <div className="navbar-legal-inner">
        <Link to="/" className="navbar-legal-brand">
          <img src={logo} alt="Chatpaper logo" className="navbar-legal-logo" />
          <span className="navbar-legal-name">Chatpaper</span>
        </Link>
        <Link to="/login" className="navbar-legal-back">
          ← Back to app
        </Link>
      </div>
    </nav>
  );
}

export function Navbar({
  variant = "auto",
  onLogout,
  sidebarHeader,
  children,
}: NavbarProps) {
  const { pathname } = useLocation();
  const resolved = resolveVariant(pathname, variant);

  switch (resolved) {
    case "public":
      return <MarketingNavbar />;
    case "pricing":
      return <MarketingNavbar onPricingPage />;
    case "dashboard":
      return <TopbarNavbar page="dashboard" onLogout={onLogout!} />;
    case "files":
      return <TopbarNavbar page="files" onLogout={onLogout!} />;
    case "chat":
      return (
        <ChatSidebar onLogout={onLogout!} sidebarHeader={sidebarHeader}>
          {children}
        </ChatSidebar>
      );
    case "settings":
      return <SettingsSidebar onLogout={onLogout!} />;
    case "legal":
      return <LegalNavbar />;
    default:
      return null;
  }
}
