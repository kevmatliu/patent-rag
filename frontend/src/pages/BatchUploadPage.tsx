import { useEffect, useState } from "react";
import { getJobStatus, uploadPatentPdfs, uploadPatents, type JobLogItem, type PatentBatchItemResult } from "../api/patents";
import { JobLogPanel } from "../components/JobLogPanel";

function isPatentBatchSummary(summary: unknown): summary is { results: PatentBatchItemResult[] } {
  if (!summary || typeof summary !== "object" || !("results" in summary)) {
    return false;
  }
  const results = (summary as { results?: unknown }).results;
  return Array.isArray(results) && (results.length === 0 || typeof results[0] === "object");
}

export function BatchUploadPage() {
  const [urlsText, setUrlsText] = useState("");
  const [results, setResults] = useState<PatentBatchItemResult[]>([]);
  const [logs, setLogs] = useState<JobLogItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);

  useEffect(() => {
    if (!jobId) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    const poll = async () => {
      try {
        const response = await getJobStatus(jobId);
        if (cancelled) {
          return;
        }
        setLogs(response.logs);
        setJobStatus(response.status);
        if (isPatentBatchSummary(response.summary)) {
          setResults(response.summary.results);
        }
        if (response.status === "completed" || response.status === "failed") {
          setSubmitting(false);
          if (response.status === "failed" && response.error) {
            setError(response.error);
          }
          return;
        }
        timeoutId = window.setTimeout(() => {
          void poll();
        }, 250);
      } catch (pollError) {
        if (!cancelled) {
          setSubmitting(false);
          setError(pollError instanceof Error ? pollError.message : "Failed to load job status");
        }
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [jobId]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setResults([]);
    setLogs([]);
    setJobStatus("pending");

    try {
      const urls = urlsText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      const response = await uploadPatents(urls);
      setJobId(response.job_id);
      setJobStatus(response.status);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Patent upload failed");
      setJobStatus("failed");
      setSubmitting(false);
    }
  };

  const handlePdfSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setResults([]);
    setLogs([]);
    setJobStatus("pending");

    try {
      const response = await uploadPatentPdfs(pdfFiles);
      setJobId(response.job_id);
      setJobStatus(response.status);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "PDF upload failed");
      setJobStatus("failed");
      setSubmitting(false);
    }
  };

  return (
    <>
      <section className="panel">
        <form className="grid" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="patent-urls">Google Patents URLs</label>
            <textarea
              id="patent-urls"
              rows={8}
              placeholder="https://patents.google.com/patent/US20250042916A1/en"
              value={urlsText}
              onChange={(event) => setUrlsText(event.target.value)}
            />
          </div>
          <div>
            <button className="primary-button" type="submit" disabled={submitting}>
              {submitting ? "Ingesting..." : "Upload patents"}
            </button>
          </div>
        </form>
        {error && <p className="status-error">{error}</p>}
      </section>

      <section className="panel">
        <form className="grid" onSubmit={handlePdfSubmit}>
          <div className="field">
            <label htmlFor="patent-pdfs">Patent PDFs</label>
            <input
              id="patent-pdfs"
              type="file"
              accept="application/pdf,.pdf"
              multiple
              onChange={(event) => setPdfFiles(Array.from(event.target.files ?? []))}
            />
            <p className="muted">
              Upload one or more PDF files. The patent code will be inferred from each filename, like
              `US20250042916A1.pdf`.
            </p>
          </div>
          <div>
            <button className="primary-button" type="submit" disabled={submitting || pdfFiles.length === 0}>
              {submitting ? "Ingesting..." : "Upload PDFs"}
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>Results</h2>
        {results.length === 0 ? (
          <p className="muted">Submit one or more patent URLs to start extraction.</p>
        ) : (
          <div className="result-list">
            {results.map((item) => (
              <article className="result-card" key={`${item.url}-${item.patent_id ?? "none"}`}>
                <strong>{item.url}</strong>
                <div className="badge-row">
                  <span className="badge">Patent {item.patent_code ?? "n/a"}</span>
                  <span className="badge">Images {item.extracted_images}</span>
                  <span className="badge">Status {item.extraction_status}</span>
                  {item.duplicate && <span className="badge">Duplicate</span>}
                </div>
                {item.error && <p className="status-error">{item.error}</p>}
              </article>
            ))}
          </div>
        )}
      </section>

      <JobLogPanel title="Ingest Logs" status={jobStatus} logs={logs} />
    </>
  );
}
