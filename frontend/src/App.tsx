import { useState } from "react";
import { Layout } from "./components/Layout";
import { CompoundBrowserPage } from "./pages/CompoundBrowserPage";
import { BatchUploadPage } from "./pages/BatchUploadPage";
import { PatentBrowserPage } from "./pages/PatentBrowserPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { SearchPage } from "./pages/SearchPage";

export type PageKey = "batch" | "patents" | "processing" | "search" | "compounds";

const pageTitles: Record<PageKey, string> = {
  batch: "Batch Patent Ingest",
  compounds: "Compound Browser",
  patents: "Patent Metadata",
  processing: "Image Processing",
  search: "Image Search"
};

function App() {
  const [page, setPage] = useState<PageKey>("batch");

  return (
    <Layout activePage={page} onNavigate={setPage} title={pageTitles[page]}>
      {page === "batch" && <BatchUploadPage />}
      {page === "compounds" && <CompoundBrowserPage />}
      {page === "patents" && <PatentBrowserPage />}
      {page === "processing" && <ProcessingPage />}
      {page === "search" && <SearchPage />}
    </Layout>
  );
}

export default App;
