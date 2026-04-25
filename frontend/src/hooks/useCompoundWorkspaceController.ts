import { useEffect, useMemo, useRef, useState } from "react";
import {
  applyModification,
  decomposeStructure,
  recommendRGroups,
  recommendSimilarCores,
  type ApplyModificationResponse,
  type DecomposeStructureResponse,
  type RGroupRecommendationItem,
  type SimilarCoreRecommendationItem
} from "../api/patents";
import type { KetcherEditorHandle } from "../components/KetcherEditor";

const DEFAULT_ATTACHMENT_POINT_OPTIONS = ["R1", "R2", "R3", "R4", "R5", "R6"];

export function useCompoundWorkspaceController() {
  const ketcherRef = useRef<KetcherEditorHandle | null>(null);
  const selectedCoreRef = useRef("");
  const selectedApplyCoreRef = useRef("");
  const [smilesText, setSmilesText] = useState("");
  const [editorSmiles, setEditorSmiles] = useState("");
  const [activeMoleculeSmiles, setActiveMoleculeSmiles] = useState("");
  const [editorLoading, setEditorLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [applyLoading, setApplyLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [similarCoreItems, setSimilarCoreItems] = useState<SimilarCoreRecommendationItem[]>([]);
  const [rGroupItems, setRGroupItems] = useState<RGroupRecommendationItem[]>([]);
  const [selectedCore, setSelectedCore] = useState("");
  const [selectedApplyCoreSmiles, setSelectedApplyCoreSmiles] = useState("");
  const [selectedAttachmentPoint, setSelectedAttachmentPoint] = useState(DEFAULT_ATTACHMENT_POINT_OPTIONS[0]);
  const [similarCoresLoading, setSimilarCoresLoading] = useState(false);
  const [rGroupsLoading, setRGroupsLoading] = useState(false);
  const [similarCoresError, setSimilarCoresError] = useState<string | null>(null);
  const [rGroupsError, setRGroupsError] = useState<string | null>(null);
  const [decomposition, setDecomposition] = useState<DecomposeStructureResponse | null>(null);

  const attachmentPointOptions = useMemo(() => {
    if (decomposition?.attachment_points.length) {
      return decomposition.attachment_points;
    }
    return DEFAULT_ATTACHMENT_POINT_OPTIONS;
  }, [decomposition]);

  const analysisStale = Boolean(
    decomposition?.canonical_smiles &&
      activeMoleculeSmiles.trim() &&
      decomposition.canonical_smiles !== activeMoleculeSmiles.trim()
  );

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

  useEffect(() => {
    const processedSmiles = activeMoleculeSmiles.trim();
    if (!processedSmiles) {
      setSimilarCoreItems([]);
      setRGroupItems([]);
      setSelectedCore("");
      setSelectedApplyCoreSmiles("");
      setSimilarCoresError(null);
      setRGroupsError(null);
      return;
    }

    let cancelled = false;

    const loadSimilarCores = async () => {
      setSimilarCoresLoading(true);
      setSimilarCoresError(null);
      setRGroupItems([]);
      try {
        const response = await recommendSimilarCores(processedSmiles, 12);
        if (cancelled) {
          return;
        }
        setSimilarCoreItems(response);
        const nextSelectedCore =
          selectedCoreRef.current && response.some((item) => item.core_smiles === selectedCoreRef.current)
            ? selectedCoreRef.current
            : response[0]?.core_smiles ?? decomposition?.reduced_core ?? processedSmiles;
        const matched = response.find((item) => item.core_smiles === nextSelectedCore);

        setSelectedCore(nextSelectedCore);
        setSelectedApplyCoreSmiles(
          selectedApplyCoreRef.current &&
            response.some(
              (item) =>
                item.apply_core_smiles === selectedApplyCoreRef.current || item.core_smiles === selectedApplyCoreRef.current
            )
            ? selectedApplyCoreRef.current
            : matched?.apply_core_smiles ?? response[0]?.apply_core_smiles ?? decomposition?.labeled_core_smiles ?? processedSmiles
        );
      } catch (recommendationError) {
        if (!cancelled) {
          setSimilarCoreItems([]);
          setSelectedCore(decomposition?.reduced_core ?? processedSmiles);
          setSelectedApplyCoreSmiles(decomposition?.labeled_core_smiles ?? processedSmiles);
          setSimilarCoresError(
            recommendationError instanceof Error ? recommendationError.message : "Failed to load similar cores"
          );
        }
      } finally {
        if (!cancelled) {
          setSimilarCoresLoading(false);
        }
      }
    };

    void loadSimilarCores();
    return () => {
      cancelled = true;
    };
  }, [activeMoleculeSmiles, decomposition?.labeled_core_smiles, decomposition?.reduced_core]);

  useEffect(() => {
    const recommendationCore = selectedCore.trim() || decomposition?.reduced_core?.trim() || "";
    if (!recommendationCore) {
      setRGroupItems([]);
      setRGroupsError(null);
      return;
    }

    let cancelled = false;

    const loadRGroups = async () => {
      setRGroupsLoading(true);
      setRGroupsError(null);
      try {
        const response = await recommendRGroups(recommendationCore, selectedAttachmentPoint, 12);
        if (!cancelled) {
          setRGroupItems(response);
        }
      } catch (recommendationError) {
        if (!cancelled) {
          setRGroupItems([]);
          setRGroupsError(
            recommendationError instanceof Error ? recommendationError.message : "Failed to load R-group suggestions"
          );
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
  }, [decomposition?.reduced_core, selectedAttachmentPoint, selectedCore]);

  const clearDecomposition = () => {
    setDecomposition(null);
  };

  const syncStructureState = (nextSmiles: string) => {
    setEditorSmiles(nextSmiles);
    setActiveMoleculeSmiles(nextSmiles);
    setSmilesText(nextSmiles);
  };

  const handleLoadSmilesIntoEditor = async () => {
    const nextSmiles = smilesText.trim();
    if (!nextSmiles) {
      setError("Enter a SMILES string first.");
      return;
    }

    setEditorLoading(true);
    setError(null);
    try {
      const appliedSmiles = ((await ketcherRef.current?.setSmiles(nextSmiles)) ?? nextSmiles).trim() || nextSmiles;
      syncStructureState(appliedSmiles);
      clearDecomposition();
    } catch (editorError) {
      setError(editorError instanceof Error ? editorError.message : "Failed to load SMILES into Ketcher");
    } finally {
      setEditorLoading(false);
    }
  };

  const handleUseEditorSmiles = async () => {
    setEditorLoading(true);
    setError(null);
    try {
      const nextSmiles = (await ketcherRef.current?.getSmiles())?.trim() ?? "";
      if (!nextSmiles) {
        throw new Error("Draw a molecule in Ketcher first.");
      }
      syncStructureState(nextSmiles);
      clearDecomposition();
    } catch (editorError) {
      setError(editorError instanceof Error ? editorError.message : "Failed to export SMILES from Ketcher");
    } finally {
      setEditorLoading(false);
    }
  };

  const resolveSmilesQuery = async () => {
    const canvasSmiles = (await ketcherRef.current?.getSmiles())?.trim() ?? editorSmiles.trim();
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
      setSmilesText("");
      setEditorSmiles("");
      setActiveMoleculeSmiles("");
      setSelectedCore("");
      setSelectedApplyCoreSmiles("");
      setSimilarCoreItems([]);
      setRGroupItems([]);
      setSimilarCoresError(null);
      setRGroupsError(null);
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
      setDecomposition(response);
      setSelectedAttachmentPoint(response.attachment_points[0] ?? DEFAULT_ATTACHMENT_POINT_OPTIONS[0]);
      setSelectedApplyCoreSmiles(response.labeled_core_smiles);
      setSelectedCore((current) => current || response.reduced_core);
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : "Failed to analyze scaffold");
    } finally {
      setAnalysisLoading(false);
    }
  };

  const applyCanvasUpdate = async (
    response: ApplyModificationResponse,
    nextSelectedCore?: string,
    nextSelectedApplyCore?: string
  ) => {
    const appliedSmiles = ((await ketcherRef.current?.setSmiles(response.smiles)) ?? response.smiles).trim() || response.smiles;
    syncStructureState(appliedSmiles);
    clearDecomposition();
    setSelectedCore(nextSelectedCore ?? response.core_smiles);
    setSelectedApplyCoreSmiles(nextSelectedApplyCore ?? response.core_smiles);
  };

  const handleIntegrateFragment = async (fragmentSmiles: string, failureMessage: string) => {
    setApplyLoading(true);
    setError(null);
    try {
      const nextFragmentSmiles = fragmentSmiles.trim();
      if (!nextFragmentSmiles) {
        throw new Error("No structure is available to integrate.");
      }
      await ketcherRef.current?.appendSmiles(nextFragmentSmiles);
      const currentCanvasSmiles = (await ketcherRef.current?.getSmiles())?.trim() ?? activeMoleculeSmiles.trim();
      if (currentCanvasSmiles) {
        syncStructureState(currentCanvasSmiles);
      }
      clearDecomposition();
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
    activeMoleculeSmiles,
    editorLoading,
    analysisLoading,
    applyLoading,
    error,
    similarCoreItems,
    rGroupItems,
    selectedCore,
    selectedApplyCoreSmiles,
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
    handleIntegrateCore,
    handleApplyCoreToScaffold,
    handleSelectCore,
    handleIntegrateRGroup,
    handleApplyRGroup
  };
}
