import { useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { CompoundBrowserPage } from "./pages/CompoundBrowserPage";
import { BatchUploadPage } from "./pages/BatchUploadPage";
import { PatentBrowserPage } from "./pages/PatentBrowserPage";
import { CompoundExplorationWorkspacePage } from "./pages/CompoundExplorationWorkspacePage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { RecommendationWorkbenchPage } from "./pages/RecommendationWorkbenchPage";
import { SearchPage } from "./pages/SearchPage";

export type PageKey =
  | "batch"
  | "patents"
  | "processing"
  | "search"
  | "workbench"
  | "compounds"
  | "exploration";

const pageTitles: Record<PageKey, string> = {
  batch: "Batch Patent Ingest",
  compounds: "Compound Browser",
  exploration: "Compound Exploration Workspace",
  patents: "Patent Metadata",
  processing: "Image Processing",
  search: "Compound Search",
  workbench: "Editor Workbench"
};

const DEFAULT_PAGE: PageKey = "batch";

function isPageKey(value: string): value is PageKey {
  return value in pageTitles;
}

function getPageFromHash(hash: string): PageKey {
  const next = hash.replace(/^#/, "").trim();
  return isPageKey(next) ? next : DEFAULT_PAGE;
}

function App() {
  const [page, setPage] = useState<PageKey>(() => getPageFromHash(window.location.hash));

  useEffect(() => {
    const syncPageFromHash = () => {
      setPage(getPageFromHash(window.location.hash));
    };

    window.addEventListener("hashchange", syncPageFromHash);
    return () => window.removeEventListener("hashchange", syncPageFromHash);
  }, []);

  const handleNavigate = (nextPage: PageKey) => {
    window.location.hash = nextPage;
    setPage(nextPage);
  };

  return (
    <Layout activePage={page} onNavigate={handleNavigate} title={pageTitles[page]}>
      <ErrorBoundary>
        {page === "batch" && <BatchUploadPage key="batch" />}
        {page === "compounds" && <CompoundBrowserPage key="compounds" />}
        {page === "exploration" && <CompoundExplorationWorkspacePage key="exploration" />}
        {page === "patents" && <PatentBrowserPage key="patents" />}
        {page === "processing" && <ProcessingPage key="processing" />}
        {page === "search" && <SearchPage key="search" />}
        {page === "workbench" && <RecommendationWorkbenchPage key="workbench" />}
      </ErrorBoundary>
    </Layout>
  );
}

export default App;
