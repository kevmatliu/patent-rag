import type { PageKey } from "../App";

interface NavProps {
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
}

const pages: Array<{ key: PageKey; label: string }> = [
  { key: "batch", label: "Batch Upload" },
  { key: "patents", label: "Patents" },
  { key: "compounds", label: "Compounds" },
  { key: "processing", label: "Processing" },
  { key: "search", label: "Search" }
];

export function Nav({ activePage, onNavigate }: NavProps) {
  return (
    <nav className="nav">
      {pages.map((page) => (
        <button
          key={page.key}
          className={activePage === page.key ? "active" : ""}
          type="button"
          onClick={() => onNavigate(page.key)}
        >
          {page.label}
        </button>
      ))}
    </nav>
  );
}
