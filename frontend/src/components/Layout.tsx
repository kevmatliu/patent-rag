import { PropsWithChildren, useState } from "react";
import { Nav } from "./Nav";
import type { PageKey } from "../App";
import { resetDatabase } from "../api/patents";

interface LayoutProps extends PropsWithChildren {
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
  title: string;
}

export function Layout({ activePage, onNavigate, title, children }: LayoutProps) {
  const [resetting, setResetting] = useState(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);
  const [resetError, setResetError] = useState<string | null>(null);

  const handleResetDatabase = async () => {
    const confirmed = window.confirm(
      "Reset the local database and FAISS index? This will permanently delete all patents, compounds, jobs, and extracted/search upload files."
    );
    if (!confirmed) {
      return;
    }

    setResetting(true);
    setResetMessage(null);
    setResetError(null);

    try {
      const result = await resetDatabase();
      setResetMessage(
        `Reset complete. Deleted ${result.patents_deleted} patents, ${result.compounds_deleted} compounds, ${result.jobs_deleted} jobs, ${result.logs_deleted} logs, and ${result.files_deleted} files.`
      );
      window.setTimeout(() => window.location.reload(), 800);
    } catch (error) {
      setResetError(error instanceof Error ? error.message : "Failed to reset the local database");
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="app-shell">
      <div className="app-card">
        <header className="app-header">
          <div className="header-top">
            <div>
              <h1>{title}</h1>
              <p>Local-first patent image extraction, SMILES processing, and FAISS similarity search.</p>
            </div>
            <button className="danger-button" type="button" onClick={handleResetDatabase} disabled={resetting}>
              {resetting ? "Resetting..." : "Reset Database"}
            </button>
          </div>
          {resetMessage && <p className="status-success header-status">{resetMessage}</p>}
          {resetError && <p className="status-error header-status">{resetError}</p>}
          <Nav activePage={activePage} onNavigate={onNavigate} />
        </header>
        <main className="page">{children}</main>
      </div>
    </div>
  );
}
