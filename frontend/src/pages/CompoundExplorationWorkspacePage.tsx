import { KetcherEditor } from "../components/KetcherEditor";
import { SmilesHoverPreview } from "../components/SmilesHoverPreview";
import { SmilesPreview } from "../components/SmilesPreview";
import { WorkspacePanelShell } from "../components/WorkspacePanelShell";
import { useCompoundWorkspaceController } from "../hooks/useCompoundWorkspaceController";
import { useState } from "react";

const CORES_PER_PAGE = 4;

export function CompoundExplorationWorkspacePage() {
  const controller = useCompoundWorkspaceController();
  const {
    ketcherRef,
    smilesText,
    setSmilesText,
    editorSmiles,
    editorLoading,
    analysisLoading,
    applyLoading,
    error,
    similarCoreItems,
    rGroupItems,
    selectedCore,
    selectedAttachmentPoint,
    setSelectedAttachmentPoint,
    similarCoresLoading,
    rGroupsLoading,
    similarCoresError,
    rGroupsError,
    decomposition,
    attachmentPointOptions,
    analysisStale,
    handleLoadSmilesIntoEditor,
    handleUseEditorSmiles,
    handleAnalyzeScaffold,
    handleClearDraft,
    handleSelectCore,
    handleIntegrateCore,
    handleApplyCoreToScaffold,
    handleIntegrateRGroup,
    handleApplyRGroup
  } = controller;

  const [corePage, setCorePage] = useState(0);
  const [expandedCoreSmiles, setExpandedCoreSmiles] = useState<string | null>(null);
  const [searchMode, setSearchMode] = useState<"smiles" | "image">("smiles");

  const totalCorePages = Math.ceil(similarCoreItems.length / CORES_PER_PAGE);
  const visibleCores = similarCoreItems.slice(
    corePage * CORES_PER_PAGE,
    (corePage + 1) * CORES_PER_PAGE
  );

  const handleToggleExpandCore = (coreSmiles: string, applyCoreSmiles: string) => {
    if (expandedCoreSmiles === coreSmiles) {
      setExpandedCoreSmiles(null);
    } else {
      setExpandedCoreSmiles(coreSmiles);
      handleSelectCore(coreSmiles, applyCoreSmiles);
    }
  };

  return (
    <div className="compound-exploration-page">
      <div className="exploration-header-row">
        <WorkspacePanelShell
          title="Global Search"
          description="Search compounds, patents, and scaffolds."
          className="exploration-header-panel exploration-header-search"
          actions={
            <div className="button-group">
              <button
                className={`secondary-button xsmall ${searchMode === "smiles" ? "active" : ""}`}
                type="button"
                onClick={() => setSearchMode("smiles")}
              >
                SMILES
              </button>
              <button
                className={`secondary-button xsmall ${searchMode === "image" ? "active" : ""}`}
                type="button"
                onClick={() => setSearchMode("image")}
              >
                Image
              </button>
            </div>
          }
        >
          <div className="compound-exploration-searchbar">
            {searchMode === "smiles" ? (
              <div className="workspace-search-field field">
                <span className="workspace-search-label">SMILES Search</span>
                <input
                  id="compound-exploration-global-search"
                  type="search"
                  placeholder="Enter SMILES to search..."
                />
              </div>
            ) : (
              <div className="search-dropzone-placeholder">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                  <circle cx="8.5" cy="8.5" r="1.5"></circle>
                  <polyline points="21 15 16 10 5 21"></polyline>
                </svg>
                <p>Drop structure image or <span>Browse</span></p>
              </div>
            )}
          </div>
        </WorkspacePanelShell>

        <WorkspacePanelShell
          title="Exploration Map"
          description="Visual navigation and cluster overlays."
          className="exploration-header-panel exploration-header-map"
        >
          <div className="workspace-placeholder-map-inline">
            <div className="map-placeholder-meta">
              <span className="workspace-kicker">Cluster View</span>
              <p className="muted">Placeholder for interactive chemical space map.</p>
            </div>
            <div className="map-placeholder-actions">
              <button className="secondary-button xsmall" disabled>Recenter</button>
              <button className="secondary-button xsmall" disabled>Filter</button>
            </div>
          </div>
        </WorkspacePanelShell>
      </div>

      <div className="compound-exploration-main-layout" data-resizable-ready="true">
        <WorkspacePanelShell
          title="Scaffold Analysis"
          description="Detailed structural decomposition."
          className="compound-exploration-panel compound-exploration-panel-analysis"
        >
          <div className="analysis-panel-stack">
            <div className="compound-editor-canvas-footer">
              <SmilesPreview
                label={analysisStale ? "Active Structure (Analysis Stale)" : "Active Structure"}
                smiles={editorSmiles || "No structure on canvas."}
              />
            </div>

            <div className="compound-analysis-body">
              {decomposition ? (
                <div className="compound-analysis-grid">
                  <div className="analysis-header-minimal">
                    <span className="workspace-kicker">Results</span>
                    {analysisStale ? <span className="badge badge-neutral">Stale</span> : null}
                  </div>
                  <SmilesHoverPreview smiles={decomposition.reduced_core}>
                    <div>
                      <SmilesPreview label="Reduced Core" smiles={decomposition.reduced_core} />
                    </div>
                  </SmilesHoverPreview>
                  <SmilesHoverPreview smiles={decomposition.labeled_core_smiles}>
                    <div>
                      <SmilesPreview label="Labeled Core" smiles={decomposition.labeled_core_smiles} />
                    </div>
                  </SmilesHoverPreview>
                  
                  <div className="compound-analysis-section">
                    <span className="workspace-kicker">Attachment Points</span>
                    <div className="compound-analysis-chip-row">
                      {decomposition.attachment_points.map((point) => (
                        <span key={point} className="badge badge-neutral">{point}</span>
                      ))}
                    </div>
                  </div>

                  <div className="compound-analysis-section">
                    <span className="workspace-kicker">Extracted R-groups</span>
                    <div className="compound-analysis-rgroup-list">
                      {decomposition.r_groups.map((item) => (
                        <SmilesHoverPreview key={`${item.r_label}-${item.r_group}`} smiles={item.r_group}>
                          <div className="compound-analysis-rgroup-row">
                            <span className="compound-analysis-rgroup-label">{item.r_label}</span>
                            <code>{item.r_group}</code>
                          </div>
                        </SmilesHoverPreview>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="workspace-inline-state workspace-inline-state-soft">
                  <strong>No analysis run</strong>
                  <p className="muted small">
                    Click "Analyze Scaffold" in the editor to populate structural decomposition data.
                  </p>
                </div>
              )}
            </div>
          </div>
        </WorkspacePanelShell>

        <WorkspacePanelShell
          title="Structure Editor"
          description="Import, analyze, and modify chemical structures."
          className="compound-exploration-panel compound-exploration-panel-editor"
        >
          <div className="workspace-editor-stack">
            <div className="compound-editor-toolbar-shell">
              <div className="compound-editor-input-stack">
                <label className="compound-editor-smiles-field" htmlFor="exploration-workspace-smiles">
                  <span className="workspace-search-label">SMILES Input</span>
                  <textarea
                    id="exploration-workspace-smiles"
                    rows={2}
                    placeholder="Paste SMILES string..."
                    value={smilesText}
                    onChange={(event) => setSmilesText(event.target.value)}
                  />
                </label>
              </div>
              <div className="compound-editor-toolbar-actions-row">
                <div className="compound-editor-actions-left">
                  <button
                    className="primary-button small"
                    type="button"
                    onClick={() => void handleLoadSmilesIntoEditor()}
                    disabled={editorLoading}
                    title="Load SMILES into the editor"
                  >
                    {editorLoading ? "Updating..." : "Load into editor"}
                  </button>
                  <button
                    className="secondary-button small"
                    type="button"
                    onClick={() => void handleAnalyzeScaffold()}
                    disabled={analysisLoading}
                    title="Analyze scaffold"
                  >
                    {analysisLoading ? "Analyzing..." : "Analyze Scaffold"}
                  </button>
                </div>
                <div className="compound-editor-actions-right">
                  <button
                    className="btn-icon"
                    type="button"
                    onClick={() => void handleUseEditorSmiles()}
                    disabled={editorLoading}
                    title="Copy from Ketcher"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="9 11 12 14 22 4"></polyline>
                      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
                    </svg>
                  </button>
                  <button
                    className="btn-icon"
                    type="button"
                    onClick={() => undefined}
                    disabled
                    title="Save Snapshot"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                      <polyline points="17 21 17 13 7 13 7 21"></polyline>
                      <polyline points="7 3 7 8 15 8"></polyline>
                    </svg>
                  </button>
                  <button
                    className="btn-icon danger"
                    type="button"
                    onClick={() => void handleClearDraft()}
                    disabled={editorLoading}
                    title="Clear Draft"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      <line x1="10" y1="11" x2="10" y2="17"></line>
                      <line x1="14" y1="11" x2="14" y2="17"></line>
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            {error ? (
              <div className="workspace-inline-state workspace-inline-state-error" role="alert">
                <strong>Workspace issue</strong>
                <p>{error}</p>
              </div>
            ) : null}

            <KetcherEditor ref={ketcherRef} value={editorSmiles} onSmilesChange={() => undefined} />
          </div>
        </WorkspacePanelShell>

        <WorkspacePanelShell
          title="Recommendations"
          description="Suggested cores and attachment-specific R-groups."
          className="compound-exploration-panel compound-exploration-panel-recommendations"
        >
          <div className="recommendation-section-stack">
            <div className="recommendation-panel-intro">
              <div>
                <span className="workspace-kicker">Recommendation Context</span>
                <p className="muted">
                  Core suggestions reshape the scaffold. R-group suggestions stay attachment-specific once scaffold
                  analysis has been run.
                </p>
              </div>
            </div>

            <section className="recommendation-cluster recommendation-cluster-core">
              <div className="recommendation-cluster-header">
                <div>
                  <span className="workspace-kicker">Recommendations</span>
                  <h3>Core Suggestions</h3>
                </div>
                {totalCorePages > 1 ? (
                  <div className="pagination-controls">
                    <button
                      className="secondary-button pagination-btn"
                      disabled={corePage === 0}
                      onClick={() => setCorePage(corePage - 1)}
                    >
                      &larr;
                    </button>
                    <span className="pagination-info">
                      Page {corePage + 1} of {totalCorePages}
                    </span>
                    <button
                      className="secondary-button pagination-btn"
                      disabled={corePage >= totalCorePages - 1}
                      onClick={() => setCorePage(corePage + 1)}
                    >
                      &rarr;
                    </button>
                  </div>
                ) : null}
              </div>
              {similarCoresLoading ? (
                <div className="workspace-inline-state workspace-inline-state-soft">
                  <strong>Loading recommendations</strong>
                </div>
              ) : similarCoresError ? (
                <div className="workspace-inline-state workspace-inline-state-error" role="alert">
                  <strong>Error loading suggestions</strong>
                </div>
              ) : visibleCores.length === 0 ? (
                <div className="workspace-inline-state workspace-inline-state-soft">
                  <strong>No suggestions yet</strong>
                </div>
              ) : (
                <div className="recommendation-card-list">
                  {visibleCores.map((item) => {
                    const isExpanded = expandedCoreSmiles === item.core_smiles;
                    return (
                      <article
                        key={`${item.core_smiles}-${item.apply_core_smiles}-${item.score}`}
                        className={`recommendation-card recommendation-card-dense recommendation-card-core ${
                          selectedCore === item.core_smiles ? "active" : ""
                        } ${isExpanded ? "expanded" : ""}`}
                      >
                        <div className="recommendation-card-topline">
                          <span className="recommendation-kind-pill">Core</span>
                          <div className="badge-row">
                            <span className="badge">Score {item.score.toFixed(4)}</span>
                          </div>
                        </div>
                        <SmilesHoverPreview smiles={item.apply_core_smiles || item.core_smiles}>
                          <div>
                            <SmilesPreview smiles={item.apply_core_smiles || item.core_smiles} label="Core" />
                          </div>
                        </SmilesHoverPreview>
                        <p className="muted recommendation-reason">{item.reason}</p>
                        <div className="recommendation-actions recommendation-actions-compact">
                          <button
                            className="primary-button small"
                            type="button"
                            onClick={() => void handleIntegrateCore(item.core_smiles, item.apply_core_smiles)}
                            disabled={applyLoading}
                            title="Add this core to editor"
                          >
                            Add
                          </button>
                          <button
                            className="secondary-button small"
                            type="button"
                            onClick={() => handleToggleExpandCore(item.core_smiles, item.apply_core_smiles)}
                            title="View attachment suggestions"
                          >
                            {isExpanded ? "Hide Attachments" : "Inspect Attachments"}
                          </button>
                        </div>

                        {isExpanded ? (
                          <div className="nested-rgroup-view">
                            <div className="nested-rgroup-header">
                              <span className="workspace-kicker">R-groups</span>
                              <div className="field recommendation-inline-field">
                                <select
                                  id="exploration-attachment-point"
                                  value={selectedAttachmentPoint}
                                  onChange={(event) => setSelectedAttachmentPoint(event.target.value)}
                                >
                                  {attachmentPointOptions.map((option) => (
                                    <option key={option} value={option}>
                                      {option}
                                    </option>
                                  ))}
                                </select>
                              </div>
                            </div>

                            {rGroupsLoading ? (
                                <p className="muted small">Loading attachments...</p>
                            ) : rGroupItems.length === 0 ? (
                                <p className="muted small">No attachments found.</p>
                            ) : (
                              <div className="nested-rgroup-list">
                                {rGroupItems.map((rg) => (
                                  <div key={`${rg.rgroup_smiles}-${rg.count}`} className="nested-rgroup-item">
                                    <div className="nested-rgroup-card">
                                      <SmilesHoverPreview smiles={rg.rgroup_smiles}>
                                        <div>
                                          <SmilesPreview smiles={rg.rgroup_smiles} label={selectedAttachmentPoint} />
                                        </div>
                                      </SmilesHoverPreview>
                                      <div className="nested-rgroup-actions">
                                        <button
                                          className="secondary-button xsmall"
                                          type="button"
                                          onClick={() => void handleIntegrateRGroup(rg.rgroup_smiles)}
                                          disabled={applyLoading}
                                        >
                                          Add
                                        </button>
                                        <button
                                          className="primary-button xsmall"
                                          type="button"
                                          onClick={() => void handleApplyRGroup(rg.rgroup_smiles)}
                                          disabled={applyLoading}
                                        >
                                          Apply
                                        </button>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        </WorkspacePanelShell>
      </div>

      <WorkspacePanelShell
        title="Exploration History"
        description="Pinned bottom rail for prior structures, saved waypoints, and return-to-state navigation."
      >
        <div className="workspace-history-grid">
          <div className="workspace-placeholder-card">
            <span className="workspace-kicker">History 1</span>
            <p className="muted">Recent explored compounds and editor snapshots will appear in chronological order.</p>
          </div>
          <div className="workspace-placeholder-card">
            <span className="workspace-kicker">History 2</span>
            <p className="muted">This footer rail is sized for timeline entries, saved states, and backtracking actions.</p>
          </div>
        </div>
      </WorkspacePanelShell>
    </div>
  );
}
