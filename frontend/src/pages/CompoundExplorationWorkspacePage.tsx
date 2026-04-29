import { CompoundExplorationLayout } from "../components/CompoundExplorationLayout";
import { CompoundSpaceMapPanel } from "../components/CompoundSpaceMapPanel";
import { KetcherEditor } from "../components/KetcherEditor";
import { RecommendationPanel } from "../components/recommendations/RecommendationPanel";
import type { RecommendationTabId } from "../components/recommendations/RecommendationTabs";
import { SmilesHoverPreview, SmilesStructurePreview } from "../components/SmilesHoverPreview";
import { SmilesPreview } from "../components/SmilesPreview";
import { WorkspacePanelShell } from "../components/WorkspacePanelShell";
import { useCompoundWorkspaceController } from "../hooks/useCompoundWorkspaceController";
import {
  searchByImage,
  searchBySmiles,
  searchByImageJob,
  getJobStatus,
  saveCompoundToDatabase,
  removeCompoundFromDatabase,
  getPatentCodes,
  type CompoundSpaceCluster,
  type CompoundSpaceNode,
  type SearchResultItem,
  type JobLogItem,
  type SearchResponse
} from "../api/patents";
import { useEffect, useRef, useState } from "react";
import { FiCamera, FiClipboard } from "react-icons/fi";

function isSearchSummary(summary: unknown): summary is SearchResponse {
  return typeof summary === "object" && summary !== null && "results" in summary;
}

function AnalysisResultItem({ 
  label, 
  smiles, 
  isSmall = false, 
  onCopy,
  onZoom
}: { 
  label: string; 
  smiles: string; 
  isSmall?: boolean; 
  onCopy: (s: string) => void;
  onZoom: (s: string, l: string) => void;
}) {
  return (
    <div className={`analysis-result-item ${isSmall ? 'is-small' : ''}`} style={{ marginBottom: isSmall ? "1rem" : "1.25rem" }}>
      <span className="workspace-kicker" style={{ fontSize: '11px', marginBottom: '2px', display: 'block', opacity: 0.8 }}>{label}</span>
      <button 
        type="button"
        className="analysis-structure-box-btn"
        onClick={() => onZoom(smiles, label)}
        style={{ 
          background: "white",
          padding: 0,
          borderRadius: "6px",
          border: "1px solid var(--border-color)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          transformOrigin: "top left",
          cursor: "zoom-in",
          width: isSmall ? "120px" : "280px",
          height: isSmall ? "120px" : "280px",
        }}
      >
        <div style={{ 
          width: isSmall ? "120px" : "280px",
          height: isSmall ? "120px" : "280px",
          // overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          margin: 0,
          padding: 0
        }}>
          <SmilesStructurePreview smiles={smiles} />
        </div>
      </button>
      <div style={{ 
        display: 'flex', 
        // justifyContent: 'center',
        // alignItems: 'center',
        margin: 0,
        padding: 0
      }}>
        <code style={{ 
          fontSize: isSmall ? '10px' : '11px',
          color: 'var(--text-secondary)',
          wordBreak: 'break-all',
          whiteSpace: 'normal',
          lineHeight: 1.1,
          margin: 0,
          padding: 0
        }}>
          {smiles}
        </code>
        <button 
          className="btn-icon xsmall" 
          onClick={(e) => {
            e.stopPropagation();
            onCopy(smiles);
          }}
          title="Copy SMILES"
          style={{ padding: '0px', display: 'flex', justifyContent: 'center', minWidth: '24px' }}
        >
          <FiClipboard style={{ fontSize: isSmall ? '11px' : '13px' }} />
        </button>
      </div>
    </div>
  );
}

