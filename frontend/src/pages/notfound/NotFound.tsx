import { Link } from "react-router-dom";
import logo from "../../assets/logo.png";
import "./NotFound.css";

function NotFound() {
  return (
    <div className="nf-root">
      <div className="nf-glow" />
      <nav className="nf-nav">
        <Link to="/" className="nf-brand">
          <img src={logo} alt="Chatpaper" className="nf-brand-logo" />
          <span className="nf-brand-name">Chatpaper</span>
        </Link>
      </nav>
      <div className="nf-body">
        <p className="nf-code">404</p>
        <h1 className="nf-heading">Page not found</h1>
        <p className="nf-sub">
          The page you are looking for does not exist or has been moved.
        </p>
        <div className="nf-actions">
          <Link to="/" className="nf-btn-primary">Go to Home</Link>
          <Link to="/login" className="nf-btn-ghost">Sign in</Link>
        </div>
      </div>
    </div>
  );
}

export default NotFound;
