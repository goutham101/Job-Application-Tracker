import { Briefcase, Rows, ChartBar, EnvelopeSimple } from "@phosphor-icons/react";

export default function TopBar({ route }) {
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="wordmark">
          <div className="wordmark-badge" aria-hidden>
            <Briefcase size={17} weight="fill" />
          </div>
          <span>Job Tracker</span>
        </div>
        <nav className="nav" aria-label="Primary">
          <a
            href="#/applications"
            className={route === "applications" ? "active" : ""}
            aria-current={route === "applications" ? "page" : undefined}
          >
            <Rows size={16} aria-hidden /> Applications
          </a>
          <a
            href="#/analytics"
            className={route === "analytics" ? "active" : ""}
            aria-current={route === "analytics" ? "page" : undefined}
          >
            <ChartBar size={16} aria-hidden /> Analytics
          </a>
          <a
            href="#/matches"
            className={route === "matches" ? "active" : ""}
            aria-current={route === "matches" ? "page" : undefined}
          >
            <EnvelopeSimple size={16} aria-hidden /> Review Queue
          </a>
        </nav>
        <div className="topbar-spacer" />
      </div>
    </header>
  );
}
