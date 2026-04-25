import { useEffect, useMemo, useState } from "react";
import {
  getJobStatus,
  searchByImageJob,
  searchBySmilesJob,
  searchByStructureJob,
  type JobLogItem,
  type SearchResponse
} from "../api/patents";
import { JobLogPanel } from "../components/JobLogPanel";
import { ResultCard } from "../components/ResultCard";

function isSearchSummary(summary: unknown): summary is SearchResponse {
  return Boolean(summary && typeof summary === "object" && "query_smiles" in summary && "results" in summary);
}

type SearchMode = "image" | "smiles" | "structure";

interface RGroupState {
  label: string;
  smiles: string;
}

const ATTACHMENT_LABELS = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"];

export function SearchPage() {
  const [mode, setMode] = useState<SearchMode>("smiles");
  const [file, setFile] = useState<File | null>(null);
  const [smilesText, setSmilesText] = useState("");
  const [coreSmiles, setCoreSmiles] = useState("");
  const [rGroups, setRGroups] = useState<RGroupState[]>([{ label: "R1", smiles: "" }]);
  const [k, setK] = useState(12);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<JobLogItem[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);

  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;
    let timeoutId: number | null = null;

    const poll = async () => {
      try {
        const response = await getJobStatus(jobId);
        if (cancelled) return;

        setLogs(response.logs);
        setJobStatus(response.status);
        if (isSearchSummary(response.summary)) {
          setResults(response.summary);
          // If in image mode, update the SMILES text with what was recognized
          if (mode === "image" && response.summary.query_smiles) {
            setSmilesText(response.summary.query_smiles);
          }
        }

        if (response.status === "completed" || response.status === "failed" || response.status === "cancelled") {
          setLoading(false);
          if (response.status === "failed" && response.error) {
            setError(response.error);
          }
          return;
        }

        timeoutId = window.setTimeout(() => void poll(), 500);
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
      if (timeoutId !== null) window.clearTimeout(timeoutId);
    };
  }, [jobId, mode]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResults(null);
    setLogs([]);
    setJobStatus("pending");

    try {
      if (mode === "image") {
        if (!file) throw new Error("Select or drop an image first.");
        const response = await searchByImageJob(file, k);
        setJobId(response.job_id);
        setJobStatus(response.status);
      } else if (mode === "smiles") {
        const querySmiles = smilesText.trim();
        if (!querySmiles) throw new Error("Enter a SMILES string first.");
        const response = await searchBySmilesJob(querySmiles, k);
        setJobId(response.job_id);
        setJobStatus(response.status);
      } else if (mode === "structure") {
        const rGroupMap: Record<string, string> = {};
        rGroups.forEach((rg) => {
          if (rg.smiles.trim()) {
            rGroupMap[rg.label] = rg.smiles.trim();
          }
        });

        if (!coreSmiles.trim() && Object.keys(rGroupMap).length === 0) {
          throw new Error("Enter at least a Core or one R-group.");
        }

        const response = await searchByStructureJob({
          core_smiles: coreSmiles.trim() || undefined,
          r_groups: rGroupMap,
          k
        });
        setJobId(response.job_id);
        setJobStatus(response.status);
      }
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

  const addRGroup = () => {
    const nextIdx = rGroups.length + 1;
    if (nextIdx > 8) return;
    setRGroups([...rGroups, { label: `R${nextIdx}`, smiles: "" }]);
  };

  const removeRGroup = (index: number) => {
    setRGroups(rGroups.filter((_, i) => i !== index));
  };

  const updateRGroup = (index: number, field: keyof RGroupState, value: string) => {
    const next = [...rGroups];
    next[index] = { ...next[index], [field]: value };
    setRGroups(next);
  };

  return (
    <div className="search-container">
      <div className="search-hero">
        <h2>Chemical Structure Search</h2>
        <p className="muted">Search across patent compounds via image, SMILES similarity, or exact R-group combinations.</p>
      </div>

      <div className="search-tabs" role="tablist" aria-label="Search input type">
        <button
          type="button"
          className={`search-tab-btn ${mode === "smiles" ? "active" : ""}`}
          onClick={() => setMode("smiles")}
        >
          <span>SMILES Similarity</span>
        </button>
        <button
          type="button"
          className={`search-tab-btn ${mode === "image" ? "active" : ""}`}
          onClick={() => setMode("image")}
        >
          <span>Image Recognition</span>
        </button>
        <button
          type="button"
          className={`search-tab-btn ${mode === "structure" ? "active" : ""}`}
          onClick={() => setMode("structure")}
        >
          <span>Structure Search</span>
        </button>
      </div>

      <section className="search-card">
        <form onSubmit={handleSubmit}>
          <div className="search-form-grid">
            {mode === "smiles" && (
              <div className="field">
                <label htmlFor="query-smiles">SMILES Query</label>
                <textarea
                  id="query-smiles"
                  rows={4}
                  placeholder="e.g. CCOC(=O)C1=C(CN(C)C)C=C2..."
                  value={smilesText}
                  onChange={(e) => setSmilesText(e.target.value)}
                  className="search-textarea"
                />
                <p className="muted small">Uses ChemBERTa embeddings to find visually and chemically similar compounds.</p>
              </div>
            )}

            {mode === "image" && (
              <div className="field">
                <label>Query Image</label>
                <div
                  data-testid="image-dropzone"
                  className={`dropzone ${dragActive ? "dropzone-active" : ""} ${file ? "has-file" : ""}`}
                  onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
                  onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
                  onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
                  onDrop={handleDrop}
                >
                  {previewUrl ? (
                    <img src={previewUrl} alt="Preview" className="preview-image-centered" />
                  ) : (
                    <div className="dropzone-prompt">
                      <p>Drag & drop or <strong>browse</strong></p>
                      <span className="muted small">Supports PNG, JPG, TIFF</span>
                    </div>
                  )}
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                </div>
              </div>
            )}

            {mode === "structure" && (
              <div className="field">
                <div className="structure-search-layout">
                  <div className="field">
                    <label htmlFor="core-smiles">Core Structure (SMILES)</label>
                    <input
                      id="core-smiles"
                      type="text"
                      placeholder="e.g. c1ccccc1"
                      value={coreSmiles}
                      onChange={(e) => setCoreSmiles(e.target.value)}
                    />
                    <p className="muted small">Ranking will be based on similarity to this core.</p>
                  </div>

                  <div className="r-group-manager">
                    <div className="r-group-header">
                      <label>R-Group Subsets (Exact Match)</label>
                      <button type="button" className="secondary-button small" onClick={addRGroup} disabled={rGroups.length >= 8}>
                        Add R-Group
                      </button>
                    </div>
                    {rGroups.map((rg, idx) => (
                      <div key={idx} className="r-group-input-row">
                        <select
                          className="r-group-label-select"
                          value={rg.label}
                          onChange={(e) => updateRGroup(idx, "label", e.target.value)}
                        >
                          {ATTACHMENT_LABELS.map((label) => (
                            <option key={label} value={label}>{label}</option>
                          ))}
                        </select>
                        <input
                          type="text"
                          placeholder="Fragment SMILES (e.g. CC)"
                          value={rg.smiles}
                          onChange={(e) => updateRGroup(idx, "smiles", e.target.value)}
                        />
                        <button type="button" className="btn-icon danger" onClick={() => removeRGroup(idx)} title="Remove">
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div className="search-action-bar">
              <div className="field-inline">
                <label htmlFor="limit">Matches</label>
                <input
                  id="limit"
                  type="number"
                  min={1}
                  max={50}
                  value={k}
                  onChange={(e) => setK(Number(e.target.value))}
                  style={{ width: "80px" }}
                />
              </div>

              <button className="primary-button large-btn" type="submit" disabled={loading}>
                {loading ? "Searching..." : "Execute Search"}
              </button>
            </div>
          </div>
        </form>
        {error && <p className="status-error mt-4">{error}</p>}
      </section>

      {results && (
        <section className="search-results-section">
          <div className="search-results-header">
            <h3>Search Results</h3>
            <span className="badge badge-neutral">{results.results.length} compounds found</span>
          </div>
          <div className="search-result-grid">
            {results.results.map((result) => (
              <ResultCard 
                key={`${result.image_id}-${result.page_number ?? ""}`} 
                result={result} 
                searchMode={mode}
              />
            ))}
          </div>
        </section>
      )}

      {!results && !loading && (
        <div className="empty-state">
          <p className="muted">Specify your search criteria above to explore patent compounds.</p>
        </div>
      )}

      <JobLogPanel title={mode === "structure" ? "Structure Search Progress" : "Search Progress"} status={jobStatus} logs={logs} />
    </div>
  );
}
