import { useEffect, useMemo, useRef, useState } from "react";
import {
  applyModification,
  decomposeStructure,
  recommendExactCoreRGroups,
  recommendRGroups,
  recommendSimilarCores,
  type ApplyModificationResponse,
  type CompoundSpaceCluster,
  type CompoundSpaceNode,
  type DecomposeStructureResponse,
  type ExactCoreRGroupRecommendationResponse,
  type RGroupRecommendationItem,
  type SimilarCoreRecommendationItem
} from "../api/patents";
import type { KetcherEditorHandle } from "../components/KetcherEditor";

const DEFAULT_ATTACHMENT_POINT_OPTIONS = ["R1", "R2", "R3", "R4", "R5", "R6"];

let globalKetcherEditorString = "";
let globalCompoundSmilesCache = "";
let globalDecomposedSmilesCache = "";

export type EditorStructureMode = "compound" | "decomposed";

export interface DecomposedEditorState {
  originalCompoundSmiles: string;
  currentCoreSmiles: string;
  lastAnalyzedCoreSmiles: string;
  attachmentPoints: string[];
  rGroups: DecomposeStructureResponse["r_groups"];
  coreModified: boolean;
}

function splitCxSmiles(smiles: string) {
  const trimmedSmiles = smiles.trim();
  const pipeIndex = trimmedSmiles.indexOf("|");
  if (pipeIndex === -1) {
    return {
      main: trimmedSmiles,
      cxSuffix: ""
    };
  }

  return {
    main: trimmedSmiles.slice(0, pipeIndex).trim(),
    cxSuffix: trimmedSmiles.slice(pipeIndex).trim()
  };
}

function joinCxSmiles(main: string, cxSuffix = "") {
  const trimmedMain = main.trim();
  const trimmedCxSuffix = cxSuffix.trim();
  if (!trimmedCxSuffix) {
    return trimmedMain;
  }
  if (!trimmedMain) {
    return trimmedCxSuffix;
  }
  return `${trimmedMain} ${trimmedCxSuffix}`.trim();
}

function buildDecomposedCanvasSmiles(
  coreSmiles: string,
  rGroups: DecomposeStructureResponse["r_groups"]
) {
  const { main: coreMain, cxSuffix } = splitCxSmiles(coreSmiles);
  const detachedRGroupFragments = rGroups
    .map((item) => splitCxSmiles(item.r_group).main)
    .filter((item) => item.length > 0);

  return joinCxSmiles([coreMain, ...detachedRGroupFragments].filter((item) => item.length > 0).join("."), cxSuffix);
}

function extractCoreSmilesFromDecomposedCanvas(
  decomposedCanvasSmiles: string,
  fallbackCoreSmiles = ""
) {
  const { main, cxSuffix } = splitCxSmiles(decomposedCanvasSmiles);
  const coreMain = main.split(".")[0]?.trim() ?? "";
  const fallbackCxSuffix = splitCxSmiles(fallbackCoreSmiles).cxSuffix;
  return joinCxSmiles(coreMain, cxSuffix || fallbackCxSuffix);
}