export function CompoundExplorationWorkspacePage() {
  const controller = useCompoundWorkspaceController();
  const {
    ketcherRef,
    editorSmiles,
    resolveSmilesQuery,
    analysisLoading,
    editorLoading,
    applyLoading,
    error,
    similarCoreItems,
    rGroupItems,
    selectedMapCompound,
    selectedMapCluster,
    similarCoresLoading,
    similarCoresError,
    exactCoreRecommendations,
    activeRecommendationCore,
    exactCoreLoading,
    exactCoreError,
    editorMode,
    modeSubtitle,
    decomposition,
    decomposedEditorState,
    activeCoreSmiles,
    recommendationSmilesText,
    setRecommendationSmilesText,
    analysisStale,
    handleEditorSmilesChange,
    handleLoadStructureIntoEditor,
    handleAnalyzeScaffold,
    handleRecommendFromCoreSmiles,
    handleSwitchEditorMode,
    handleClearDraft,
    handleSelectCompoundFromMap,
    handleSelectMapCluster,
    handleIntegrateCore,
    handleIntegrateRGroup,
  } = controller;

  const [recommendationTab, setRecommendationTab] = useState<RecommendationTabId>("rgroup-recommendations");
  const [similarCorePage, setSimilarCorePage] = useState(0);
  const [exactColumnPages, setExactColumnPages] = useState<Record<string, number>>({});
  const [mapNodes, setMapNodes] = useState<CompoundSpaceNode[]>([]);
  const [smilesSearchText, setSmilesSearchText] = useState("");
  const [imageSearchFile, setImageSearchFile] = useState<File | null>(null);
  
  // Advanced Settings State
  const [isAdvancedSettingsOpen, setIsAdvancedSettingsOpen] = useState(false);
  const [searchLimit, setSearchLimit] = useState(10);
  const [patentFilterList, setPatentFilterList] = useState<string[]>([]);
  const [availablePatentCodes, setAvailablePatentCodes] = useState<string[]>([]);
  const [patentSearchText, setPatentSearchText] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [searchJobId, setSearchJobId] = useState<string | null>(null);
  const [searchLogs, setSearchLogs] = useState<JobLogItem[]>([]);
  const [zoomedSmiles, setZoomedSmiles] = useState<{ smiles: string; label: string } | null>(null);
  const [imageZoom, setImageZoom] = useState(1.6);
  
  useEffect(() => {
    getPatentCodes().then(setAvailablePatentCodes).catch(console.error);
  }, []);

  useEffect(() => {
    if (!searchJobId) return;

    let cancelled = false;
    let timeoutId: number | null = null;

    const poll = async () => {
      try {
        const response = await getJobStatus(searchJobId);
        if (cancelled) return;

        setSearchLogs(response.logs);
        if (isSearchSummary(response.summary)) {
          if (response.summary.query_x !== undefined) setSearchQueryX(response.summary.query_x);
          if (response.summary.query_y !== undefined) setSearchQueryY(response.summary.query_y);
          setSearchQuerySmiles(response.summary.query_smiles);
          
          applyRankedHighlights(resolveSearchMatchesToMapNodes(response.summary.results));
          if (response.summary.query_smiles?.trim()) {
            await handleLoadStructureIntoEditor(response.summary.query_smiles, { clearMapSelection: true });
          }
        }

        if (response.status === "completed" || response.status === "failed" || response.status === "cancelled") {
          setSearchLoading(false);
          setSearchJobId(null);
          if (response.status === "failed" && response.error) {
            setSearchError(response.error);
            setSearchHighlightMap({});
            setSearchMatchCount(0);
            setSearchQueryX(null);
            setSearchQueryY(null);
            setSearchQuerySmiles(null);
          }
          return;
        }

        timeoutId = window.setTimeout(() => void poll(), 500);
      } catch (pollError) {
        if (!cancelled) {
          setSearchLoading(false);
          setSearchJobId(null);
          setSearchError(pollError instanceof Error ? pollError.message : "Failed to load job status");
        }
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timeoutId !== null) window.clearTimeout(timeoutId);
    };
  }, [searchJobId]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchHighlightMap, setSearchHighlightMap] = useState<Record<number, { score: number; rank: number }> | null>(null);
  const [searchMatchCount, setSearchMatchCount] = useState(0);
  const [searchQueryLabel, setSearchQueryLabel] = useState("");
  const [searchQuerySmiles, setSearchQuerySmiles] = useState<string | null>(null);
  const [searchQueryX, setSearchQueryX] = useState<number | null>(null);
  const [searchQueryY, setSearchQueryY] = useState<number | null>(null);
  const [recommendationHighlightMap, setRecommendationHighlightMap] = useState<Record<number, { score: number; rank: number }> | null>(null);
  const [recommendationHighlightMeta, setRecommendationHighlightMeta] = useState<{
    mode: "recommendation";
    queryLabel: string;
    matchCount: number;
    loading: boolean;
    error: string | null;
    empty: boolean;
  } | null>(null);
  const [mapOutlinePulseKey, setMapOutlinePulseKey] = useState(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  // Recommend search image state
  const [recommendImageFile, setRecommendImageFile] = useState<File | null>(null);
  const [recommendDragActive, setRecommendDragActive] = useState(false);
  const [recommendImageLoading, setRecommendImageLoading] = useState(false);
  const recommendFileInputRef = useRef<HTMLInputElement | null>(null);

  // Return-to-compound form state
  const [returnSmiles, setReturnSmiles] = useState("");
  const [returnImageFile, setReturnImageFile] = useState<File | null>(null);
  const [returnDragActive, setReturnDragActive] = useState(false);
  const [returnImageLoading, setReturnImageLoading] = useState(false);
  const returnFileInputRef = useRef<HTMLInputElement | null>(null);

  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isHighlightsCleared, setIsHighlightsCleared] = useState(false);
  const [lastSavedCompoundId, setLastSavedCompoundId] = useState<number | null>(null);
  const [isSavingToDB, setIsSavingToDB] = useState(false);
  const [mapRefreshKey, setMapRefreshKey] = useState(0);
  const [isMapExpanded, setIsMapExpanded] = useState(true);
  const mapSectionRef = useRef<HTMLDivElement | null>(null);

  const resetSaveState = () => {
    if (lastSavedCompoundId !== null) {
      setLastSavedCompoundId(null);
    }
  };

  const resolveSearchMatchesToMapNodes = (results: SearchResultItem[]) => {
    return results
      .map((item, index) => {
        const directNode = mapNodes.find((node) => node.compound_id === item.image_id);
        const mappedNode =
          directNode ??
          mapNodes.find(
            (node) =>
              node.image_url === item.image_url ||
              ((node.canonical_smiles || node.smiles || "") === (item.smiles || "") &&
                node.patent_code === item.patent_code)
          );

        if (!mappedNode) {
          return null;
        }

        return {
          compoundId: mappedNode.compound_id,
          score: Math.max(0, item.similarity - index * 0.01)
        };
      })
      .filter((item): item is { compoundId: number; score: number } => item !== null);
  };

  const activeSearchMeta =
    searchQueryLabel || searchLoading || searchError || searchHighlightMap
      ? {
          mode: "unified" as const,
          queryLabel: searchQueryLabel || "current query",
          matchCount: searchMatchCount,
          loading: searchLoading,
          error: searchError,
          empty: !searchLoading && !searchError && Boolean(searchQueryLabel) && searchMatchCount === 0,
          query_x: searchQueryX ?? undefined,
          query_y: searchQueryY ?? undefined,
          query_smiles: searchQuerySmiles ?? undefined
        }
      : null;

  const selectedMapSummaryCluster: CompoundSpaceCluster | null =
    selectedMapCluster ??
    (selectedMapCompound
      ? {
          cluster_id: selectedMapCompound.cluster_id,
          x: selectedMapCompound.x,
          y: selectedMapCompound.y,
          member_count: 1,
          patent_counts: {
            [selectedMapCompound.patent_code]: 1
          }
        }
      : null);
  const recommendationCount = similarCoreItems.length;
  const analysisSummaryLabel = decomposition
    ? `${decomposition.attachment_points.length} attachment${decomposition.attachment_points.length === 1 ? "" : "s"}`
    : "Not run";
  const recommendationSummaryLabel =
    recommendationCount > 0 ? `${recommendationCount} core${recommendationCount === 1 ? "" : "s"}` : "Idle";

  const applyRankedHighlights = (
    matches: Array<{ compoundId: number; score: number }>
  ) => {
    if (matches.length === 0) {
      setSearchHighlightMap({});
      setSearchMatchCount(0);
      return;
    }

    const nextMap: Record<number, { score: number; rank: number }> = {};
    matches.forEach((match, index) => {
      nextMap[match.compoundId] = {
        score: Math.max(0, Math.min(1, match.score)),
        rank: index + 1
      };
    });
    setSearchHighlightMap(nextMap);
    setSearchMatchCount(matches.length);
  };

  const handleToggleClearSearchHighlights = () => {
    setIsHighlightsCleared((current) => !current);
  };

  useEffect(() => {
    setSimilarCorePage(0);
  }, [similarCoreItems]);

  useEffect(() => {
    setExactColumnPages((current) => {
      const next: Record<string, number> = {};
      exactCoreRecommendations?.columns.forEach((column) => {
        const currentPage = current[column.attachment_point] ?? 0;
        next[column.attachment_point] = Math.min(currentPage, Math.max(0, column.items.length - 1));
      });
      return next;
    });
  }, [exactCoreRecommendations]);

  const handleSetExactColumnPage = (attachmentPoint: string, page: number) => {
    setExactColumnPages((current) => ({
      ...current,
      [attachmentPoint]: page
    }));
  };

  const applyRecommendationHighlights = (compoundIds: number[], queryLabel: string) => {
    setMapOutlinePulseKey((current) => current + 1);
    const uniqueIds = Array.from(new Set(compoundIds));
    const matches = uniqueIds
      .map((compoundId, index) => {
        const node = mapNodes.find((item) => item.compound_id === compoundId);
        if (!node) {
          return null;
        }
        return {
          compoundId: node.compound_id,
          score: Math.max(0.4, 1 - index * 0.08)
        };
      })
      .filter((item): item is { compoundId: number; score: number } => item !== null);

    if (matches.length === 0) {
      setRecommendationHighlightMap({});
      setRecommendationHighlightMeta({
        mode: "recommendation",
        queryLabel,
        matchCount: 0,
        loading: false,
        error: null,
        empty: true
      });
      setIsHighlightsCleared(false);
      return;
    }

    const nextMap: Record<number, { score: number; rank: number }> = {};
    matches.forEach((match, index) => {
      nextMap[match.compoundId] = {
        score: match.score,
        rank: index + 1
      };
    });
    setRecommendationHighlightMap(nextMap);
    setRecommendationHighlightMeta({
      mode: "recommendation",
      queryLabel,
      matchCount: matches.length,
      loading: false,
      error: null,
      empty: false
    });
    setIsHighlightsCleared(false);
  };

  const activeHighlightMap = recommendationHighlightMap ?? searchHighlightMap;
  const activeHighlightMeta = recommendationHighlightMeta ?? activeSearchMeta;

  const handleRecommendFileOrUpload = async (file: File) => {
    setRecommendImageFile(file);
    setRecommendImageLoading(true);
    try {
      const response = await searchByImage(file, 1);
      if (response.query_smiles?.trim()) {
        setRecommendationSmilesText(response.query_smiles.trim());
      } else {
        setToastMessage("Could not extract SMILES from image.");
        setTimeout(() => setToastMessage(null), 3000);
      }
    } catch {
      setToastMessage("Failed to process image.");
      setTimeout(() => setToastMessage(null), 3000);
    } finally {
      setRecommendImageLoading(false);
    }
  };

  const handleReturnToFullCompoundFromImage = async (file: File) => {
    setReturnImageFile(file);
    setReturnImageLoading(true);
    try {
      const response = await searchByImage(file, 1);
      if (response.query_smiles?.trim()) {
        await handleLoadStructureIntoEditor(response.query_smiles.trim(), { clearMapSelection: false });
        setReturnImageFile(null);
        setReturnSmiles("");
        setToastMessage("Compound loaded from image!");
        setTimeout(() => setToastMessage(null), 3000);
      } else {
        setToastMessage("Could not extract SMILES from image.");
        setTimeout(() => setToastMessage(null), 3000);
      }
    } catch {
      setToastMessage("Failed to process image.");
      setTimeout(() => setToastMessage(null), 3000);
    } finally {
      setReturnImageLoading(false);
    }
  };

  const handleReturnToFullCompound = async () => {
    const query = returnSmiles.trim();
    if (!query) {
      setToastMessage("Paste a SMILES string or drop an image.");
      setTimeout(() => setToastMessage(null), 3000);
      return;
    }
    await handleLoadStructureIntoEditor(query, { clearMapSelection: false });
    setReturnSmiles("");
    setReturnImageFile(null);
  };

  const handleGlobalSearch = async (fileOverride?: File) => {
    const fileToSearch = fileOverride ?? imageSearchFile;
    setIsHighlightsCleared(false);
    setSearchLoading(true);
    setSearchError(null);
    setSearchQuerySmiles(null);
    setSearchQueryX(null);
    setSearchQueryY(null);
    setSearchLogs([]);
    setSearchJobId(null);

    try {
      if (fileToSearch) {
        setSearchQueryLabel(fileToSearch.name);
        const response = await searchByImageJob(fileToSearch, searchLimit, patentFilterList);
        setSearchJobId(response.job_id);
      } else {
        const query = smilesSearchText.trim();
        if (!query) {
          throw new Error("Enter a SMILES query or upload an image.");
        }
        await runSmilesMapSearch(query, {
          queryLabel: query,
          loadIntoEditor: true
        });
        setSearchLoading(false);
      }
    } catch (globalSearchError) {
      setSearchLoading(false);
      setSearchJobId(null);
      setSearchHighlightMap({});
      setSearchMatchCount(0);
      setSearchQueryX(null);
      setSearchQueryY(null);
      setSearchQuerySmiles(null);
      setSearchError(globalSearchError instanceof Error ? globalSearchError.message : "Search failed");
    }
  };

  const runSmilesMapSearch = async (
    query: string,
    options?: {
      queryLabel?: string;
      loadIntoEditor?: boolean;
    }
  ) => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      throw new Error("Enter a SMILES query first.");
    }

    setSearchQueryLabel(options?.queryLabel ?? trimmedQuery);
    const response = await searchBySmiles(trimmedQuery, searchLimit, patentFilterList);
    if (response.query_x !== undefined) setSearchQueryX(response.query_x);
    if (response.query_y !== undefined) setSearchQueryY(response.query_y);
    setSearchQuerySmiles(response.query_smiles);
    applyRankedHighlights(resolveSearchMatchesToMapNodes(response.results));

    if (options?.loadIntoEditor) {
      await handleLoadStructureIntoEditor(trimmedQuery, { clearMapSelection: true });
    }
  };

  const handleSearchSimilarFromCompound = async () => {
    setIsHighlightsCleared(false);
    setSearchLoading(true);
    setSearchError(null);
    setSearchLogs([]);
    setSearchJobId(null);
    try {
      const currentSmiles = await resolveSmilesQuery({ preferActiveEditor: true });
      await runSmilesMapSearch(currentSmiles, {
        queryLabel: currentSmiles,
        loadIntoEditor: false
      });
      mapSectionRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    } catch (searchError) {
      setSearchHighlightMap({});
      setSearchMatchCount(0);
      setSearchQueryX(null);
      setSearchQueryY(null);
      setSearchQuerySmiles(null);
      setSearchError(searchError instanceof Error ? searchError.message : "Search failed");
    } finally {
      setSearchLoading(false);
    }
  };

  const handleFileDropOrUpload = (file: File) => {
    setImageSearchFile(file);
    setSmilesSearchText("");
    void handleGlobalSearch(file);
  };

  return (
    <>
      <CompoundExplorationLayout
        topRow={
          <WorkspacePanelShell
            title="Global Search"
            className="compound-exploration-top-panel compound-exploration-panel-compact"
            bodyClassName="compound-exploration-top-body"
            actions={
              <div className="button-group">
                <button
                  className={`secondary-button xsmall ${isAdvancedSettingsOpen ? "active" : ""}`}
                  type="button"
                  onClick={() => setIsAdvancedSettingsOpen(!isAdvancedSettingsOpen)}
                >
                  {isAdvancedSettingsOpen ? "Close" : "Advanced Settings"}
                </button>
              </div>
            }
          >
        <p className="muted small" style={{ marginBottom: "1rem" }}>
          Search by SMILES string or drag and drop/upload a compound image.
        </p>
        <form
          className="compound-exploration-searchbar"
          onSubmit={(event) => {
            event.preventDefault();
            void handleGlobalSearch();
          }}
        >
          <div className="workspace-search-field field" style={{ position: "relative", flexGrow: 1, marginBottom: 0 }}>
            <div
              className={`dropzone unified-search-dropzone ${imageSearchFile ? "has-file" : ""} ${dragActive ? "drag-active" : ""}`}
              onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
              onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
              onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
              onDrop={(e) => {
                e.preventDefault();
                setDragActive(false);
                const dropped = e.dataTransfer.files?.[0] ?? null;
                if (dropped) {
                  handleFileDropOrUpload(dropped);
                }
              }}
              style={{ 
                display: "flex", 
                alignItems: "center", 
                border: "1px solid var(--border-color)", 
                padding: "0.5rem", 
                borderRadius: "4px",
                minHeight: dragActive ? "100px" : "40px",
                transition: "min-height 0.2s ease, background 0.2s ease",
                background: dragActive ? "var(--surface-color-alt)" : "transparent"
              }}
            >
              {imageSearchFile ? (
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexGrow: 1 }}>
                  <span className="badge badge-primary">{imageSearchFile.name}</span>
                  <button type="button" className="btn-icon danger xsmall" onClick={(e) => { e.stopPropagation(); setImageSearchFile(null); }}>✕</button>
                </div>
              ) : (
                <input
                  type="text"
                  placeholder="Enter SMILES or drag image here..."
                  value={smilesSearchText}
                  onChange={(e) => setSmilesSearchText(e.target.value)}
                  style={{ border: "none", outline: "none", flexGrow: 1, background: "transparent" }}
                />
              )}
              <button
                type="button"
                className="btn-icon"
                onClick={() => fileInputRef.current?.click()}
                title="Upload Image"
                style={{ marginLeft: "auto", fontSize: "1.25rem", display: "flex", alignItems: "center" }}
              >
                <FiCamera />
              </button>
              <input
                ref={fileInputRef}
                className="visually-hidden"
                type="file"
                accept="image/*"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  if (file) {
                    handleFileDropOrUpload(file);
                  }
                }}
              />
            </div>
          </div>

          <div className="exploration-global-search-actions">
            <button
              className="primary-button small"
              type="submit"
              disabled={searchLoading}
              style={{ height: "100%" }}
            >
              {searchLoading ? "Searching..." : "Search Map"}
            </button>
          </div>
        </form>

        {(patentFilterList.length > 0 || searchLimit !== 10) && (
          <div style={{ marginTop: "0.5rem" }}>
            <span className="badge badge-neutral">
              {patentFilterList.length > 0 ? `Search within ${patentFilterList.length} patent(s) enabled` : `Search limit: ${searchLimit}`}
            </span>
          </div>
        )}

        {isAdvancedSettingsOpen && (
          <div className="advanced-settings-panel" style={{ marginTop: "1rem", padding: "1rem", border: "1px solid var(--border-color)", borderRadius: "4px", background: "var(--surface-color-alt)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <strong style={{ fontSize: "14px" }}>Advanced Settings</strong>
              <button
                type="button"
                className="secondary-button xsmall"
                onClick={() => {
                  setSearchLimit(10);
                  setPatentFilterList([]);
                  setPatentSearchText("");
                }}
              >
                Reset settings
              </button>
            </div>
            
            <div className="field" style={{ marginBottom: "1rem" }}>
              <label>Match Limit (Top N)</label>
              <input type="number" min="1" value={searchLimit} onChange={(e) => setSearchLimit(Number(e.target.value) || 10)} style={{ width: "100px" }} />
            </div>

            <div className="field" style={{ marginBottom: "0" }}>
              <label>Filter by Processed Patents</label>
              <input 
                type="text" 
                placeholder="Search patents..." 
                value={patentSearchText} 
                onChange={(e) => setPatentSearchText(e.target.value)} 
                style={{ marginBottom: "0.5rem" }}
              />
              <div style={{ maxHeight: "150px", overflowY: "auto", border: "1px solid var(--border-color)", padding: "0.5rem", borderRadius: "4px", background: "var(--surface-color)" }}>
                {availablePatentCodes
                  .filter(code => code.toLowerCase().includes(patentSearchText.toLowerCase()))
                  .slice(0, 50)
                  .map(code => (
                  <label key={code} style={{ display: "flex", gap: "0.5rem", alignItems: "center", cursor: "pointer", marginBottom: "0.25rem", textAlign: "left", justifyContent: "flex-start" }}>
                    <input 
                      type="checkbox" 
                      checked={patentFilterList.includes(code)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setPatentFilterList([...patentFilterList, code]);
                        } else {
                          setPatentFilterList(patentFilterList.filter(c => c !== code));
                        }
                      }}
                    />
                    <span style={{ fontSize: "13px" }}>{code}</span>
                  </label>
                ))}
                {availablePatentCodes.length === 0 && <span className="muted small">Loading patents...</span>}
              </div>
            </div>
          </div>
        )}

        {activeSearchMeta ? (
          <div className={`workspace-inline-state ${searchError ? "workspace-inline-state-error" : "workspace-inline-state-soft"}`} style={{ marginTop: "1rem" }}>
            <strong>
              {searchLoading
                ? "Searching compound space"
                : searchError
                  ? "Search issue"
                  : searchMatchCount === 0
                    ? "No highlighted matches"
                    : `${searchMatchCount} highlighted map match${searchMatchCount === 1 ? "" : "es"}`}
            </strong>
            <p>
              {searchLoading
                ? "Applying ranked results to the current exploration map."
                : searchError
                  ? searchError
                  : searchMatchCount === 0
                    ? "Try a broader SMILES query or another image."
                    : `Search overlay active for ${searchQueryLabel}.`}
            </p>
            {searchLogs.length > 0 && (
              <div className="search-job-logs" style={{ marginTop: "0.5rem" }}>
                {searchLogs.map((log, idx) => (
                  <div key={idx} className={`log-item log-${log.level}`} style={{ fontSize: "12px", textAlign: "left" }}>
                    <span style={{opacity: 0.7, marginRight: "4px"}}>[{new Date(log.created_at).toLocaleTimeString()}]</span>
                    {log.message}
                  </div>
                ))}
                {searchQuerySmiles && (
                  <div style={{ marginTop: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.25rem 0.5rem", background: "var(--background-color)", borderRadius: "4px", width: "fit-content" }}>
                    <span style={{ fontSize: "12px", fontFamily: "monospace" }}>
                      {searchQuerySmiles}
                    </span>
                    <button 
                      type="button" 
                      className="btn-icon xsmall" 
                      onClick={() => {
                        void navigator.clipboard.writeText(searchQuerySmiles);
                        setToastMessage("SMILES copied to clipboard!");
                        setTimeout(() => setToastMessage(null), 3000);
                      }}
                      title="Copy SMILES"
                      style={{ display: "flex", alignItems: "center", fontSize: "1rem" }}
                    >
                      <FiClipboard />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : null}
          </WorkspacePanelShell>
        }
        middleRow={
          <div ref={mapSectionRef}>
          <WorkspacePanelShell
          title="Exploration Map"
          className={`compound-exploration-panel compound-exploration-panel-map compound-exploration-panel-compact ${isMapExpanded ? "is-expanded" : "is-collapsed"}`}
          bodyClassName="compound-exploration-map-body"
          actions={
            <button
              className="secondary-button xsmall compound-exploration-map-toggle"
              type="button"
              onClick={() => setIsMapExpanded((current) => !current)}
              aria-expanded={isMapExpanded}
              aria-controls="compound-exploration-map-content"
            >
              {isMapExpanded ? "Collapse map" : "Expand map"}
            </button>
          }
        >
          <div
            id="compound-exploration-map-content"
            className={`compound-exploration-map-body-shell ${isMapExpanded ? "is-expanded" : "is-collapsed"}`}
          >
            <div className="compound-exploration-map-body-content">
              <CompoundSpaceMapPanel
                selectedCompound={selectedMapCompound}
                selectedCluster={selectedMapSummaryCluster}
                onSelectCompound={async (node) => {
                  void handleSelectCompoundFromMap(node);
                  if (node.canonical_smiles || node.smiles) {
                    setToastMessage("SMILES copied to clipboard!");
                    setTimeout(() => setToastMessage(null), 3000);
                  }
                }}
                onSelectCluster={handleSelectMapCluster}
                onNodesLoaded={setMapNodes}
                searchHighlights={isHighlightsCleared ? null : activeHighlightMap}
                searchMeta={isHighlightsCleared ? null : activeHighlightMeta}
                clearHighlightsStatus={
                  !activeHighlightMap && !searchError && !searchQueryLabel && !recommendationHighlightMap
                    ? "disabled"
                    : isHighlightsCleared
                      ? "undo"
                      : "clear"
                }
                onToggleClearHighlights={handleToggleClearSearchHighlights}
                orientation="horizontal"
                refreshKey={mapRefreshKey}
                lastSavedCompoundId={lastSavedCompoundId}
                pulseOutlineKey={mapOutlinePulseKey}
              />
            </div>
          </div>
          </WorkspacePanelShell>
          </div>
        }
        bottomLeft={
          <WorkspacePanelShell
          title="Structure Editor"
          className="compound-exploration-panel compound-exploration-panel-editor compound-exploration-panel-compact"
        >
          <div className="workspace-editor-stack">
            {/* <SmilesPreview
              label={editorMode === "decomposed" ? "Active Decomposed Structure" : "Active Structure"}
              smiles={editorSmiles || "No structure on canvas."}
              copyable
            /> */}

            <div className="compound-editor-toolbar-shell">
              <div className="compound-editor-mode-row">
                <div className="compound-editor-mode-switch" role="group" aria-label="Editor mode">
                  <button
                    className={`compound-editor-mode-option ${editorMode === "compound" ? "is-active" : ""}`}
                    type="button"
                    onClick={() => {
                      void handleSwitchEditorMode("compound");
                    }}
                  >
                    Display Full Compound
                  </button>
                  <button
                    className={`compound-editor-mode-option ${editorMode === "decomposed" ? "is-active" : ""}`}
                    type="button"
                    onClick={() => {
                      void handleSwitchEditorMode("decomposed");
                    }}
                    disabled={!decomposition}
                  >
                    Edit Decomposed Scaffold
                  </button>
                  <span className={`compound-editor-mode-pill compound-editor-mode-pill-${editorMode}`} aria-hidden="true" />
                </div>
                <p className="compound-editor-mode-subtitle">{modeSubtitle}</p>
              </div>
              <div className="compound-editor-toolbar-actions-row">
                <div className="compound-editor-actions-left">
                  {editorMode === "compound" ? (
                    <>
                      <button
                        className="primary-button small"
                        type="button"
                        onClick={() => {
                          resetSaveState();
                          void handleAnalyzeScaffold();
                        }}
                        disabled={analysisLoading}
                        title="Analyze scaffold"
                      >
                        {analysisLoading ? "Analyzing..." : "Analyze Scaffold"}
                      </button>
                      <button
                        className="secondary-button small"
                        type="button"
                        onClick={() => {
                          void handleSearchSimilarFromCompound();
                        }}
                        disabled={analysisLoading || editorLoading || searchLoading}
                      >
                        {searchLoading ? "Searching..." : "Search Similar"}
                      </button>
                    </>
                  ) : (
                    <div className="compound-editor-decomposed-forms">
                      {/* Recommend from core SMILES — styled like global search */}
                      <form
                        className="compound-editor-recommend-search"
                        onSubmit={(event) => {
                          event.preventDefault();
                          void handleRecommendFromCoreSmiles();
                        }}
                      >
                        <p className="compound-editor-recommend-search-label">
                          Recommend from core SMILES
                        </p>
                        <div className="compound-editor-unified-search-row">
                          <div
                            className={`dropzone unified-search-dropzone ${recommendImageFile ? "has-file" : ""} ${recommendDragActive ? "drag-active" : ""}`}
                            onDragEnter={(e) => { e.preventDefault(); setRecommendDragActive(true); }}
                            onDragOver={(e) => { e.preventDefault(); setRecommendDragActive(true); }}
                            onDragLeave={(e) => { e.preventDefault(); setRecommendDragActive(false); }}
                            onDrop={(e) => {
                              e.preventDefault();
                              setRecommendDragActive(false);
                              const dropped = e.dataTransfer.files?.[0] ?? null;
                              if (dropped) void handleRecommendFileOrUpload(dropped);
                            }}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              border: "1px solid var(--border-color)",
                              padding: "0.4rem 0.6rem",
                              borderRadius: "8px",
                              minHeight: recommendDragActive ? "60px" : "36px",
                              transition: "min-height 0.2s ease, background 0.2s ease",
                              background: recommendDragActive ? "var(--surface-color-alt)" : "transparent",
                              flex: "1 1 auto"
                            }}
                          >
                            {recommendImageFile ? (
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexGrow: 1 }}>
                                <span className="badge badge-primary" style={{ fontSize: "12px" }}>{recommendImageFile.name}</span>
                                <button
                                  type="button"
                                  className="btn-icon danger xsmall"
                                  onClick={(e) => { e.stopPropagation(); setRecommendImageFile(null); }}
                                >✕</button>
                              </div>
                            ) : (
                              <input
                                id="recommend-core-smiles"
                                type="text"
                                value={recommendationSmilesText}
                                onChange={(event) => setRecommendationSmilesText(event.target.value)}
                                placeholder={recommendDragActive ? "Drop image here…" : "Paste core SMILES or drop image…"}
                                disabled={analysisLoading || editorLoading || similarCoresLoading || exactCoreLoading || recommendImageLoading}
                                style={{ border: "none", outline: "none", flexGrow: 1, background: "transparent", fontSize: "0.85rem" }}
                              />
                            )}
                            <button
                              type="button"
                              className="btn-icon"
                              onClick={() => recommendFileInputRef.current?.click()}
                              title="Upload compound image"
                              style={{ marginLeft: "0.25rem", fontSize: "1.1rem", display: "flex", alignItems: "center", flexShrink: 0 }}
                            >
                              <FiCamera />
                            </button>
                            <input
                              ref={recommendFileInputRef}
                              className="visually-hidden"
                              type="file"
                              accept="image/*"
                              onChange={(event) => {
                                const file = event.target.files?.[0] ?? null;
                                if (file) void handleRecommendFileOrUpload(file);
                                event.target.value = "";
                              }}
                            />
                          </div>
                          <button
                            className="secondary-button small"
                            type="submit"
                            disabled={analysisLoading || editorLoading || similarCoresLoading || exactCoreLoading || recommendImageLoading}
                          >
                            {recommendImageLoading ? "Processing…" : "Recommend"}
                          </button>
                        </div>
                      </form>

                      {/* Load full compound — paste SMILES or drop screenshot */}
                      <form
                        className="compound-editor-recommend-search"
                        onSubmit={(event) => {
                          event.preventDefault();
                          void handleReturnToFullCompound();
                        }}
                      >
                        <p className="compound-editor-recommend-search-label">
                          Load full compound
                        </p>
                        <div className="compound-editor-unified-search-row">
                          <div
                            className={`dropzone unified-search-dropzone ${returnImageFile ? "has-file" : ""} ${returnDragActive ? "drag-active" : ""}`}
                            onDragEnter={(e) => { e.preventDefault(); setReturnDragActive(true); }}
                            onDragOver={(e) => { e.preventDefault(); setReturnDragActive(true); }}
                            onDragLeave={(e) => { e.preventDefault(); setReturnDragActive(false); }}
                            onDrop={(e) => {
                              e.preventDefault();
                              setReturnDragActive(false);
                              const dropped = e.dataTransfer.files?.[0] ?? null;
                              if (dropped) void handleReturnToFullCompoundFromImage(dropped);
                            }}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              border: "1px solid var(--border-color)",
                              padding: "0.4rem 0.6rem",
                              borderRadius: "8px",
                              minHeight: returnDragActive ? "60px" : "36px",
                              transition: "min-height 0.2s ease, background 0.2s ease",
                              background: returnDragActive ? "var(--surface-color-alt)" : "transparent",
                              flex: "1 1 auto"
                            }}
                          >
                            {returnImageFile ? (
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexGrow: 1 }}>
                                <span className="badge badge-primary" style={{ fontSize: "12px" }}>{returnImageFile.name}</span>
                                <button
                                  type="button"
                                  className="btn-icon danger xsmall"
                                  onClick={(e) => { e.stopPropagation(); setReturnImageFile(null); }}
                                >✕</button>
                              </div>
                            ) : (
                              <input
                                type="text"
                                value={returnSmiles}
                                onChange={(event) => setReturnSmiles(event.target.value)}
                                placeholder={returnDragActive ? "Drop image here…" : "Paste SMILES or drop compound screenshot…"}
                                disabled={editorLoading || returnImageLoading}
                                style={{ border: "none", outline: "none", flexGrow: 1, background: "transparent", fontSize: "0.85rem" }}
                              />
                            )}
                            <button
                              type="button"
                              className="btn-icon"
                              onClick={() => returnFileInputRef.current?.click()}
                              title="Upload compound image"
                              style={{ marginLeft: "0.25rem", fontSize: "1.1rem", display: "flex", alignItems: "center", flexShrink: 0 }}
                            >
                              <FiCamera />
                            </button>
                            <input
                              ref={returnFileInputRef}
                              className="visually-hidden"
                              type="file"
                              accept="image/*"
                              onChange={(event) => {
                                const file = event.target.files?.[0] ?? null;
                                if (file) void handleReturnToFullCompoundFromImage(file);
                                event.target.value = "";
                              }}
                            />
                          </div>
                          <button
                            className="secondary-button small"
                            type="submit"
                            disabled={editorLoading || returnImageLoading}
                          >
                            {returnImageLoading ? "Processing…" : "Load Full Compound"}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}
                </div>
                <div className="compound-editor-actions-right">
                  {editorMode === "compound"
                    ? lastSavedCompoundId !== null ? (
                        <button
                          className="primary-button small"
                          type="button"
                          onClick={async () => {
                            try {
                              await removeCompoundFromDatabase(lastSavedCompoundId);
                              setToastMessage("Undo successful.");
                              setTimeout(() => setToastMessage(null), 3000);
                              setLastSavedCompoundId(null);
                              setMapRefreshKey(prev => prev + 1);
                            } catch (err) {
                               console.error(err);
                               setToastMessage("Failed to undo.");
                               setTimeout(() => setToastMessage(null), 3000);
                            }
                          }}
                          disabled={editorLoading}
                        >
                          Undo Add
                        </button>
                      ) : (
                        <button
                          className="primary-button small"
                          type="button"
                          onClick={async () => {
                            setIsSavingToDB(true);
                            try {
                              const latestSmiles = await resolveSmilesQuery();
                              if (!latestSmiles) {
                                setToastMessage("Draw a molecule first.");
                                setTimeout(() => setToastMessage(null), 3000);
                                setIsSavingToDB(false);
                                return;
                              }

                              const res = await saveCompoundToDatabase(latestSmiles);
                              const newId = res.compound_id;
                              setLastSavedCompoundId(newId);
                              setMapRefreshKey(prev => prev + 1);
                              setToastMessage("Saved to DB!");
                              setTimeout(() => setToastMessage(null), 3000);
                            } catch (err) {
                              console.error(err);
                              setToastMessage(err instanceof Error ? err.message : "Failed to save.");
                              setTimeout(() => setToastMessage(null), 3000);
                            } finally {
                              setIsSavingToDB(false);
                            }
                          }}
                          disabled={editorLoading || isSavingToDB || analysisLoading}
                        >
                          {isSavingToDB ? "Saving to DB..." : "Save to DB"}
                        </button>
                      )
                    : null}
                  <button
                    className="btn-icon danger"
                    type="button"
                    onClick={() => {
                        resetSaveState();
                        void handleClearDraft();
                    }}
                    disabled={editorLoading}
                    aria-label="Clear Draft"
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

            <KetcherEditor ref={ketcherRef} value={editorSmiles} onSmilesChange={handleEditorSmilesChange} />

            {/* {decomposition ? (
              <div className="compound-editor-decomposition-shell" data-testid="editor-decomposition-panel">
                <div className="compound-editor-decomposition-header">
                  <div>
                    <span className="workspace-kicker">Scaffold Snapshot</span>
                    <h3>{editorMode === "decomposed" ? "Decomposed scaffold" : "Compound with saved decomposition"}</h3>
                  </div>
                  <div className="compound-editor-decomposition-badges">
                    <span className="badge badge-neutral">{analysisSummaryLabel}</span>
                    {analysisStale ? <span className="badge badge-neutral">Compound changed</span> : null}
                    {editorMode === "decomposed" && decomposedEditorState?.coreModified ? (
                      <span className="badge badge-neutral">Core edited</span>
                    ) : null}
                  </div>
                </div>

                <div className="compound-editor-decomposition-grid">
                  <AnalysisResultItem
                    label={editorMode === "decomposed" ? "Tracked Recommendation Core" : "Detected Core"}
                    smiles={editorMode === "decomposed" ? activeCoreSmiles || decomposition.labeled_core_smiles : decomposition.labeled_core_smiles}
                    onZoom={(s, l) => {
                      setZoomedSmiles({ smiles: s, label: l });
                      setImageZoom(1.6);
                    }}
                    onCopy={(s) => {
                      void navigator.clipboard.writeText(s);
                      setToastMessage("Core SMILES copied!");
                      setTimeout(() => setToastMessage(null), 2000);
                    }}
                  />

                  <div className="compound-editor-rgroup-stack">
                    <span className="workspace-kicker">{editorMode === "decomposed" ? "Floating R-groups" : "Pinned R-groups"}</span>
                    {editorMode === "decomposed" ? (
                      <div className="compound-editor-rgroup-orbit" data-testid="decomposed-rgroup-orbit">
                        {decomposition.r_groups.map((item, index) => (
                          <div
                            key={`${item.r_label}-${item.r_group}`}
                            className={`compound-editor-rgroup-float orbit-slot-${index % 4}`}
                            data-testid={`decomposed-rgroup-${item.r_label}`}
                          >
                            <div className="compound-editor-rgroup-chip">
                              <span className="workspace-kicker">{item.r_label}</span>
                              <span className="compound-editor-rgroup-chip-label">Attachment point</span>
                            </div>
                            <AnalysisResultItem
                              label={item.r_label}
                              smiles={item.r_group}
                              isSmall={true}
                              onZoom={(s, l) => {
                                setZoomedSmiles({ smiles: s, label: l });
                                setImageZoom(1.6);
                              }}
                              onCopy={(s) => {
                                void navigator.clipboard.writeText(s);
                                setToastMessage(`${item.r_label} SMILES copied!`);
                                setTimeout(() => setToastMessage(null), 2000);
                              }}
                            />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="compound-analysis-rgroup-list" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                        {decomposition.r_groups.map((item) => (
                          <AnalysisResultItem
                            key={`${item.r_label}-${item.r_group}`}
                            label={item.r_label}
                            smiles={item.r_group}
                            isSmall={true}
                            onZoom={(s, l) => {
                              setZoomedSmiles({ smiles: s, label: l });
                              setImageZoom(1.6);
                            }}
                            onCopy={(s) => {
                              void navigator.clipboard.writeText(s);
                              setToastMessage(`${item.r_label} SMILES copied!`);
                              setTimeout(() => setToastMessage(null), 2000);
                            }}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : null} */}
          </div>
          </WorkspacePanelShell>
        }
        bottomRight={
          <WorkspacePanelShell
            title="Recommendations"
            className="compound-exploration-panel compound-exploration-panel-recommendations compound-exploration-panel-compact"
          >
            <div style={{ marginBottom: "0.75rem" }}>
              <span className="badge badge-neutral">{recommendationSummaryLabel}</span>
            </div>
            <RecommendationPanel
              activeTab={recommendationTab}
              onTabChange={setRecommendationTab}
              exactCoreRecommendations={exactCoreRecommendations}
              exactCoreLoading={exactCoreLoading}
              exactCoreError={exactCoreError}
              similarCoreItems={similarCoreItems}
              similarCoresLoading={similarCoresLoading}
              similarCoresError={similarCoresError}
              similarCorePage={similarCorePage}
              onSimilarCorePageChange={setSimilarCorePage}
              exactColumnPages={exactColumnPages}
              onExactColumnPageChange={handleSetExactColumnPage}
              onZoom={(smiles, label) => {
                setZoomedSmiles({ smiles, label });
                setImageZoom(1.6);
              }}
              onAddRGroup={(smiles) => handleIntegrateRGroup(smiles)}
              onShowRGroup={(item, attachmentPoint) =>
                applyRecommendationHighlights(
                  item.compound_ids,
                  `${attachmentPoint} for ${activeRecommendationCore || activeCoreSmiles || "active core"}`
                )
              }
              onAddCore={(item) => handleIntegrateCore(item.core_smiles, item.apply_core_smiles)}
              onShowCore={(item) =>
                applyRecommendationHighlights(item.compound_ids, `Core ${item.core_smiles}`)
              }
              addDisabled={applyLoading}
            />
          </WorkspacePanelShell>
        }
      />

      {toastMessage && (
        <div style={{
          position: "fixed",
          bottom: "24px",
          right: "24px",
          backgroundColor: "var(--bg-card, #ffffff)",
          color: "var(--text-main, #000000)",
          padding: "10px 20px",
          borderRadius: "8px",
          boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
          zIndex: 9999,
          border: "1px solid var(--border-color, #444)",
          display: "flex",
          alignItems: "center",
          gap: "2px",
          fontSize: "18px",
          fontWeight: 500,
          animation: "fadeIn 0.2s ease-out"
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--primary-color)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          {toastMessage}
        </div>
      )}
      {zoomedSmiles && (
        <div className="image-zoom-modal" role="dialog" aria-modal="true" aria-label="Zoomed structure">
          <div className="image-zoom-backdrop" onClick={() => setZoomedSmiles(null)} />
          <div className="image-zoom-panel">
            <div className="image-zoom-toolbar">
              <div>
                <strong style={{ fontSize: "16px" }}>{zoomedSmiles.label}</strong>
              </div>
              <div className="browser-actions" style={{ display: "flex", gap: "8px" }}>
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
              <button className="secondary-button small" type="button" onClick={() => setZoomedSmiles(null)}>
                Close
              </button>
            </div>
            <div className="image-zoom-canvas" style={{ overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", minHeight: "400px" }}>
              <div 
                className="image-zoom-preview-svg" 
                style={{ 
                  transform: `scale(${imageZoom})`, 
                  transition: "transform 0.2s ease",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "white",
                  padding: "40px",
                  borderRadius: "12px",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.05)"
                }}
              >
                <SmilesStructurePreview smiles={zoomedSmiles.smiles} />
              </div>
            </div>
            <div style={{ padding: "1.25rem", background: "var(--surface-color-alt)", borderTop: "1px solid var(--border-color)", borderBottomLeftRadius: "22px", borderBottomRightRadius: "22px", display: "flex", alignItems: "center", gap: "10px" }}>
              <code style={{ fontSize: "12px", wordBreak: "break-all", flexGrow: 1, opacity: 0.8 }}>{zoomedSmiles.smiles}</code>
              <button 
                type="button" 
                className="btn-icon small" 
                onClick={() => {
                  void navigator.clipboard.writeText(zoomedSmiles.smiles);
                  setToastMessage("SMILES copied!");
                  setTimeout(() => setToastMessage(null), 2000);
                }}
              >
                <FiClipboard />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
