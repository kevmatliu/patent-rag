import { useState } from "react";
import { KetcherEditor } from "../components/KetcherEditor";
import { SmilesPreview } from "../components/SmilesPreview";
import { useCompoundWorkspaceController } from "../hooks/useCompoundWorkspaceController";

type RecommendationTab = "similar-cores" | "rgroups";

export function RecommendationWorkbenchPage() {
  const controller = useCompoundWorkspaceController();
  const {
    ketcherRef,
    smilesText,
    setSmilesText,
    editorSmiles,
    editorLoading,
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
    attachmentPointOptions,
    handleLoadSmilesIntoEditor,
    handleUseEditorSmiles,
    handleIntegrateCore,
    handleApplyRGroup,
    handleSelectCore
  } = controller;
  const [recommendationTab, setRecommendationTab] = useState<RecommendationTab>("similar-cores");

  return (
    <>
      <section className="panel">
        <div className="workbench-intro">
          <h2>Editor Workbench</h2>
          <p className="muted">Load a structure into Ketcher, then explore similar cores and R-group recommendations.</p>
        </div>
        <div className="search-workbench">
          <div className="search-workbench-panel">
            <div className="ketcher-panel-header">
              <h3>SMILES input</h3>
              <p className="muted">Enter a SMILE string to start.</p>
            </div>
            <div className="field search-drop-field">
              <label htmlFor="workbench-smiles">SMILES input</label>
              <textarea
                id="workbench-smiles"
                rows={8}
                placeholder="CCOC(=O)C1=..."
                value={smilesText}
                onChange={(event) => setSmilesText(event.target.value)}
              />
            </div>
            <div className="browser-actions search-editor-actions">
              <button
                className="secondary-button small"
                type="button"
                onClick={() => void handleLoadSmilesIntoEditor()}
                disabled={editorLoading}
              >
                {editorLoading ? "Updating..." : "Load into editor"}
              </button>
              <button
                className="secondary-button small"
                type="button"
                onClick={() => void handleUseEditorSmiles()}
                disabled={editorLoading}
              >
                Use editor SMILES
              </button>
            </div>
            <div className="search-smiles-preview">
              <strong>Canvas SMILES</strong>
              <p>{editorSmiles || "No structure on the canvas yet."}</p>
            </div>
            <p className="muted search-helper-text">
              Recommendations refresh from the active structure you load from the editor.
            </p>
          </div>

          <div className="search-workbench-panel search-workbench-panel-middle">
            <div className="ketcher-panel-header">
              <div>
                <h3>Structure Editor</h3>
                <p className="muted">Ketcher is mounted here as the main molecule editor.</p>
              </div>
            </div>
            <KetcherEditor ref={ketcherRef} value={editorSmiles} onSmilesChange={() => undefined} />
          </div>

          <div className="search-workbench-panel">
            <div className="recommendation-panel">
              <div className="recommendation-panel-header">
                <div>
                  <h3>Recommendations</h3>
                  <p className="muted">Recommends similar cores and R-groups.</p>
                </div>
              </div>
              <div className="recommendation-tab-row" role="tablist" aria-label="Recommendation tabs">
                <button
                  type="button"
                  className={recommendationTab === "similar-cores" ? "active" : ""}
                  onClick={() => setRecommendationTab("similar-cores")}
                >
                  Similar cores
                </button>
                <button
                  type="button"
                  className={recommendationTab === "rgroups" ? "active" : ""}
                  onClick={() => setRecommendationTab("rgroups")}
                >
                  R-group suggestions
                </button>
              </div>

              {recommendationTab === "similar-cores" ? (
                <div className="recommendation-content">
                  <div className="recommendation-summary">
                    <span className="badge badge-neutral">Selected core</span>
                    <p>{selectedCore || "No core selected yet."}</p>
                  </div>
                  {similarCoresLoading ? (
                    <p className="muted">Loading similar cores...</p>
                  ) : similarCoresError ? (
                    <p className="status-error">{similarCoresError}</p>
                  ) : similarCoreItems.length === 0 ? (
                    <p className="muted">Load a structure into the editor to get similar core recommendations.</p>
                  ) : (
                    <div className="result-list recommendation-list">
                      {similarCoreItems.map((item) => (
                        <article
                          key={`${item.core_smiles}-${item.apply_core_smiles}-${item.score}`}
                          className={`recommendation-card ${selectedCore === item.core_smiles ? "active" : ""}`}
                        >
                          <SmilesPreview smiles={item.apply_core_smiles || item.core_smiles} label="Core" />
                          <div className="badge-row">
                            <span className="badge">Score {item.score.toFixed(4)}</span>
                            <span className="badge badge-neutral">Support {item.support_count}</span>
                          </div>
                          <p className="muted recommendation-reason">{item.reason}</p>
                          <div className="recommendation-actions">
                            <button
                              className="secondary-button small"
                              type="button"
                              onClick={() => handleSelectCore(item.core_smiles, item.apply_core_smiles)}
                            >
                              {selectedCore === item.core_smiles ? "Selected" : "Select"}
                            </button>
                            <button
                              className="primary-button small"
                              type="button"
                              onClick={() => void handleIntegrateCore(item.core_smiles, item.apply_core_smiles)}
                              disabled={applyLoading}
                            >
                              {applyLoading ? "Appending..." : "Append core"}
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="recommendation-content">
                  <div className="field">
                    <label htmlFor="attachment-point">Attachment point</label>
                    <select
                      id="attachment-point"
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
                  <div className="recommendation-summary">
                    <span className="badge badge-neutral">Selected core</span>
                    <p>{selectedCore || "Pick a similar core first."}</p>
                  </div>
                  {rGroupsLoading ? (
                    <p className="muted">Loading R-group suggestions...</p>
                  ) : rGroupsError ? (
                    <p className="status-error">{rGroupsError}</p>
                  ) : rGroupItems.length === 0 ? (
                    <p className="muted">Select a core and attachment point to load R-group suggestions.</p>
                  ) : (
                    <div className="result-list recommendation-list">
                      {rGroupItems.map((item) => (
                        <article key={`${item.rgroup_smiles}-${item.count}`} className="recommendation-card static">
                          <SmilesPreview smiles={item.rgroup_smiles} label={selectedAttachmentPoint} />
                          <div className="badge-row">
                            <span className="badge badge-neutral">Count {item.count}</span>
                          </div>
                          <p className="muted recommendation-reason">{item.reason}</p>
                          <div className="recommendation-actions">
                            <button
                              className="primary-button small"
                              type="button"
                              onClick={() => void handleApplyRGroup(item.rgroup_smiles)}
                              disabled={applyLoading}
                            >
                              {applyLoading ? "Applying..." : `Apply ${selectedAttachmentPoint}`}
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
        {error && <p className="status-error">{error}</p>}
      </section>
    </>
  );
}
