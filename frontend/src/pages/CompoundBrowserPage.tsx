import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL } from "../api/client";
import {
  deleteCompounds,
  getCompoundDetail,
  getCompounds,
  getCoreCandidateRGroups,
  getPatentCodes,
  reprocessCompounds,
  type CompoundBrowserItem,
  type CompoundCoreCandidateItem,
  type CompoundCoreCandidateRGroupItem
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
  const [selectedCompound, setSelectedCompound] = useState<CompoundBrowserItem | null>(null);
  const [coreCandidates, setCoreCandidates] = useState<CompoundCoreCandidateItem[]>([]);
  const [selectedCoreCandidate, setSelectedCoreCandidate] = useState<CompoundCoreCandidateItem | null>(null);
  const [rGroupItems, setRGroupItems] = useState<CompoundCoreCandidateRGroupItem[]>([]);
  const [scaffoldsLoading, setScaffoldsLoading] = useState(false);
  const [scaffoldsError, setScaffoldsError] = useState<string | null>(null);
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
    if (selectedCompound == null) {
      setCoreCandidates([]);
      setSelectedCoreCandidate(null);
      setRGroupItems([]);
      setScaffoldsError(null);
      setRGroupsError(null);
      return;
    }

    let cancelled = false;

    const loadCompoundDetail = async () => {
      setScaffoldsLoading(true);
      setScaffoldsError(null);
      try {
        const response = await getCompoundDetail(selectedCompound.compound_id);
        if (cancelled) {
          return;
        }
        setSelectedCompound(response.compound);
        setCoreCandidates(response.core_candidates);
        setSelectedCoreCandidate((current) => {
          if (current == null) {
            return response.core_candidates[0] ?? null;
          }
          return response.core_candidates.find((item) => item.id === current.id) ?? response.core_candidates[0] ?? null;
        });
      } catch (loadError) {
        if (!cancelled) {
          setScaffoldsError(loadError instanceof Error ? loadError.message : "Failed to load scaffolds");
          setCoreCandidates([]);
          setSelectedCoreCandidate(null);
        }
      } finally {
        if (!cancelled) {
          setScaffoldsLoading(false);
        }
      }
    };

    void loadCompoundDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedCompound?.compound_id]);

  useEffect(() => {
    if (selectedCoreCandidate == null) {
      setRGroupItems([]);
      setRGroupsError(null);
      return;
    }

    let cancelled = false;

    const loadRGroups = async () => {
      setRGroupsLoading(true);
      setRGroupsError(null);
      try {
        const response = await getCoreCandidateRGroups(selectedCoreCandidate.id);
        if (!cancelled) {
          setRGroupItems(response.items);
        }
      } catch (loadError) {
        if (!cancelled) {
          setRGroupsError(loadError instanceof Error ? loadError.message : "Failed to load R-groups");
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
  }, [selectedCoreCandidate?.id]);

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

  const openScaffoldInspect = (compound: CompoundBrowserItem) => {
    setSelectedCompound(compound);
    setSelectedCoreCandidate(null);
    setRGroupItems([]);
    setScaffoldsError(null);
    setRGroupsError(null);
  };

  const closeInspect = () => {
    setSelectedCompound(null);
    setSelectedCoreCandidate(null);
    setCoreCandidates([]);
    setRGroupItems([]);
    setScaffoldsError(null);
    setRGroupsError(null);
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
      closeInspect();
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
      closeInspect();
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
              Browse stored compounds and inspect scaffold decompositions. Total matching compounds: <strong>{total}</strong>
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

      <div
        className={`compound-browser-layout ${
          selectedCompound ? (selectedCoreCandidate ? "with-two-sidebars" : "with-sidebar") : "without-sidebar"
        }`}
      >
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
                    <th>Embedding</th>
                    <th>Duplicate</th>
                    <th>Canonical SMILES</th>
                    <th>Inspect scaffolds</th>
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
                      <td>{item.has_embedding ? "Yes" : "No"}</td>
                      <td>
                        {item.is_duplicate_within_patent ? (
                          <div className="table-subtext">Duplicate of #{item.duplicate_of_compound_id}</div>
                        ) : (
                          <div className="table-subtext">Primary record</div>
                        )}
                      </td>
                      <td className="compound-smiles-cell">{item.canonical_smiles || item.smiles || "No SMILES yet"}</td>
                      <td>
                        <button className="secondary-button small" type="button" onClick={() => openScaffoldInspect(item)}>
                          Inspect scaffolds
                        </button>
                        <div className="table-subtext">{item.core_candidate_count} scaffold candidate(s)</div>
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
                <h3>Inspect scaffolds</h3>
                <p className="muted">
                  Compound #{selectedCompound.compound_id} · {selectedCompound.patent_code}
                </p>
              </div>
              <button className="secondary-button small" type="button" onClick={closeInspect}>
                Close
              </button>
            </div>

            <div className="compound-sidebar-body">
              {scaffoldsLoading ? (
                <p className="muted">Loading scaffold candidates...</p>
              ) : scaffoldsError ? (
                <p className="status-error">{scaffoldsError}</p>
              ) : coreCandidates.length === 0 ? (
                <p className="muted">No scaffold candidates stored for this compound.</p>
              ) : (
                <div className="scaffold-list">
                  {coreCandidates.map((candidate) => (
                    <button
                      key={candidate.id}
                      type="button"
                      className={`scaffold-list-item ${selectedCoreCandidate?.id === candidate.id ? "active" : ""}`}
                      onClick={() => setSelectedCoreCandidate(candidate)}
                    >
                      <span className="scaffold-list-kicker">
                        {candidate.is_selected ? "Selected" : `Candidate ${candidate.candidate_rank}`}
                      </span>
                      <span className="scaffold-list-smiles">{candidate.core_smiles || "No core SMILES"}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </aside>
        )}

        {selectedCompound && selectedCoreCandidate && (
          <aside className="panel compound-sidebar secondary">
            <div className="compound-sidebar-header">
              <div>
                <h3>Attached R-groups</h3>
                <p className="muted">{selectedCoreCandidate.core_smiles || "No core SMILES"}</p>
              </div>
            </div>

            <div className="compound-sidebar-body">
              {rGroupsLoading ? (
                <p className="muted">Loading R-groups...</p>
              ) : rGroupsError ? (
                <p className="status-error">{rGroupsError}</p>
              ) : rGroupItems.length === 0 ? (
                <p className="muted">No R-groups stored for this scaffold candidate.</p>
              ) : (
                <div className="detail-grid">
                  {rGroupItems.map((row, index) => (
                    <div className="detail-row" key={`${row.core_candidate_id}-${row.r_label}-${index}`}>
                      <span className="detail-label">
                        {row.r_label}
                        {row.attachment_index != null ? ` · attachment ${row.attachment_index}` : ""}
                      </span>
                      <span className="detail-value multiline">{row.r_group_smiles}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
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
