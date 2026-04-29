import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent as ReactWheelEvent } from "react";
import {
  getCompoundSpaceMap,
  type CompoundSpaceCluster,
  type CompoundSpaceNode
} from "../api/patents";
import { SmilesStructurePreview } from "./SmilesHoverPreview";

const MAP_PADDING = 32;

interface CompoundSpaceMapPanelProps {
  selectedCompound: CompoundSpaceNode | null;
  selectedCluster: CompoundSpaceCluster | null;
  onSelectCompound: (node: CompoundSpaceNode) => void | Promise<void>;
  onSelectCluster: (cluster: CompoundSpaceCluster | null) => void;
  onNodesLoaded?: (nodes: CompoundSpaceNode[]) => void;
  searchHighlights?: Record<number, { score: number; rank: number }> | null;
  searchMeta?: {
    mode: "smiles" | "image" | "keyword" | "unified" | "recommendation";
    queryLabel: string;
    matchCount: number;
    loading: boolean;
    error: string | null;
    empty: boolean;
    query_x?: number;
    query_y?: number;
    query_smiles?: string;
  } | null;
  clearHighlightsStatus?: "disabled" | "clear" | "undo";
  onToggleClearHighlights?: () => void;
  orientation?: "horizontal" | "vertical";
  refreshKey?: number;
  lastSavedCompoundId?: number | null;
  pulseOutlineKey?: number;
}

interface ViewState {
  scale: number;
  tx: number;
  ty: number;
}

