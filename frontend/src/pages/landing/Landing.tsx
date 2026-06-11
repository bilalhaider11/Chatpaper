import { Link } from "react-router-dom";
import logo from "../../assets/logo.png";
import hero from "../../assets/hero.png";
import "./Landing.css";

const FILE_TYPES = ["PDF", "DOCX", "TXT", "CSV", "XLSX"];

const STEPS = [
  {
    num: "01",
    title: "Upload Your Document",
    desc: "Drag and drop a PDF, Word doc, CSV, Excel sheet, or plain text file. We process it automatically — usually under a minute.",
  },
  {
    num: "02",
    title: "Ask Any Question",
    desc: "Type your question in plain English. No special syntax, no commands — just ask like you would ask a colleague.",
  },
  {
    num: "03",
    title: "Get Cited Answers",
    desc: "Receive a precise answer with citations pointing to the exact source in your document. Know exactly where every fact came from.",
  },
];

const FEATURES = [
  {
    icon: "📄",
    title: "Per-Document Chat",
    desc: "Each document gets its own dedicated conversation. Ask focused questions and get precise answers from that exact file.",
  },
  {
    icon: "🌐",
    title: "Global Chat",
    desc: "Cross-search all your documents at once. Perfect for research where the answer might span multiple files.",
  },
  {
    icon: "🔍",
    title: "AI-Powered Citations",
    desc: "Every answer comes with source references. Know exactly where each piece of information came from — no guessing.",
  },
  {
    icon: "📊",
    title: "All File Types",
    desc: "Supports PDF, Word (DOCX), plain text, CSV, and Excel (XLSX). One tool for all your document types.",
  },
];

const USE_CASES = [
  { icon: "🔬", title: "Researchers", desc: "Analyze papers, extract key findings, and cross-reference sources in seconds." },
  { icon: "⚖️", title: "Legal Teams", desc: "Query contracts, case documents, and compliance files without manual search." },
  { icon: "🎓", title: "Students", desc: "Understand textbooks, study materials, and lecture notes — ask, don't skim." },
  { icon: "📈", title: "Analysts", desc: "Extract insights from reports, spreadsheets, and financial documents instantly." },
  { icon: "👥", title: "HR Teams", desc: "Search policies, resumes, and handbooks without scrolling through pages." },
];

const PLAN_FEATURES = [
  "Upload PDF, Word, CSV, Excel, TXT",
  "Per-document conversations",
  "Global chat across all documents",
  "AI-powered answers with source citations",
  "Unlimited conversations",
  "Google Sign-In supported",
];

