import { LogoutIcon } from "./icons/Icons";
import { useLogout } from "../hooks/useLogout";
import "./LogoutButton.css";

type LogoutButtonProps = {
  onLogout: () => void;
  variant?: "topbar" | "sidebar";
  iconSize?: number;
};

export function LogoutButton({
  onLogout,
  variant = "topbar",
  iconSize,
}: LogoutButtonProps) {
  const logout = useLogout(onLogout);
  const size = iconSize ?? (variant === "sidebar" ? 15 : 14);

  return (
    <button
      type="button"
      className={`logout-btn logout-btn--${variant}`}
      onClick={logout}
    >
      <LogoutIcon width={size} height={size} />
      Logout
    </button>
  );
}
