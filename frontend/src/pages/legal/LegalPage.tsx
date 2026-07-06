import { Link } from "react-router-dom";
import { Navbar } from "../../components/Navbar";
import "./LegalPage.css";

type Section = {
  heading: string;
  body: string[];
};

type LegalPageProps = {
  title: string;
  subtitle: string;
  lastUpdated: string;
  sections: Section[];
};

function LegalPage({ title, subtitle, lastUpdated, sections }: LegalPageProps) {
  return (
    <div className="legal-root">
      <Navbar variant="legal" />

      <main className="legal-main">
        <div className="legal-inner">
          <header className="legal-header">
            <h1 className="legal-title">{title}</h1>
            <p className="legal-subtitle">{subtitle}</p>
            <p className="legal-date">Last updated: {lastUpdated}</p>
          </header>

          <div className="legal-body">
            {sections.map((s) => (
              <section key={s.heading} className="legal-section">
                <h2 className="legal-section-heading">{s.heading}</h2>
                {s.body.map((para, i) => (
                  <p key={i} className="legal-para">{para}</p>
                ))}
              </section>
            ))}
          </div>

          <div className="legal-contact">
            <p>
              Questions about this document?{" "}
              <a href="mailto:support@chatpaper.ai" className="legal-link">
                Contact us at support@chatpaper.ai
              </a>
            </p>
          </div>
        </div>
      </main>

      <footer className="legal-footer">
        <div className="legal-footer-inner">
          <Link to="/terms" className="legal-footer-link">Terms of Service</Link>
          <Link to="/privacy" className="legal-footer-link">Privacy Policy</Link>
          <a href="mailto:support@chatpaper.ai" className="legal-footer-link">Contact</a>
        </div>
        <p className="legal-footer-copy">© 2026 Chatpaper. All rights reserved.</p>
      </footer>
    </div>
  );
}

export default LegalPage;
