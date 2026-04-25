import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL } from "../api/client";
import {
  deleteCompounds,
  getCompoundRGroups,
  getCompounds,
  getPatentCodes,
  reprocessCompounds,
  type CompoundBrowserItem,
  type CompoundRGroupItem
} from "../api/patents";

const PAGE_SIZE = 50;
type SidebarTab = "overview" | "rgroups";

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
  const [selectedCompound, setSelectedCompound] = useState<CompoundBrowserItem | null>(null);
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("overview");
  const [rGroupItems, setRGroupItems] = useState<CompoundRGroupItem[]>([]);
  const [rGroupsLoading, setRGroupsLoading] = useState(false);
  const [rGroupsError, setRGroupsError] = useState<string | null>(null);
  const [zoomedImage, setZoomedImage] = useState<{ src: string; alt: string } | null>(null);
  const [imageZoom, setImageZoom] = useState(1.6);

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
        setSelectedCompound((current) => {
          if (current == null) {
            return null;
          }
          return response.items.find((item) => item.compound_id === current.compound_id) ?? null;
        });
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

  useEffect(() => {
    if (selectedCompound == null || sidebarTab !== "rgroups") {
      return;
    }

    let cancelled = false;

    const loadRGroups = async () => {
      setRGroupsLoading(true);
      setRGroupsError(null);
      try {
        const response = await getCompoundRGroups(selectedCompound.compound_id);
        if (!cancelled) {
          setRGroupItems(response.items);
        }
      } catch (loadError) {
        if (!cancelled) {
          setRGroupsError(loadError instanceof Error ? loadError.message : "Failed to load child rows");
          setRGroupItems([]);
        }
      } finally {
        if (!cancelled) {
          setRGroupsLoading(false);
        }
      }
    };

    void loadRGroups();
    return () => {
      cancelled = true;
    };
  }, [selectedCompound, sidebarTab]);

  useEffect(() => {
    if (zoomedImage == null) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setZoomedImage(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [zoomedImage]);

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

  const openSidebar = (compound: CompoundBrowserItem, tab: SidebarTab) => {
    setSelectedCompound(compound);
    setSidebarTab(tab);
    if (tab === "overview") {
      setRGroupsError(null);
    }
  };

  const openImageZoom = (imageUrl: string, alt: string) => {
    setZoomedImage({ src: `${API_BASE_URL}${imageUrl}`, alt });
    setImageZoom(1.6);
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

      <div className={`compound-browser-layout ${selectedCompound ? "with-sidebar" : "without-sidebar"}`}>
        <section className="panel compound-browser-main">
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
                    <th>Validation</th>
                    <th>Embedding</th>
                    <th>Duplicate</th>
                    <th>Canonical SMILES</th>
                    <th>Murcko Scaffold</th>
                    <th>Reduced Core</th>
                    <th>Child DB</th>
                    <th>Inspect</th>
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
                        <button
                          className="image-zoom-trigger"
                          type="button"
                          onClick={() => openImageZoom(item.image_url, `Compound ${item.compound_id}`)}
                        >
                          <img
                            className="compound-row-image large"
                            src={`${API_BASE_URL}${item.image_url}`}
                            alt={`Compound ${item.compound_id}`}
                          />
                        </button>
                      </td>
                      <td>
                        <strong>{item.compound_id}</strong>
                        <div className="table-subtext">Page {item.page_number ?? "n/a"}</div>
                      </td>
                      <td>
                        <strong>{item.patent_code}</strong>
                        <div className="table-subtext">{new Date(item.updated_at).toLocaleString()}</div>
                      </td>
                      <td>
                        <div className="badge-row">
                          <span className="badge">{item.processing_status}</span>
                          {item.validation_status && <span className="badge">{item.validation_status}</span>}
                          {item.is_compound === false && <span className="badge badge-danger">non-compound</span>}
                        </div>
                      </td>
                      <td>{item.has_embedding ? "Yes" : "No"}</td>
                      <td>
                        {item.is_duplicate_within_patent ? (
                          <div className="table-subtext">Duplicate of #{item.duplicate_of_compound_id}</div>
                        ) : (
                          <div className="table-subtext">Primary record</div>
                        )}
                      </td>
                      <td className="compound-smiles-cell">{item.canonical_smiles || item.smiles || "No SMILES yet"}</td>
                      <td className="compound-smiles-cell">{item.murcko_scaffold_smiles || "No scaffold"}</td>
                      <td className="compound-smiles-cell">{item.reduced_core || "No reduced core"}</td>
                      <td>
                        <button className="secondary-button small" type="button" onClick={() => openSidebar(item, "rgroups")}>
                          View child DB
                        </button>
                      </td>
                      <td>
                        <button className="secondary-button small" type="button" onClick={() => openSidebar(item, "overview")}>
                          Open sidebar
                        </button>
                        {item.last_error && <p className="status-error compound-row-error">{item.last_error}</p>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {selectedCompound && (
          <aside className="panel compound-sidebar">
            <div className="compound-sidebar-header">
              <div>
                <h3>Compound #{selectedCompound.compound_id}</h3>
                <p className="muted">Patent {selectedCompound.patent_code}</p>
              </div>
              <button className="secondary-button small" type="button" onClick={() => setSelectedCompound(null)}>
                Close
              </button>
            </div>

            <div className="compound-sidebar-tabs" role="tablist" aria-label="Compound details tabs">
              <button
                type="button"
                className={sidebarTab === "overview" ? "active" : ""}
                onClick={() => setSidebarTab("overview")}
              >
                Overview
              </button>
              <button
                type="button"
                className={sidebarTab === "rgroups" ? "active" : ""}
                onClick={() => setSidebarTab("rgroups")}
              >
                Child DB
              </button>
            </div>

            {sidebarTab === "overview" ? (
              <div className="compound-sidebar-body">
                <button
                  className="image-zoom-trigger compound-sidebar-image-button"
                  type="button"
                  onClick={() => openImageZoom(selectedCompound.image_url, `Compound ${selectedCompound.compound_id}`)}
                >
                  <img
                    className="compound-row-image large compound-sidebar-image"
                    src={`${API_BASE_URL}${selectedCompound.image_url}`}
                    alt={`Compound ${selectedCompound.compound_id}`}
                  />
                </button>
                <button
                  className="secondary-button small image-zoom-button"
                  type="button"
                  onClick={() => openImageZoom(selectedCompound.image_url, `Compound ${selectedCompound.compound_id}`)}
                >
                  Zoom image
                </button>
                <div className="detail-grid">
                  <DetailRow label="Processing status" value={selectedCompound.processing_status} />
                  <DetailRow label="Validation status" value={selectedCompound.validation_status} />
                  <DetailRow
                    label="Is compound"
                    value={
                      selectedCompound.is_compound == null ? "Unknown" : selectedCompound.is_compound ? "Yes" : "No"
                    }
                  />
                  <DetailRow label="Canonical SMILES" value={selectedCompound.canonical_smiles || selectedCompound.smiles} multiline />
                  <DetailRow label="Murcko scaffold" value={selectedCompound.murcko_scaffold_smiles} multiline />
                  <DetailRow label="Reduced core" value={selectedCompound.reduced_core} multiline />
                  <DetailRow label="Core SMILES" value={selectedCompound.core_smiles} multiline />
                  <DetailRow label="Core SMARTS" value={selectedCompound.core_smarts} multiline />
                  <DetailRow
                    label="Duplicate within patent"
                    value={
                      selectedCompound.is_duplicate_within_patent
                        ? `Yes, of #${selectedCompound.duplicate_of_compound_id ?? "unknown"}`
                        : "No"
                    }
                  />
                  <DetailRow
                    label="Kept for series analysis"
                    value={selectedCompound.kept_for_series_analysis ? "Yes" : "No"}
                  />
                  <DetailRow label="Validation error" value={selectedCompound.validation_error} multiline />
                  <DetailRow label="Last error" value={selectedCompound.last_error} multiline />
                  <DetailRow label="Pipeline version" value={selectedCompound.pipeline_version} />
                  <DetailRow label="Patent URL" value={selectedCompound.patent_source_url} multiline link />
                  <DetailRow label="Created" value={new Date(selectedCompound.created_at).toLocaleString()} />
                  <DetailRow label="Updated" value={new Date(selectedCompound.updated_at).toLocaleString()} />
                </div>
              </div>
            ) : (
              <div className="compound-sidebar-body">
                {rGroupsLoading ? (
                  <p className="muted">Loading child database rows...</p>
                ) : rGroupsError ? (
                  <p className="status-error">{rGroupsError}</p>
                ) : rGroupItems.length === 0 ? (
                  <p className="muted">No child rows stored for this compound.</p>
                ) : (
                  <div className="child-db-table-wrap">
                    <table className="compound-table child-db-table">
                      <thead>
                        <tr>
                          <th>R Label</th>
                          <th>R Group</th>
                          <th>Core SMILES</th>
                          <th>Core SMARTS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rGroupItems.map((row, index) => (
                          <tr key={`${row.compound_id}-${row.r_label}-${index}`}>
                            <td>{row.r_label}</td>
                            <td className="compound-smiles-cell">{row.r_group}</td>
                            <td className="compound-smiles-cell">{row.core_smiles || "n/a"}</td>
                            <td className="compound-smiles-cell">{row.core_smarts || "n/a"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </aside>
        )}
      </div>

      {zoomedImage && (
        <div className="image-zoom-modal" role="dialog" aria-modal="true" aria-label="Zoomed compound image">
          <div className="image-zoom-backdrop" onClick={() => setZoomedImage(null)} />
          <div className="image-zoom-panel">
            <div className="image-zoom-toolbar">
              <div className="browser-actions">
                <button
                  className="secondary-button small"
                  type="button"
                  onClick={() => setImageZoom((current) => Math.max(0.8, Number((current - 0.2).toFixed(1))))}
                >
                  Zoom out
                </button>
                <button className="secondary-button small" type="button" onClick={() => setImageZoom(1.6)}>
                  Reset
                </button>
                <button
                  className="secondary-button small"
                  type="button"
                  onClick={() => setImageZoom((current) => Math.min(4, Number((current + 0.2).toFixed(1))))}
                >
                  Zoom in
                </button>
              </div>
              <button className="secondary-button small" type="button" onClick={() => setZoomedImage(null)}>
                Close
              </button>
            </div>
            <div className="image-zoom-canvas">
              <img
                className="image-zoom-preview"
                src={zoomedImage.src}
                alt={zoomedImage.alt}
                style={{ transform: `scale(${imageZoom})` }}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

type DetailRowProps = {
  label: string;
  value?: string | null;
  multiline?: boolean;
  link?: boolean;
};

function DetailRow({ label, value, multiline = false, link = false }: DetailRowProps) {
  const displayValue = value?.trim() ? value : "n/a";

  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      {link && displayValue !== "n/a" ? (
        <a className={multiline ? "detail-value multiline" : "detail-value"} href={displayValue} target="_blank" rel="noreferrer">
          {displayValue}
        </a>
      ) : (
        <span className={multiline ? "detail-value multiline" : "detail-value"}>{displayValue}</span>
      )}
    </div>
  );
}
