import { PropsWithChildren } from "react";
import { Nav } from "./Nav";
import type { PageKey } from "../App";

interface LayoutProps extends PropsWithChildren {
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
  title: string;
}

export function Layout({ activePage, onNavigate, title, children }: LayoutProps) {
  return (
    <div className="app-shell">
      <div className="app-card">
        <header className="app-header">
          <h1>{title}</h1>
          <p>Local-first patent image extraction, SMILES processing, and FAISS similarity search.</p>
          <Nav activePage={activePage} onNavigate={onNavigate} />
        </header>
        <main className="page">{children}</main>
      </div>
    </div>
  );
}
