import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL } from "../api/client";
import {
  deleteCompounds,
  getCompounds,
  getPatentCodes,
  reprocessCompounds,
  type CompoundBrowserItem
} from "../api/patents";

const PAGE_SIZE = 50;

export function CompoundBrowserPage() {
  const [items, setItems] = useState<CompoundBrowserItem[]>([]);
  const [patentCodes, setPatentCodes] = useState<string[]>([]);
  const [selectedPatentCode, setSelectedPatentCode] = useState("");
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadPatentCodes = async () => {
      try {
        const response = await getPatentCodes();
        if (!cancelled) {
          setPatentCodes(response);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load patent codes");
        }
      }
    };

    void loadPatentCodes();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await getCompounds(offset, PAGE_SIZE, selectedPatentCode || undefined);
        if (cancelled) {
          return;
        }
        setItems(response.items);
        setTotal(response.total);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load compounds");
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
  }, [offset, reloadKey, selectedPatentCode]);

  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const allVisibleSelected = useMemo(
    () => items.length > 0 && items.every((item) => selectedIds.includes(item.compound_id)),
    [items, selectedIds]
  );

  const refresh = () => {
    setReloadKey((current) => current + 1);
    setSelectedIds([]);
  };

  const toggleSelection = (compoundId: number) => {
    setSelectedIds((current) =>
      current.includes(compoundId) ? current.filter((id) => id !== compoundId) : [...current, compoundId]
    );
  };

  const handlePatentFilterChange = (patentCode: string) => {
    setSelectedPatentCode(patentCode);
    setOffset(0);
    setSelectedIds([]);
    setMessage(null);
  };

  const handleDeleteSelected = async () => {
    if (selectedIds.length === 0) {
      return;
    }
    if (!window.confirm(`Delete ${selectedIds.length} selected compound(s)? This cannot be undone.`)) {
      return;
    }
    try {
      const response = await deleteCompounds(selectedIds);
      setMessage(`Deleted ${response.affected_count} compound(s).`);
      refresh();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to delete compounds");
    }
  };

  const handleReprocessSelected = async () => {
    if (selectedIds.length === 0) {
      return;
    }
    if (!window.confirm(`Reprocess ${selectedIds.length} selected compound(s)? Existing embeddings will be replaced.`)) {
      return;
    }
    try {
      const response = await reprocessCompounds(selectedIds);
      setMessage(`Queued selected compounds for reprocessing. Job ${response.job_id}.`);
      refresh();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to reprocess compounds");
    }
  };

  return (
    <>
      <section className="panel">
        <div className="browser-toolbar">
          <div>
            <h2>Existing compounds</h2>
            <p className="muted">
              Browse stored compounds and filter by patent. Total matching compounds: <strong>{total}</strong>
            </p>
          </div>
          <div className="browser-actions">
            <button className="primary-button" type="button" onClick={refresh} disabled={loading}>
              Refresh
            </button>
            <button className="secondary-button" type="button" onClick={handleReprocessSelected} disabled={selectedIds.length === 0}>
              Reprocess selected
            </button>
            <button className="danger-button" type="button" onClick={handleDeleteSelected} disabled={selectedIds.length === 0}>
              Delete selected
            </button>
          </div>
        </div>
        <div className="grid two browser-filter-grid">
          <div className="field">
            <label htmlFor="compound-patent-filter">Filter by patent</label>
            <select
              id="compound-patent-filter"
              value={selectedPatentCode}
              onChange={(event) => handlePatentFilterChange(event.target.value)}
            >
              <option value="">All patents</option>
              {patentCodes.map((patentCode) => (
                <option key={patentCode} value={patentCode}>
                  {patentCode}
                </option>
              ))}
            </select>
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
          <p className="muted">Loading compounds...</p>
        ) : items.length === 0 ? (
          <p className="muted">No compounds stored for this filter yet.</p>
        ) : (
          <div className="compound-table-wrap large">
            <table className="compound-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={allVisibleSelected}
                      onChange={() =>
                        setSelectedIds(allVisibleSelected ? [] : items.map((item) => item.compound_id))
                      }
                    />
                  </th>
                  <th>Image</th>
                  <th>Compound ID</th>
                  <th>Patent</th>
                  <th>Page</th>
                  <th>Status</th>
                  <th>Embedding</th>
                  <th>SMILES</th>
                  <th>Patent URL</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.compound_id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(item.compound_id)}
                        onChange={() => toggleSelection(item.compound_id)}
                      />
                    </td>
                    <td>
                      <img
                        className="compound-row-image large"
                        src={`${API_BASE_URL}${item.image_url}`}
                        alt={`Compound ${item.compound_id}`}
                      />
                    </td>
                    <td>{item.compound_id}</td>
                    <td>{item.patent_code}</td>
                    <td>{item.page_number ?? "n/a"}</td>
                    <td>
                      <span className="badge">{item.processing_status}</span>
                    </td>
                    <td>{item.has_embedding ? "Yes" : "No"}</td>
                    <td className="compound-smiles-cell">{item.smiles || "No SMILES yet"}</td>
                    <td className="compound-url-cell">
                      <a href={item.patent_source_url} target="_blank" rel="noreferrer">
                        {item.patent_source_url}
                      </a>
                      {item.last_error && <p className="status-error compound-row-error">{item.last_error}</p>}
                    </td>
                    <td>{new Date(item.created_at).toLocaleString()}</td>
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