function Landing() {
  return (
    <div className="lp-root">

      {/* ── Navbar ── */}
      <nav className="lp-nav">
        <div className="lp-nav-inner">
          <Link to="/" className="lp-nav-brand">
            <img src={logo} alt="Chatpaper logo" className="lp-nav-logo" />
            <span className="lp-nav-brand-name">Chatpaper</span>
          </Link>
          <div className="lp-nav-actions">
            <Link to="/login" className="lp-nav-signin">Sign in</Link>
            <Link to="/login?mode=signup" className="lp-nav-cta">Get Started Free</Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="lp-hero">
        <div className="lp-hero-glow lp-hero-glow-1" />
        <div className="lp-hero-glow lp-hero-glow-2" />
        <div className="lp-hero-inner">
          <div className="lp-file-types-bar">
            {FILE_TYPES.map((t) => <span key={t} className="lp-file-type">{t}</span>)}
          </div>
          <h1 className="lp-hero-headline">
            Chat with Any Document.<br />
            <span className="lp-hero-headline-accent">Get Answers in Seconds.</span>
          </h1>
          <p className="lp-hero-subhead">
            Upload a PDF, Word doc, spreadsheet, or text file. Ask anything in plain English.
            Chatpaper reads it, understands it, and answers with source citations — instantly.
          </p>
          <div className="lp-hero-ctas">
            <Link to="/login?mode=signup" className="lp-cta-primary">
              Start Free — No credit card required
            </Link>
            <a href="#how-it-works" className="lp-cta-ghost">See How It Works →</a>
          </div>
          <div className="lp-hero-img-wrap">
            <img src={hero} alt="Chatpaper document chat interface" className="lp-hero-img" />
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section id="how-it-works" className="lp-section">
        <div className="lp-section-inner">
          <p className="lp-section-label">HOW IT WORKS</p>
          <h2 className="lp-section-heading">From Document to Insight in Three Steps</h2>
          <div className="lp-steps">
            {STEPS.map((s, i) => (
              <div key={s.num} className="lp-step-wrap">
                <div className="lp-step">
                  <div className="lp-step-num">{s.num}</div>
                  <h3 className="lp-step-title">{s.title}</h3>
                  <p className="lp-step-desc">{s.desc}</p>
                </div>
                {i < STEPS.length - 1 && <div className="lp-step-arrow" aria-hidden="true">→</div>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="lp-section lp-features-section">
        <div className="lp-section-inner">
          <p className="lp-section-label">FEATURES</p>
          <h2 className="lp-section-heading">Everything You Need</h2>
          <p className="lp-section-sub">Powerful document intelligence, simple enough for anyone to use.</p>
          <div className="lp-features">
            {FEATURES.map((f) => (
              <div key={f.title} className="lp-feature">
                <div className="lp-feature-icon">{f.icon}</div>
                <h3 className="lp-feature-title">{f.title}</h3>
                <p className="lp-feature-desc">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Use cases ── */}
      <section className="lp-section">
        <div className="lp-section-inner">
          <p className="lp-section-label">USE CASES</p>
          <h2 className="lp-section-heading">Built For Anyone Who Works with Documents</h2>
          <div className="lp-usecases">
            {USE_CASES.map((u) => (
              <div key={u.title} className="lp-usecase">
                <span className="lp-usecase-icon">{u.icon}</span>
                <h3 className="lp-usecase-title">{u.title}</h3>
                <p className="lp-usecase-desc">{u.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ── */}
      <section id="pricing" className="lp-section lp-pricing-section">
        <div className="lp-section-inner">
          <p className="lp-section-label">PRICING</p>
          <h2 className="lp-section-heading">Simple Pricing</h2>
          <p className="lp-section-sub">No credit card. No hidden fees. Just start.</p>
          <div className="lp-pricing">
            <div className="lp-plan">
              <div className="lp-plan-badge">Free</div>
              <div className="lp-plan-price">
                <span className="lp-plan-amount">$0</span>
                <span className="lp-plan-period">/ forever</span>
              </div>
              <ul className="lp-plan-features">
                {PLAN_FEATURES.map((feat) => (
                  <li key={feat} className="lp-plan-feature">
                    <span className="lp-plan-check">✓</span>
                    {feat}
                  </li>
                ))}
              </ul>
              <Link to="/login?mode=signup" className="lp-plan-cta">Get Started Free</Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA Banner ── */}
      <section className="lp-cta-banner">
        <div className="lp-cta-banner-glow" />
        <div className="lp-cta-banner-inner">
          <h2 className="lp-cta-banner-heading">Start Chatting with Your Documents Today</h2>
          <p className="lp-cta-banner-sub">Free. No credit card required.</p>
          <Link to="/login?mode=signup" className="lp-cta-primary">Get Started Free</Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <div className="lp-footer-brand">
            <img src={logo} alt="Chatpaper" className="lp-footer-logo" />
            <span className="lp-footer-brand-name">Chatpaper</span>
          </div>
          <nav className="lp-footer-links" aria-label="Footer navigation">
            <Link to="/terms">Terms of Service</Link>
            <Link to="/privacy">Privacy Policy</Link>
            <a href="mailto:support@chatpaper.ai">Contact</a>
          </nav>
          <p className="lp-footer-copy">© 2026 Chatpaper. All rights reserved.</p>
        </div>
      </footer>

    </div>
  );
}

export default Landing;