export function useCompoundWorkspaceController() {
  const ketcherRef = useRef<KetcherEditorHandle | null>(null);
  const selectedCoreRef = useRef("");
  const selectedApplyCoreRef = useRef("");
  const skipNextEditorChangeRef = useRef(false);
  const [smilesText, setSmilesText] = useState("");
  const [editorSmiles, setEditorSmiles] = useState("");
  const [compoundSmiles, setCompoundSmiles] = useState("");
  const [editorLoading, setEditorLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [applyLoading, setApplyLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [similarCoreItems, setSimilarCoreItems] = useState<SimilarCoreRecommendationItem[]>([]);
  const [rGroupItems, setRGroupItems] = useState<RGroupRecommendationItem[]>([]);
  const [exactCoreRecommendations, setExactCoreRecommendations] = useState<ExactCoreRGroupRecommendationResponse | null>(null);
  const [activeRecommendationCore, setActiveRecommendationCore] = useState("");
  const [selectedCore, setSelectedCore] = useState("");
  const [selectedApplyCoreSmiles, setSelectedApplyCoreSmiles] = useState("");
  const [selectedAttachmentPoint, setSelectedAttachmentPoint] = useState(DEFAULT_ATTACHMENT_POINT_OPTIONS[0]);
  const [selectedMapCompound, setSelectedMapCompound] = useState<CompoundSpaceNode | null>(null);
  const [selectedMapCluster, setSelectedMapCluster] = useState<CompoundSpaceCluster | null>(null);
  const [similarCoresLoading, setSimilarCoresLoading] = useState(false);
  const [rGroupsLoading, setRGroupsLoading] = useState(false);
  const [similarCoresError, setSimilarCoresError] = useState<string | null>(null);
  const [rGroupsError, setRGroupsError] = useState<string | null>(null);
  const [exactCoreLoading, setExactCoreLoading] = useState(false);
  const [exactCoreError, setExactCoreError] = useState<string | null>(null);
  const [editorMode, setEditorMode] = useState<EditorStructureMode>("compound");
  const [decomposition, setDecomposition] = useState<DecomposeStructureResponse | null>(null);
  const [decomposedEditorState, setDecomposedEditorState] = useState<DecomposedEditorState | null>(null);
  const [recommendationSmilesText, setRecommendationSmilesText] = useState("");

  const attachmentPointOptions = useMemo(() => {
    if (decomposedEditorState?.attachmentPoints.length) {
      return decomposedEditorState.attachmentPoints;
    }
    if (decomposition?.attachment_points.length) {
      return decomposition.attachment_points;
    }
    return DEFAULT_ATTACHMENT_POINT_OPTIONS;
  }, [decomposition, decomposedEditorState]);

  const analysisStale = Boolean(
    decomposition?.canonical_smiles &&
      compoundSmiles.trim() &&
      decomposition.canonical_smiles !== compoundSmiles.trim()
  );

  const activeCoreSmiles =
    editorMode === "decomposed"
      ? decomposedEditorState?.currentCoreSmiles.trim() ?? decomposition?.labeled_core_smiles ?? ""
      : decomposition?.labeled_core_smiles ?? "";

  const activeDecomposedCanvasSmiles =
    decomposedEditorState ? buildDecomposedCanvasSmiles(decomposedEditorState.currentCoreSmiles, decomposedEditorState.rGroups) : "";

  const modeSubtitle =
    editorMode === "decomposed"
      ? decomposedEditorState
        ? `Editable core with detached R-groups on canvas. ${decomposedEditorState.rGroups.length} R-group${decomposedEditorState.rGroups.length === 1 ? "" : "s"} remain pinned from the last scaffold analysis.`
        : "Run scaffold analysis to generate a decomposed scaffold view."
      : "Full compound on canvas. Scaffold analysis keeps a decomposed core ready without replacing the original molecule.";

  useEffect(() => {
    if (!attachmentPointOptions.includes(selectedAttachmentPoint)) {
      setSelectedAttachmentPoint(attachmentPointOptions[0] ?? DEFAULT_ATTACHMENT_POINT_OPTIONS[0]);
    }
  }, [attachmentPointOptions, selectedAttachmentPoint]);

  useEffect(() => {
    selectedCoreRef.current = selectedCore;
  }, [selectedCore]);

  useEffect(() => {
    selectedApplyCoreRef.current = selectedApplyCoreSmiles;
  }, [selectedApplyCoreSmiles]);

  const loadRecommendations = async (
    processedSmiles: string,
    attachmentPoints: string[] = decomposition?.attachment_points ?? []
  ) => {
    const trimmedSmiles = processedSmiles.trim();
    if (!trimmedSmiles) {
      setSimilarCoreItems([]);
      setRGroupItems([]);
      setExactCoreRecommendations(null);
      setActiveRecommendationCore("");
      setSelectedCore("");
      setSelectedApplyCoreSmiles("");
      setSimilarCoresError(null);
      setRGroupsError(null);
      setExactCoreError(null);
      return;
    }

    let cancelled = false;
    try {
      setSimilarCoresLoading(true);
      setExactCoreLoading(true);
      setSimilarCoresError(null);
      setExactCoreError(null);
      setRGroupItems([]);
      const [similarResponse, exactResponse] = await Promise.all([
        recommendSimilarCores(trimmedSmiles, 12),
        recommendExactCoreRGroups(trimmedSmiles, attachmentPoints, 12)
      ]);
      if (cancelled) {
        return;
      }
      setSimilarCoreItems(similarResponse);
      setExactCoreRecommendations(exactResponse);
      setActiveRecommendationCore(exactResponse.query_core_smiles);
      const nextSelectedCore =
        selectedCoreRef.current && similarResponse.some((item) => item.core_smiles === selectedCoreRef.current)
          ? selectedCoreRef.current
          : similarResponse[0]?.core_smiles ?? exactResponse.query_core_smiles;
      const matched = similarResponse.find((item) => item.core_smiles === nextSelectedCore);

      setSelectedCore(nextSelectedCore);
      setSelectedApplyCoreSmiles(
        selectedApplyCoreRef.current &&
          similarResponse.some(
            (item) =>
              item.apply_core_smiles === selectedApplyCoreRef.current || item.core_smiles === selectedApplyCoreRef.current
          )
          ? selectedApplyCoreRef.current
          : matched?.apply_core_smiles ?? similarResponse[0]?.apply_core_smiles ?? exactResponse.query_core_smiles
      );
    } catch (recommendationError) {
      if (!cancelled) {
        const fallbackSmiles = decomposition?.reduced_core ?? activeCoreSmiles ?? trimmedSmiles;
        const fallbackApplySmiles = decomposition?.labeled_core_smiles ?? activeCoreSmiles ?? trimmedSmiles;
        setSimilarCoreItems([]);
        setExactCoreRecommendations(null);
        setActiveRecommendationCore(fallbackSmiles);
        setSelectedCore(fallbackSmiles);
        setSelectedApplyCoreSmiles(fallbackApplySmiles);
        setSimilarCoresError(
          recommendationError instanceof Error ? recommendationError.message : "Failed to load similar cores"
        );
        setExactCoreError(
          recommendationError instanceof Error ? recommendationError.message : "Failed to load exact-core recommendations"
        );
      }
    } finally {
      if (!cancelled) {
        setSimilarCoresLoading(false);
        setExactCoreLoading(false);
      }
    }
  };

  const clearDecomposition = () => {
    setDecomposition(null);
    setDecomposedEditorState(null);
    setEditorMode("compound");
  };

  const resetRecommendationSelections = () => {
    setSelectedCore("");
    setSelectedApplyCoreSmiles("");
    setSelectedAttachmentPoint(DEFAULT_ATTACHMENT_POINT_OPTIONS[0]);
  };

  const syncStructureState = (nextSmiles: string) => {
    globalKetcherEditorString = nextSmiles;
    setEditorSmiles(nextSmiles);
    setCompoundSmiles(nextSmiles);
    setSmilesText(nextSmiles);
  };

  const syncEditorOnlyState = (nextSmiles: string) => {
    globalKetcherEditorString = nextSmiles;
    setEditorSmiles(nextSmiles);
    setSmilesText(nextSmiles);
  };

  const handleEditorSmilesChange = (nextSmiles: string) => {
    const trimmedSmiles = nextSmiles.trim();
    globalKetcherEditorString = trimmedSmiles;
    setEditorSmiles(trimmedSmiles);
    setSmilesText(trimmedSmiles);
    if (skipNextEditorChangeRef.current) {
      skipNextEditorChangeRef.current = false;
      return;
    }
    if (editorMode === "decomposed") {
      const nextCoreSmiles = extractCoreSmilesFromDecomposedCanvas(
        trimmedSmiles,
        decomposedEditorState?.currentCoreSmiles ?? decomposition?.labeled_core_smiles ?? ""
      );
      setDecomposedEditorState((current) =>
        current
          ? {
              ...current,
              currentCoreSmiles: nextCoreSmiles,
              coreModified: nextCoreSmiles !== current.lastAnalyzedCoreSmiles
            }
          : current
      );
      return;
    }
    setCompoundSmiles(trimmedSmiles);
  };

  const refreshRecommendations = async (querySmiles: string, attachmentPoints: string[] = attachmentPointOptions) => {
    await loadRecommendations(querySmiles, attachmentPoints);
  };

  const setCanvasSmiles = async (nextSmiles: string) => {
    skipNextEditorChangeRef.current = true;
    try {
      return (await ketcherRef.current?.setSmiles(nextSmiles)) ?? nextSmiles;
    } finally {
      window.setTimeout(() => {
        skipNextEditorChangeRef.current = false;
      }, 0);
    }
  };

  const handleLoadStructureIntoEditor = async (
    nextSmiles: string,
    options?: {
      clearMapSelection?: boolean;
    }
  ) => {
    const trimmedSmiles = nextSmiles.trim();
    if (!trimmedSmiles) {
      setError("No structure is available to load.");
      return "";
    }

    setEditorLoading(true);
    setError(null);
    try {
      const combinedSmiles = trimmedSmiles;
      resetRecommendationSelections();
      clearDecomposition();
      setSimilarCoreItems([]);
      setRGroupItems([]);
      setExactCoreRecommendations(null);
      setActiveRecommendationCore("");
      setSimilarCoresError(null);
      setRGroupsError(null);
      setExactCoreError(null);
      if (options?.clearMapSelection) {
        setSelectedMapCompound(null);
        setSelectedMapCluster(null);
      }
      const appliedSmiles = ((await setCanvasSmiles(combinedSmiles)) ?? combinedSmiles).trim() || combinedSmiles;
      setEditorMode("compound");
      globalCompoundSmilesCache = appliedSmiles;
      globalDecomposedSmilesCache = "";
      syncStructureState(appliedSmiles);
      return appliedSmiles;
    } catch (editorError) {
      setError(editorError instanceof Error ? editorError.message : "Failed to load structure into Ketcher");
      return "";
    } finally {
      setEditorLoading(false);
    }
  };

  const handleLoadSmilesIntoEditor = async () => {
    const nextSmiles = smilesText.trim();
    if (!nextSmiles) {
      setError("Enter a SMILES string first.");
      return;
    }
    await handleLoadStructureIntoEditor(nextSmiles);
  };

  const handleUseEditorSmiles = async () => {
    setEditorLoading(true);
    setError(null);
    try {
      const nextSmiles = (await ketcherRef.current?.getSmiles())?.trim() ?? "";
      if (!nextSmiles) {
        throw new Error("Draw a molecule in Ketcher first.");
      }
      resetRecommendationSelections();
      setSimilarCoreItems([]);
      setRGroupItems([]);
      setExactCoreRecommendations(null);
      setActiveRecommendationCore("");
      setSimilarCoresError(null);
      setRGroupsError(null);
      setExactCoreError(null);
      setRecommendationSmilesText("");
      setEditorMode("compound");
      syncStructureState(nextSmiles);
      clearDecomposition();
    } catch (editorError) {
      setError(editorError instanceof Error ? editorError.message : "Failed to export SMILES from Ketcher");
    } finally {
      setEditorLoading(false);
    }
  };

  const resolveSmilesQuery = async (options?: { preferActiveEditor?: boolean }) => {
    const canvasSmiles = (await ketcherRef.current?.getSmiles())?.trim() ?? editorSmiles.trim();
    if (options?.preferActiveEditor) {
      if (canvasSmiles) {
        if (editorMode === "compound") {
          syncStructureState(canvasSmiles);
        }
        return canvasSmiles;
      }
    }

    if (editorMode === "decomposed") {
      const preservedCompoundSmiles = compoundSmiles.trim() || decomposedEditorState?.originalCompoundSmiles.trim() || "";
      if (preservedCompoundSmiles) {
        return preservedCompoundSmiles;
      }
    }

    if (canvasSmiles) {
      syncStructureState(canvasSmiles);
      return canvasSmiles;
    }

    const fallbackSmiles = smilesText.trim();
    if (fallbackSmiles) {
      return fallbackSmiles;
    }

    throw new Error("Draw a molecule in Ketcher or enter a SMILES string first.");
  };

  const handleClearDraft = async () => {
    setEditorLoading(true);
    setError(null);
    try {
      await ketcherRef.current?.clear();
      globalKetcherEditorString = "";
      globalCompoundSmilesCache = "";
      globalDecomposedSmilesCache = "";
      setSmilesText("");
      setEditorSmiles("");
      setCompoundSmiles("");
      resetRecommendationSelections();
      setSimilarCoreItems([]);
      setRGroupItems([]);
      setExactCoreRecommendations(null);
      setActiveRecommendationCore("");
      setSimilarCoresError(null);
      setRGroupsError(null);
      setExactCoreError(null);
      setRecommendationSmilesText("");
      setSelectedMapCompound(null);
      setSelectedMapCluster(null);
      clearDecomposition();
    } catch (editorError) {
      setError(editorError instanceof Error ? editorError.message : "Failed to clear the editor draft");
    } finally {
      setEditorLoading(false);
    }
  };

  const handleAnalyzeScaffold = async () => {
    setAnalysisLoading(true);
    setError(null);
    try {
      const currentSmiles = await resolveSmilesQuery();
      const response = await decomposeStructure(currentSmiles);
      const nextDecomposedCanvasSmiles = buildDecomposedCanvasSmiles(response.labeled_core_smiles, response.r_groups);
      setDecomposition(response);
      setDecomposedEditorState({
        originalCompoundSmiles: currentSmiles,
        currentCoreSmiles: response.labeled_core_smiles,
        lastAnalyzedCoreSmiles: response.labeled_core_smiles,
        attachmentPoints: response.attachment_points,
        rGroups: response.r_groups,
        coreModified: false
      });
      setSelectedAttachmentPoint(response.attachment_points[0] ?? DEFAULT_ATTACHMENT_POINT_OPTIONS[0]);
      setSelectedApplyCoreSmiles(response.labeled_core_smiles);
      setSelectedCore((current) => current || response.reduced_core);
      setRecommendationSmilesText(response.labeled_core_smiles);
      const appliedSmiles =
        ((await setCanvasSmiles(nextDecomposedCanvasSmiles)) ?? nextDecomposedCanvasSmiles).trim() ||
        nextDecomposedCanvasSmiles;
      setEditorMode("decomposed");
      globalKetcherEditorString = appliedSmiles;
      globalDecomposedSmilesCache = appliedSmiles;
      globalCompoundSmilesCache = currentSmiles;
      setEditorSmiles(appliedSmiles);
      setSmilesText(appliedSmiles);
      setCompoundSmiles(currentSmiles);
      await refreshRecommendations(response.labeled_core_smiles, response.attachment_points);
      return currentSmiles;
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : "Failed to analyze scaffold");
      return "";
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleSelectMapCluster = (cluster: CompoundSpaceCluster | null) => {
    setSelectedMapCluster(cluster);
  };

  const handleSelectCompoundFromMap = async (node: CompoundSpaceNode) => {
    setSelectedMapCompound(node);
    const nextSmiles = (node.canonical_smiles || node.smiles || "").trim();
    if (!nextSmiles) {
      setEditorSmiles("");
      setCompoundSmiles("");
      setSmilesText("");
      return;
    }
    await handleLoadStructureIntoEditor(nextSmiles);
    try {
      await navigator.clipboard.writeText(nextSmiles);
    } catch {
      // Ignore if clipboard fails
    }
    await handleAnalyzeScaffold();
  };

  const applyCanvasUpdate = async (
    response: ApplyModificationResponse,
    nextSelectedCore?: string,
    nextSelectedApplyCore?: string
  ) => {
    const appliedSmiles = ((await setCanvasSmiles(response.smiles)) ?? response.smiles).trim() || response.smiles;
    syncStructureState(appliedSmiles);
    clearDecomposition();
    setSelectedCore(nextSelectedCore ?? response.core_smiles);
    setSelectedApplyCoreSmiles(nextSelectedApplyCore ?? response.core_smiles);
  };

  const handleSwitchEditorMode = async (nextMode: EditorStructureMode) => {
    if (nextMode === editorMode) {
      return;
    }
    if (nextMode === "decomposed" && !decomposedEditorState) {
      return;
    }

    setEditorLoading(true);
    setError(null);
    try {
      // Capture live canvas state before switching so edits are never lost
      const liveCanvas = (await ketcherRef.current?.getSmiles())?.trim() ?? "";
      if (editorMode === "compound" && liveCanvas) {
        globalCompoundSmilesCache = liveCanvas;
        setCompoundSmiles(liveCanvas);
      } else if (editorMode === "decomposed" && liveCanvas) {
        globalDecomposedSmilesCache = liveCanvas;
        const extractedCore = extractCoreSmilesFromDecomposedCanvas(
          liveCanvas,
          decomposedEditorState?.currentCoreSmiles ?? decomposition?.labeled_core_smiles ?? ""
        );
        setDecomposedEditorState((current) =>
          current
            ? {
                ...current,
                currentCoreSmiles: extractedCore,
                coreModified: extractedCore !== current.lastAnalyzedCoreSmiles
              }
            : current
        );
      }

      const nextSmiles =
        nextMode === "decomposed"
          ? globalDecomposedSmilesCache ||
            activeDecomposedCanvasSmiles ||
            buildDecomposedCanvasSmiles(
              decomposedEditorState?.currentCoreSmiles.trim() ?? decomposition?.labeled_core_smiles ?? "",
              decomposedEditorState?.rGroups ?? decomposition?.r_groups ?? []
            )
          : globalCompoundSmilesCache ||
            compoundSmiles.trim() ||
            decomposedEditorState?.originalCompoundSmiles.trim() ||
            "";
      if (!nextSmiles) {
        throw new Error("No structure is available for that mode.");
      }
      const appliedSmiles = ((await setCanvasSmiles(nextSmiles)) ?? nextSmiles).trim() || nextSmiles;
      setEditorMode(nextMode);
      globalKetcherEditorString = appliedSmiles;
      setEditorSmiles(appliedSmiles);
      setSmilesText(appliedSmiles);
      if (nextMode === "compound") {
        globalCompoundSmilesCache = appliedSmiles;
        setCompoundSmiles(appliedSmiles);
      } else {
        globalDecomposedSmilesCache = appliedSmiles;
        setDecomposedEditorState((current) =>
          current
            ? {
                ...current,
                currentCoreSmiles: extractCoreSmilesFromDecomposedCanvas(appliedSmiles, current.currentCoreSmiles),
                coreModified:
                  extractCoreSmilesFromDecomposedCanvas(appliedSmiles, current.currentCoreSmiles) !==
                  current.lastAnalyzedCoreSmiles
              }
            : current
        );
      }
    } catch (modeError) {
      setError(modeError instanceof Error ? modeError.message : "Failed to switch editor mode");
    } finally {
      setEditorLoading(false);
    }
  };

  const handleUpdateRecommendations = async () => {
    setError(null);
    try {
      const canvasSmiles = (await ketcherRef.current?.getSmiles())?.trim() ?? editorSmiles.trim();
      const querySmiles =
        editorMode === "decomposed"
          ? extractCoreSmilesFromDecomposedCanvas(
              canvasSmiles,
              decomposedEditorState?.currentCoreSmiles ?? decomposition?.labeled_core_smiles ?? ""
            )
          : canvasSmiles || compoundSmiles.trim();
      if (!querySmiles) {
        throw new Error("Draw a molecule in Ketcher first.");
      }

      if (editorMode === "decomposed") {
        const nextDecomposedCanvasSmiles = buildDecomposedCanvasSmiles(
          querySmiles,
          decomposedEditorState?.rGroups ?? decomposition?.r_groups ?? []
        );
        setDecomposedEditorState((current) =>
          current
            ? {
                ...current,
                currentCoreSmiles: querySmiles,
                coreModified: querySmiles !== current.lastAnalyzedCoreSmiles
              }
            : current
        );
        setEditorSmiles(nextDecomposedCanvasSmiles);
        setSmilesText(nextDecomposedCanvasSmiles);
        globalKetcherEditorString = nextDecomposedCanvasSmiles;
        await refreshRecommendations(querySmiles, decomposedEditorState?.attachmentPoints ?? attachmentPointOptions);
        return querySmiles;
      }

      syncStructureState(querySmiles);
      await refreshRecommendations(querySmiles, decomposition?.attachment_points ?? []);
      return querySmiles;
    } catch (recommendationError) {
      setError(recommendationError instanceof Error ? recommendationError.message : "Failed to update recommendations");
      return "";
    }
  };

  const handleRecommendFromCoreSmiles = async () => {
    setError(null);
    try {
      const querySmiles = recommendationSmilesText.trim();
      if (!querySmiles) {
        throw new Error("Paste a core SMILES string first.");
      }
      await refreshRecommendations(querySmiles, decomposedEditorState?.attachmentPoints ?? decomposition?.attachment_points ?? []);
      return querySmiles;
    } catch (recommendationError) {
      setError(
        recommendationError instanceof Error ? recommendationError.message : "Failed to update recommendations"
      );
      return "";
    }
  };

  const handleIntegrateFragment = async (fragmentSmiles: string, failureMessage: string) => {
    setApplyLoading(true);
    setError(null);
    try {
      const nextFragmentSmiles = fragmentSmiles.trim();
      if (!nextFragmentSmiles) {
        throw new Error("No structure is available to integrate.");
      }
      const currentSmiles = globalKetcherEditorString.trim();
      let combinedSmiles = nextFragmentSmiles;
      if (currentSmiles) {
        const currentParts = currentSmiles.split('|');
        const currentBase = currentParts[0].trim();
        const currentCx = currentParts.length > 1 ? '|' + currentParts.slice(1).join('|') : '';
        const nextParts = nextFragmentSmiles.split('|');
        const nextBase = nextParts[0].trim();
        combinedSmiles = `${currentBase}.${nextBase} ${currentCx}`.trim();
      }
      const appliedSmiles = ((await setCanvasSmiles(combinedSmiles)) ?? combinedSmiles).trim() || combinedSmiles;
      // Keep current recommendations stable after lightweight editor appends.
      syncEditorOnlyState(appliedSmiles);
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : failureMessage);
    } finally {
      setApplyLoading(false);
    }
  };

  const handleIntegrateCore = async (displayCoreSmiles: string, applyCoreSmiles: string) => {
    await handleIntegrateFragment(applyCoreSmiles || displayCoreSmiles, "Failed to integrate core recommendation");
    setSelectedCore(displayCoreSmiles);
    setSelectedApplyCoreSmiles(applyCoreSmiles || displayCoreSmiles);
  };

  const handleApplyCoreToScaffold = async (displayCoreSmiles: string, applyCoreSmiles: string) => {
    setApplyLoading(true);
    setError(null);
    try {
      const currentSmiles = await resolveSmilesQuery();
      const response = await applyModification({
        current_smiles: currentSmiles,
        target_core_smiles: applyCoreSmiles || displayCoreSmiles
      });
      await applyCanvasUpdate(response, displayCoreSmiles, applyCoreSmiles || displayCoreSmiles);
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : "Failed to apply core recommendation");
    } finally {
      setApplyLoading(false);
    }
  };

  const handleIntegrateRGroup = async (rgroupSmiles: string) => {
    await handleIntegrateFragment(rgroupSmiles, "Failed to integrate R-group recommendation");
  };

  const handleApplyRGroup = async (rgroupSmiles: string) => {
    setApplyLoading(true);
    setError(null);
    try {
      const currentSmiles = await resolveSmilesQuery();
      const response = await applyModification({
        current_smiles: currentSmiles,
        target_core_smiles: selectedApplyCoreSmiles || decomposition?.labeled_core_smiles || selectedCore || undefined,
        attachment_point: selectedAttachmentPoint,
        rgroup_smiles: rgroupSmiles
      });
      await applyCanvasUpdate(
        response,
        selectedCore || decomposition?.reduced_core || response.core_smiles,
        selectedApplyCoreSmiles || decomposition?.labeled_core_smiles || response.core_smiles
      );
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : "Failed to apply R-group suggestion");
    } finally {
      setApplyLoading(false);
    }
  };

  const handleSelectCore = (displayCoreSmiles: string, applyCoreSmiles: string) => {
    setSelectedCore(displayCoreSmiles);
    setSelectedApplyCoreSmiles(applyCoreSmiles || displayCoreSmiles);
  };

  return {
    ketcherRef,
    smilesText,
    setSmilesText,
    editorSmiles,
    resolveSmilesQuery,
    editorLoading,
    analysisLoading,
    applyLoading,
    error,
    similarCoreItems,
    rGroupItems,
    exactCoreRecommendations,
    activeRecommendationCore,
    selectedCore,
    selectedApplyCoreSmiles,
    selectedAttachmentPoint,
    setSelectedAttachmentPoint,
    selectedMapCompound,
    selectedMapCluster,
    similarCoresLoading,
    rGroupsLoading,
    similarCoresError,
    rGroupsError,
    exactCoreLoading,
    exactCoreError,
    editorMode,
    modeSubtitle,
    decomposition,
    decomposedEditorState,
    activeCoreSmiles,
    recommendationSmilesText,
    setRecommendationSmilesText,
    attachmentPointOptions,
    analysisStale,
    handleEditorSmilesChange,
    handleLoadStructureIntoEditor,
    handleLoadSmilesIntoEditor,
    handleUseEditorSmiles,
    handleAnalyzeScaffold,
    handleUpdateRecommendations,
    handleRecommendFromCoreSmiles,
    handleClearDraft,
    handleSwitchEditorMode,
    handleSelectCompoundFromMap,
    handleSelectMapCluster,
    handleIntegrateCore,
    handleApplyCoreToScaffold,
    handleSelectCore,
    handleIntegrateRGroup,
    handleApplyRGroup
  };
}
