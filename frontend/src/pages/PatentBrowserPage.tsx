import { useEffect, useMemo, useState } from "react";
import {
  deletePatent,
  getPatentMetadata,
  reprocessPatents,
  type PatentMetadataItem,
  type PatentMetadataSummary
} from "../api/patents";

const PAGE_SIZE = 25;

const EMPTY_SUMMARY: PatentMetadataSummary = {
  total_patents: 0,
  processed_patents: 0,
  unprocessed_patents: 0
};

export function PatentBrowserPage() {
  const [items, setItems] = useState<PatentMetadataItem[]>([]);
  const [summary, setSummary] = useState<PatentMetadataSummary>(EMPTY_SUMMARY);
  const [offset, setOffset] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [filter, setFilter] = useState("");
  const [appliedFilter, setAppliedFilter] = useState("");
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedPatentIds, setSelectedPatentIds] = useState<number[]>([]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await getPatentMetadata(offset, PAGE_SIZE, appliedFilter || undefined);
        if (cancelled) {
          return;
        }
        setItems(response.items);
        setSummary(response.summary);
        setTotal(response.total);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load patent metadata");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [offset, reloadKey, appliedFilter]);

  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const allVisibleSelected = useMemo(
    () => items.length > 0 && items.every((item) => selectedPatentIds.includes(item.patent_id)),
    [items, selectedPatentIds]
  );

  const refresh = () => {
    setReloadKey((current) => current + 1);
    setSelectedPatentIds([]);
  };

  const applyFilter = () => {
    setAppliedFilter(filter.trim());
    setOffset(0);
    setSelectedPatentIds([]);
  };

  const toggleSelection = (patentId: number) => {
    setSelectedPatentIds((current) =>
      current.includes(patentId) ? current.filter((id) => id !== patentId) : [...current, patentId]
    );
  };

  const handleReprocessSelected = async () => {
    if (selectedPatentIds.length === 0) {
      return;
    }
    if (
      !window.confirm(
        `Reprocess ${selectedPatentIds.length} selected patent(s)? Existing embeddings and derived compound fields will be replaced.`
      )
    ) {
      return;
    }
    try {
      const response = await reprocessPatents(selectedPatentIds);
      setMessage(`Queued selected patents for reprocessing. Job ${response.job_id}.`);
      refresh();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to reprocess patents");
    }
  };

  const handleDeletePatent = async (patentCode: string) => {
    if (!window.confirm(`Delete patent ${patentCode} and all of its compounds? This cannot be undone.`)) {
      return;
    }
    try {
      const response = await deletePatent(patentCode);
      setMessage(`Deleted patent ${patentCode} and ${response.affected_count} compound(s).`);
      refresh();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to delete patent");
    }
  };

  return (
    <>
      <section className="panel">
        <div className="browser-toolbar">
          <div>
            <h2>Patent metadata</h2>
            <p className="muted">Patent-level view for filtering, monitoring progress, and managing deletes.</p>
          </div>
          <div className="browser-actions">
            <button className="primary-button" type="button" onClick={refresh} disabled={loading}>
              Refresh
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={handleReprocessSelected}
              disabled={selectedPatentIds.length === 0}
            >
              Reprocess selected
            </button>
          </div>
        </div>
        <div className="grid two browser-filter-grid">
          <div className="field">
            <label htmlFor="patent-filter">Patent code filter</label>
            <input
              id="patent-filter"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="US20250042916A1"
            />
          </div>
          <div className="browser-actions align-end">
            <button className="secondary-button" type="button" onClick={applyFilter}>
              Apply filter
            </button>
          </div>
        </div>
        <div className="summary-strip">
          <div className="summary-card">
            <span className="muted">Total patents</span>
            <strong>{summary.total_patents}</strong>
          </div>
          <div className="summary-card">
            <span className="muted">Processed patents</span>
            <strong>{summary.processed_patents}</strong>
          </div>
          <div className="summary-card">
            <span className="muted">Unprocessed patents</span>
            <strong>{summary.unprocessed_patents}</strong>
          </div>
        </div>
        {message && <p className="status-success">{message}</p>}
        {error && <p className="status-error">{error}</p>}
      </section>

      <section className="panel">
        <div className="browser-pagination">
          <button type="button" onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} disabled={offset === 0 || loading}>
            Previous
          </button>
          <span className="muted">
            Page {currentPage} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setOffset(offset + PAGE_SIZE)}
            disabled={loading || offset + PAGE_SIZE >= total}
          >
            Next
          </button>
        </div>

        {loading ? (
          <p className="muted">Loading patents...</p>
        ) : items.length === 0 ? (
          <p className="muted">No patents matched this filter.</p>
        ) : (
          <div className="compound-table-wrap large">
            <table className="compound-table patent-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={allVisibleSelected}
                      onChange={() =>
                        setSelectedPatentIds(allVisibleSelected ? [] : items.map((item) => item.patent_id))
                      }
                    />
                  </th>
                  <th>Patent ID</th>
                  <th>Patent Code</th>
                  <th>Extraction</th>
                  <th>Total Compounds</th>
                  <th>Processed</th>
                  <th>Unprocessed</th>
                  <th>Failed</th>
                  <th>Created</th>
                  <th>Source URL</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.patent_id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedPatentIds.includes(item.patent_id)}
                        onChange={() => toggleSelection(item.patent_id)}
                      />
                    </td>
                    <td>{item.patent_id}</td>
                    <td>{item.patent_code}</td>
                    <td>
                      <span className="badge">{item.extraction_status}</span>
                    </td>
                    <td>{item.total_compounds}</td>
                    <td>{item.processed_compounds}</td>
                    <td>{item.unprocessed_compounds}</td>
                    <td>{item.failed_compounds}</td>
                    <td>{new Date(item.created_at).toLocaleString()}</td>
                    <td className="compound-url-cell">
                      <a href={item.source_url} target="_blank" rel="noreferrer">
                        {item.source_url}
                      </a>
                      {item.last_error && <p className="status-error compound-row-error">{item.last_error}</p>}
                    </td>
                    <td>
                      <button className="danger-button small" type="button" onClick={() => handleDeletePatent(item.patent_code)}>
                        Delete patent
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