export function CompoundSpaceMapPanel({
  selectedCompound,
  selectedCluster,
  onSelectCompound,
  onSelectCluster,
  onNodesLoaded,
  searchHighlights,
  searchMeta,
  clearHighlightsStatus = "disabled",
  onToggleClearHighlights,
  orientation = "horizontal",
  refreshKey = 0,
  lastSavedCompoundId = null,
  pulseOutlineKey = 0
}: CompoundSpaceMapPanelProps) {
  const [nodes, setNodes] = useState<CompoundSpaceNode[]>([]);
  const [clusters, setClusters] = useState<CompoundSpaceCluster[]>([]);
  const [hoveredNode, setHoveredNode] = useState<CompoundSpaceNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOutlinePulsing, setIsOutlinePulsing] = useState(false);
  const [view, setView] = useState<ViewState>({ scale: 1, tx: 0, ty: 0 });
  const dragStateRef = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const surfaceRef = useRef<SVGSVGElement | null>(null);

  const mapWidth = orientation === "vertical" ? 320 : 920;
  const mapHeight = orientation === "vertical" ? 720 : 260;

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await getCompoundSpaceMap();
        if (cancelled) {
          return;
        }
        setNodes(response.nodes);
        setClusters(response.clusters);
        onNodesLoaded?.(response.nodes);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load compound space map");
          setNodes([]);
          setClusters([]);
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
  }, [onNodesLoaded, refreshKey]);

  useEffect(() => {
    if (pulseOutlineKey <= 0) {
      return;
    }
    setIsOutlinePulsing(false);
    const frameId = window.requestAnimationFrame(() => {
      setIsOutlinePulsing(true);
    });
    const timeoutId = window.setTimeout(() => {
      setIsOutlinePulsing(false);
    }, 1150);
    return () => {
      window.cancelAnimationFrame(frameId);
      window.clearTimeout(timeoutId);
    };
  }, [pulseOutlineKey]);

  const plottedNodes = useMemo(
    () =>
      nodes.map((node) => ({
        ...node,
        plotX:
          orientation === "vertical"
            ? MAP_PADDING + node.y * (mapWidth - MAP_PADDING * 2)
            : MAP_PADDING + node.x * (mapWidth - MAP_PADDING * 2),
        plotY:
          orientation === "vertical"
            ? MAP_PADDING + (1 - node.x) * (mapHeight - MAP_PADDING * 2)
            : MAP_PADDING + (1 - node.y) * (mapHeight - MAP_PADDING * 2)
      })),
    [mapHeight, mapWidth, nodes, orientation]
  );

  const plottedClusters = useMemo(
    () =>
      clusters.map((cluster) => ({
        ...cluster,
        plotX:
          orientation === "vertical"
            ? MAP_PADDING + cluster.y * (mapWidth - MAP_PADDING * 2)
            : MAP_PADDING + cluster.x * (mapWidth - MAP_PADDING * 2),
        plotY:
          orientation === "vertical"
            ? MAP_PADDING + (1 - cluster.x) * (mapHeight - MAP_PADDING * 2)
            : MAP_PADDING + (1 - cluster.y) * (mapHeight - MAP_PADDING * 2),
        radius: Math.max(22, Math.min(54, 18 + cluster.member_count * 1.4))
      })),
    [clusters, mapHeight, mapWidth, orientation]
  );

  const handleWheel = (event: ReactWheelEvent<SVGSVGElement>) => {
    event.preventDefault();
    const surface = surfaceRef.current;
    if (!surface) {
      return;
    }

    const rect = surface.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const nextScale = Math.min(6, Math.max(0.8, view.scale * Math.exp(-event.deltaY * 0.0012)));
    const worldX = (px - view.tx) / view.scale;
    const worldY = (py - view.ty) / view.scale;

    setView({
      scale: nextScale,
      tx: px - worldX * nextScale,
      ty: py - worldY * nextScale
    });
  };

  const handlePointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    dragStateRef.current = {
      x: event.clientX,
      y: event.clientY,
      tx: view.tx,
      ty: view.ty
    };
    if ("setPointerCapture" in event.currentTarget) {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  };

  const handlePointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (dragStateRef.current == null) {
      return;
    }
    const deltaX = event.clientX - dragStateRef.current.x;
    const deltaY = event.clientY - dragStateRef.current.y;
    setView({
      scale: view.scale,
      tx: dragStateRef.current.tx + deltaX,
      ty: dragStateRef.current.ty + deltaY
    });
  };

  const handlePointerEnd = (event: ReactPointerEvent<SVGSVGElement>) => {
    dragStateRef.current = null;
    if (
      "hasPointerCapture" in event.currentTarget &&
      "releasePointerCapture" in event.currentTarget &&
      event.currentTarget.hasPointerCapture(event.pointerId)
    ) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const handleResetView = () => {
    setView({ scale: 1, tx: 0, ty: 0 });
  };

  const selectedPatentSummary = useMemo(() => {
    if (!selectedCluster) {
      return [];
    }
    return Object.entries(selectedCluster.patent_counts);
  }, [selectedCluster]);

  const hoveredNodePosition = useMemo(() => {
    if (!hoveredNode) {
      return null;
    }
    
    if (hoveredNode.compound_id === -1) {
      const plotX = orientation === "vertical"
        ? MAP_PADDING + hoveredNode.y * (mapWidth - MAP_PADDING * 2)
        : MAP_PADDING + hoveredNode.x * (mapWidth - MAP_PADDING * 2);
      const plotY = orientation === "vertical"
        ? MAP_PADDING + (1 - hoveredNode.x) * (mapHeight - MAP_PADDING * 2)
        : MAP_PADDING + (1 - hoveredNode.y) * (mapHeight - MAP_PADDING * 2);
        
      return {
        left: plotX * view.scale + view.tx,
        top: plotY * view.scale + view.ty
      };
    }

    const plottedNode = plottedNodes.find((node) => node.compound_id === hoveredNode.compound_id);
    if (!plottedNode) {
      return null;
    }
    return {
      left: plottedNode.plotX * view.scale + view.tx,
      top: plottedNode.plotY * view.scale + view.ty
    };
  }, [hoveredNode, plottedNodes, view.scale, view.tx, view.ty, mapWidth, mapHeight, orientation]);

  const highlightedNodeIds = useMemo(
    () => new Set(Object.keys(searchHighlights ?? {}).map((item) => Number(item))),
    [searchHighlights]
  );

  const plottedNodesOrdered = useMemo(() => {
    return [...plottedNodes].sort((left, right) => {
      const leftHighlight = searchHighlights?.[left.compound_id];
      const rightHighlight = searchHighlights?.[right.compound_id];
      const leftRank = leftHighlight?.rank ?? Number.MAX_SAFE_INTEGER;
      const rightRank = rightHighlight?.rank ?? Number.MAX_SAFE_INTEGER;
      if (leftRank !== rightRank) {
        return rightRank - leftRank;
      }
      return left.compound_id - right.compound_id;
    });
  }, [plottedNodes, searchHighlights]);

  return (
    <div
      className={`compound-space-map-panel compound-space-map-panel-${orientation} ${searchMeta ? "has-search-overlay" : ""}`}
      data-pulse-outline={pulseOutlineKey > 0 ? pulseOutlineKey : undefined}
    >
      <div className="compound-space-map-toolbar" style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
        <button className="secondary-button xsmall" type="button" onClick={handleResetView}>
          Recenter
        </button>
        <button 
          className="secondary-button xsmall" 
          type="button" 
          disabled={clearHighlightsStatus === "disabled"}
          title={clearHighlightsStatus === "disabled" ? "Search a compound first!" : ""}
          onClick={onToggleClearHighlights}
        >
          {clearHighlightsStatus === "undo" ? "Undo Clear" : "Clear Highlights"}
        </button>
      </div>

      {searchMeta ? (
        <div className="compound-space-search-status">
          <div>
            <span className="workspace-kicker">
              {searchMeta.mode === "recommendation" ? "Map Highlight" : "Map Search"}
            </span>
            <p className="muted">
              {searchMeta.loading
                ? searchMeta.mode === "recommendation"
                  ? `Highlighting compounds for ${searchMeta.queryLabel}...`
                  : `Searching ${searchMeta.mode} matches for ${searchMeta.queryLabel}...`
                : searchMeta.error
                  ? searchMeta.error
                  : searchMeta.empty
                    ? `No map matches found for ${searchMeta.queryLabel}.`
                    : `${searchMeta.matchCount} map match${searchMeta.matchCount === 1 ? "" : "es"} highlighted.`}
            </p>
          </div>
        </div>
      ) : null}

      {loading ? (
        <div className="workspace-inline-state workspace-inline-state-soft">
          <strong>Computing compound space...</strong>
          <p>Projecting embeddings into a navigable 2D view.</p>
        </div>
      ) : error ? (
        <div className="workspace-inline-state workspace-inline-state-error" role="alert">
          <strong>Could not load compound space</strong>
          <p>{error}</p>
        </div>
      ) : nodes.length === 0 ? (
        <div className="workspace-inline-state workspace-inline-state-soft">
          <strong>No embedded compounds available yet</strong>
          <p>Process compounds with ChemBERTa embeddings before using the map.</p>
        </div>
      ) : (
        <>
          <div className={`compound-space-map-surface ${isOutlinePulsing ? "is-pulsing-outline" : ""}`}>
            <svg
              ref={surfaceRef}
              className="compound-space-map-svg"
              viewBox={`0 0 ${mapWidth} ${mapHeight}`}
              onWheel={handleWheel}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerEnd}
              onPointerLeave={handlePointerEnd}
            >
              <rect x="0" y="0" width={mapWidth} height={mapHeight} className="compound-space-map-background" />
              <g transform={`translate(${view.tx} ${view.ty}) scale(${view.scale})`}>
                <g className="compound-space-map-grid">
                  {Array.from({ length: 5 }).map((_, index) => {
                    const x = MAP_PADDING + (index * (mapWidth - MAP_PADDING * 2)) / 4;
                    return <line key={`vx-${index}`} x1={x} y1={MAP_PADDING} x2={x} y2={mapHeight - MAP_PADDING} />;
                  })}
                  {Array.from({ length: 4 }).map((_, index) => {
                    const y = MAP_PADDING + (index * (mapHeight - MAP_PADDING * 2)) / 3;
                    return <line key={`hy-${index}`} x1={MAP_PADDING} y1={y} x2={mapWidth - MAP_PADDING} y2={y} />;
                  })}
                </g>

                {plottedClusters.map((cluster) => (
                  <g
                    key={cluster.cluster_id}
                    className={`compound-space-map-cluster ${
                      selectedCluster?.cluster_id === cluster.cluster_id ? "active" : ""
                    }`}
                    data-testid={`compound-space-cluster-${cluster.cluster_id}`}
                  >
                    <circle cx={cluster.plotX} cy={cluster.plotY} r={cluster.radius} />
                    <text x={cluster.plotX} y={cluster.plotY + 4}>
                      {cluster.member_count}
                    </text>
                  </g>
                ))}

                {plottedNodesOrdered.map((node) => (
                  <g
                    key={node.compound_id}
                    className={`compound-space-map-node ${
                      selectedCompound?.compound_id === node.compound_id ? "active" : ""
                    } ${searchHighlights ? (highlightedNodeIds.has(node.compound_id) ? "matched" : "dimmed") : ""}`}
                    onPointerDown={(event) => {
                      event.stopPropagation();
                    }}
                    onMouseEnter={() => {
                      setHoveredNode(node);
                    }}
                    onMouseLeave={() => {
                      setHoveredNode((current) => (current?.compound_id === node.compound_id ? null : current));
                    }}
                    onClick={(event) => {
                      event.stopPropagation();
                      void onSelectCompound(node);
                    }}
                    data-testid={`compound-space-node-${node.compound_id}`}
                  >
                    <circle
                      className="compound-space-map-node-hit"
                      cx={node.plotX}
                      cy={node.plotY}
                      r={searchHighlights?.[node.compound_id] ? 12 : 10}
                    />
                    <circle
                      cx={node.plotX}
                      cy={node.plotY}
                      r={
                        node.compound_id === lastSavedCompoundId
                          ? 8.0 // 2x base radius (4 * 2)
                          : selectedCompound?.compound_id === node.compound_id
                            ? 5.8
                            : searchHighlights?.[node.compound_id]
                              ? 4.6 + Math.max(0, searchHighlights[node.compound_id].score) * 3.2
                              : 4
                      }
                      style={{
                        fill: node.compound_id === lastSavedCompoundId ? "#3b82f6" : undefined,
                        opacity: searchHighlights
                          ? highlightedNodeIds.has(node.compound_id)
                            ? 0.82 + Math.max(0, searchHighlights?.[node.compound_id]?.score ?? 0) * 0.18
                            : 0.38
                          : 1
                      }}
                    />
                  </g>
                ))}
              </g>
            </svg>

            {searchMeta?.query_x !== undefined && searchMeta?.query_y !== undefined && searchMeta?.query_smiles && !(
              nodes.some(node => node.canonical_smiles === searchMeta.query_smiles)
            ) ? (
              <svg 
                className="compound-space-map-svg"
                viewBox={`0 0 ${mapWidth} ${mapHeight}`}
                style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}
              >
                <g transform={`translate(${view.tx} ${view.ty}) scale(${view.scale})`}>
                  <circle
                    cx={MAP_PADDING + searchMeta.query_x * (mapWidth - MAP_PADDING * 2)}
                    cy={MAP_PADDING + searchMeta.query_y * (mapHeight - MAP_PADDING * 2)}
                    r={8.0}
                    fill="#3b82f6"
                    stroke="#1d4ed8"
                    strokeWidth={1.5}
                    style={{ pointerEvents: 'auto', cursor: 'help' }}
                    onPointerEnter={(e) => {
                      const rect = surfaceRef.current?.getBoundingClientRect();
                      if (rect) {
                        setHoveredNode({
                          compound_id: -1,
                          patent_id: -1,
                          patent_code: "",
                          patent_source_url: "",
                          image_url: "",
                          smiles: searchMeta.query_smiles || "",
                          canonical_smiles: searchMeta.query_smiles || "",
                          has_embedding: false,
                          x: searchMeta.query_x!,
                          y: searchMeta.query_y!,
                          cluster_id: -1,
                        });
                      }
                    }}
                    onPointerLeave={() => {
                        setHoveredNode(null);
                    }}
                  />
                </g>
              </svg>
            ) : null}

            {hoveredNode && hoveredNodePosition ? (
              <div
                className="compound-space-map-tooltip"
                data-testid="compound-space-node-tooltip"
                style={{
                  left: `${Math.max(16, Math.min(mapWidth - 250, hoveredNodePosition.left + 14))}px`,
                  top: `${Math.max(12, Math.min(mapHeight - 20, hoveredNodePosition.top - 12))}px`
                }}
              >
                {hoveredNode.compound_id === -1 ? (
                  <>
                    <span className="workspace-kicker">Query Structure (Not in DB)</span>
                    <SmilesStructurePreview
                      smiles={hoveredNode.canonical_smiles || hoveredNode.smiles || ""}
                      loadingText="Rendering query..."
                      errorText="Unable to render structure preview"
                      testId="compound-space-node-structure-preview"
                    />
                  </>
                ) : (
                  <>
                    <span className="workspace-kicker">Compound Preview</span>
                    <SmilesStructurePreview
                      smiles={hoveredNode.canonical_smiles || hoveredNode.smiles || ""}
                      loadingText="Rendering structure..."
                      errorText="Unable to render structure preview"
                      testId="compound-space-node-structure-preview"
                    />
                    <div className="compound-space-map-tooltip-meta">
                      <span className="badge badge-neutral">{hoveredNode.patent_code}</span>
                      <span className="badge badge-neutral">Page {hoveredNode.page_number ?? "n/a"}</span>
                    </div>
                  </>
                )}
              </div>
            ) : null}
          </div>


        </>
      )}
    </div>
  );
}
