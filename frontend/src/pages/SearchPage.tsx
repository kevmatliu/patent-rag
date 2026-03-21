import { useEffect, useMemo, useState } from "react";
import {
  getJobStatus,
  searchByImageJob,
  searchBySmilesJob,
  type JobLogItem,
  type SearchResponse
} from "../api/patents";
import { JobLogPanel } from "../components/JobLogPanel";
import { ResultCard } from "../components/ResultCard";

function isSearchSummary(summary: unknown): summary is SearchResponse {
  return Boolean(summary && typeof summary === "object" && "query_smiles" in summary && "results" in summary);
}

export function SearchPage() {
  const [mode, setMode] = useState<"image" | "smiles">("image");
  const [file, setFile] = useState<File | null>(null);
  const [smilesText, setSmilesText] = useState("");
  const [k, setK] = useState(5);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<JobLogItem[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);

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
        if (isSearchSummary(response.summary)) {
          setResults(response.summary);
        }

        if (response.status === "completed" || response.status === "failed" || response.status === "cancelled") {
          setLoading(false);
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
          setLoading(false);
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
    setLoading(true);
    setError(null);
    setResults(null);
    setLogs([]);
    setJobStatus("pending");

    try {
      if (mode === "image") {
        if (!file) {
          throw new Error("Select or drop an image first.");
        }
        const response = await searchByImageJob(file, k);
        setJobId(response.job_id);
        setJobStatus(response.status);
        return;
      }

      if (!smilesText.trim()) {
        throw new Error("Enter a SMILES string first.");
      }
      const response = await searchBySmilesJob(smilesText.trim(), k);
      setJobId(response.job_id);
      setJobStatus(response.status);
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : "Search failed");
      setLoading(false);
    }
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    const dropped = event.dataTransfer.files?.[0] ?? null;
    if (dropped) {
      setFile(dropped);
      setMode("image");
    }
  };

  return (
    <>
      <section className="panel">
        <form className="grid two" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="search-mode">Search mode</label>
            <select
              id="search-mode"
              value={mode}
              onChange={(event) => setMode(event.target.value as "image" | "smiles")}
            >
              <option value="image">Image</option>
              <option value="smiles">SMILES</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="neighbors">Top matches</label>
            <input
              id="neighbors"
              type="number"
              min={1}
              max={50}
              value={k}
              onChange={(event) => setK(Number(event.target.value))}
            />
          </div>

          {mode === "image" ? (
            <div className="field search-drop-field">
              <label htmlFor="query-image">Query image</label>
              <div
                className={`dropzone ${dragActive ? "dropzone-active" : ""}`}
                onDragEnter={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={(event) => {
                  event.preventDefault();
                  setDragActive(false);
                }}
                onDrop={handleDrop}
              >
                <p>{file ? file.name : "Drag and drop an image here, or use the file picker."}</p>
                <input
                  id="query-image"
                  type="file"
                  accept="image/*"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
              </div>
            </div>
          ) : (
            <div className="field search-drop-field">
              <label htmlFor="query-smiles">SMILES query</label>
              <textarea
                id="query-smiles"
                rows={5}
                placeholder="CCOC(=O)C1=..."
                value={smilesText}
                onChange={(event) => setSmilesText(event.target.value)}
              />
            </div>
          )}

          <div>
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? "Searching..." : mode === "image" ? "Search by image" : "Search by SMILES"}
            </button>
          </div>
        </form>
        {previewUrl && mode === "image" && <img className="preview-image" src={previewUrl} alt="Query preview" />}
        {error && <p className="status-error">{error}</p>}
      </section>

      <section className="panel">
        <h2>Search results</h2>
        {!results ? (
          <p className="muted">Run an image or SMILES search to find similar stored compounds.</p>
        ) : (
          <>
            <p>
              <strong>Query SMILES:</strong> {results.query_smiles}
            </p>
            <div className="result-list">
              {results.results.map((result) => (
                <ResultCard key={`${result.image_id}-${result.page_number ?? "na"}`} result={result} />
              ))}
            </div>
          </>
        )}
      </section>

      <JobLogPanel title="Search Logs" status={jobStatus} logs={logs} />
    </>
  );
}
