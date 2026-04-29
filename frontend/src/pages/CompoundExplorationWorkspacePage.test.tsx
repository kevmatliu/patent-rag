import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getSmilesMock = vi.fn();
const setSmilesMock = vi.fn();
const recommendSimilarCoresMock = vi.fn();
const recommendExactCoreRGroupsMock = vi.fn();
const recommendRGroupsMock = vi.fn();
const applyModificationMock = vi.fn();
const decomposeStructureMock = vi.fn();
const renderSmilesSvgMock = vi.fn();
const getCompoundSpaceMapMock = vi.fn();
const searchBySmilesMock = vi.fn();
const searchByImageMock = vi.fn();
const getPatentCodesMock = vi.fn();

vi.mock("../api/patents", async () => {
  const actual = await vi.importActual("../api/patents");
  return {
    ...actual,
    recommendSimilarCores: (...args: unknown[]) => recommendSimilarCoresMock(...args),
    recommendExactCoreRGroups: (...args: unknown[]) => recommendExactCoreRGroupsMock(...args),
    recommendRGroups: (...args: unknown[]) => recommendRGroupsMock(...args),
    applyModification: (...args: unknown[]) => applyModificationMock(...args),
    decomposeStructure: (...args: unknown[]) => decomposeStructureMock(...args),
    renderSmilesSvg: (...args: unknown[]) => renderSmilesSvgMock(...args),
    getCompoundSpaceMap: (...args: unknown[]) => getCompoundSpaceMapMock(...args),
    searchBySmiles: (...args: unknown[]) => searchBySmilesMock(...args),
    searchByImage: (...args: unknown[]) => searchByImageMock(...args),
    getPatentCodes: (...args: unknown[]) => getPatentCodesMock(...args)
  };
});

vi.mock("../components/KetcherEditor", async () => {
  const ReactModule = await vi.importActual<typeof import("react")>("react");
  return {
    KetcherEditor: ReactModule.forwardRef(function MockKetcherEditor(
      {
        value,
        onSmilesChange
      }: {
        value: string;
        onSmilesChange?: (smiles: string) => void;
        height?: number | string;
      },
      ref: React.ForwardedRef<{
        getSmiles: () => Promise<string>;
        setSmiles: (smiles: string) => Promise<string>;
        appendSmiles: (smiles: string) => Promise<string>;
        clear: () => Promise<void>;
      }>
    ) {
      ReactModule.useImperativeHandle(ref, () => ({
        getSmiles: () => getSmilesMock(),
        setSmiles: async (smiles: string) => {
          const result = ((await setSmilesMock(smiles)) as string | undefined) ?? smiles;
          onSmilesChange?.(result);
          return result;
        },
        appendSmiles: async (smiles: string) => {
          const result = ((await setSmilesMock(smiles)) as string | undefined) ?? smiles;
          onSmilesChange?.(result);
          return result;
        },
        clear: async () => undefined
      }));

      return (
        <div>
          <div data-testid="mock-ketcher-editor">{value}</div>
          <button type="button" onClick={() => onSmilesChange?.("edited-smiles")} data-testid="mock-ketcher-live-change">
            Trigger Live Change
          </button>
        </div>
      );
    })
  };
});

import { CompoundExplorationWorkspacePage } from "./CompoundExplorationWorkspacePage";

describe("CompoundExplorationWorkspacePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    getSmilesMock.mockResolvedValue("canvas-smiles");
    setSmilesMock.mockImplementation(async (smiles: string) => smiles);
    getCompoundSpaceMapMock.mockResolvedValue({
      nodes: [
        {
          compound_id: 101,
          patent_id: 11,
          patent_code: "US20250042916A1",
          patent_source_url: "https://patents.google.com/patent/US20250042916A1/en",
          image_url: "/static/extracted/compound-a.png",
          page_number: 7,
          canonical_smiles: "CCO",
          smiles: "CCO",
          has_embedding: true,
          x: 0.2,
          y: 0.8,
          cluster_id: 0
        }
      ],
      clusters: [
        {
          cluster_id: 0,
          x: 0.2,
          y: 0.8,
          member_count: 1,
          patent_counts: {
            US20250042916A1: 1
          }
        }
      ]
    });
    recommendSimilarCoresMock.mockResolvedValue([
      {
        core_smiles: "c1ccccc1",
        apply_core_smiles: "c1ccc([*:1])cc1",
        score: 0.91,
        support_count: 3,
        reason: "embedding similarity"
      }
    ]);
    recommendRGroupsMock.mockResolvedValue([
      {
        rgroup_smiles: "Cl[*:1]",
        count: 4,
        reason: "frequent at R1",
        compound_ids: [101],
        exact_match: true
      }
    ]);
    recommendExactCoreRGroupsMock.mockResolvedValue({
      query_core_smiles: "c1ccccc1",
      attachment_points: ["R1"],
      exact_core_found: true,
      columns: [
        {
          attachment_point: "R1",
          items: [
            {
              rgroup_smiles: "Cl[*:1]",
              count: 4,
              reason: "frequent at R1",
              compound_ids: [101],
              exact_match: true
            }
          ]
        }
      ]
    });
    applyModificationMock.mockResolvedValue({
      smiles: "CCN",
      core_smiles: "c1ccc([*:1])cc1"
    });
    decomposeStructureMock.mockResolvedValue({
      canonical_smiles: "Clc1ccccc1",
      reduced_core: "c1ccccc1",
      labeled_core_smiles: "c1ccc([*:1])cc1",
      attachment_points: ["R1"],
      r_groups: [{ r_label: "R1", r_group: "Cl[*:1]" }]
    });
    renderSmilesSvgMock.mockResolvedValue({
      svg: "<svg><rect width='10' height='10'></rect></svg>"
    });
    searchBySmilesMock.mockResolvedValue({
      query_smiles: "CCO",
      results: [
        {
          image_id: 101,
          similarity: 0.97,
          smiles: "CCO",
          image_url: "/static/extracted/compound-a.png",
          patent_code: "US20250042916A1",
          page_number: 7,
          patent_source_url: "https://patents.google.com/patent/US20250042916A1/en"
        }
      ]
    });
    searchByImageMock.mockResolvedValue({
      query_smiles: "CCO",
      results: []
    });
    getPatentCodesMock.mockResolvedValue(["US20250042916A1"]);
  });

  afterEach(() => {
    cleanup();
  });

  it("loads the compound-space map and syncs node selection into the editor workflow", async () => {
    const user = userEvent.setup();
    const { container } = render(<CompoundExplorationWorkspacePage />);

    expect(container.querySelector(".compound-exploration-top-panel")).toBeTruthy();
    expect(container.querySelector(".compound-exploration-workspace-row")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Display Full Compound" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit Decomposed Scaffold" })).toBeDisabled();

    await user.hover(await screen.findByTestId("compound-space-node-101"));
    expect(await screen.findByTestId("compound-space-node-tooltip")).toHaveTextContent("US20250042916A1");
    await waitFor(() => {
      expect(renderSmilesSvgMock).toHaveBeenCalledWith("CCO");
    });
    expect(await screen.findByTestId("compound-space-node-structure-preview")).toBeInTheDocument();

    await user.click(screen.getByTestId("compound-space-node-101"));

    await waitFor(() => {
      expect(setSmilesMock).toHaveBeenCalledWith("CCO");
    });
    await waitFor(() => {
      expect(decomposeStructureMock).toHaveBeenCalledWith("canvas-smiles");
    });
    await waitFor(() => expect(recommendSimilarCoresMock).toHaveBeenCalledWith("c1ccc([*:1])cc1", 12));
    await waitFor(() => expect(recommendExactCoreRGroupsMock).toHaveBeenCalledWith("c1ccc([*:1])cc1", ["R1"], 12));
  });

  it("uses the global smiles search bar to highlight ranked map matches", async () => {
    const user = userEvent.setup();
    render(<CompoundExplorationWorkspacePage />);

    await user.click(screen.getByTestId("mock-ketcher-live-change"));
    await user.type(screen.getByRole("textbox"), "CCO");
    await user.click(screen.getByRole("button", { name: "Search Map" }));

    await waitFor(() => {
      expect(searchBySmilesMock).toHaveBeenCalledWith("CCO", 10, []);
    });
    expect(await screen.findByText("1 highlighted map match")).toBeInTheDocument();
    expect(screen.getByText("Search overlay active for CCO.")).toBeInTheDocument();
    expect(await screen.findByTestId("compound-space-node-101")).toHaveClass("matched");
    await waitFor(() => {
      expect(setSmilesMock).toHaveBeenCalledWith("CCO");
    });
    expect(screen.getByTestId("mock-ketcher-editor")).toHaveTextContent("CCO");
  });

  it("analyzes scaffold state from the active editor structure", async () => {
    const user = userEvent.setup();
    render(<CompoundExplorationWorkspacePage />);

    getSmilesMock.mockResolvedValueOnce("Clc1ccccc1");
    await user.click(screen.getByRole("button", { name: "Analyze Scaffold" }));

    await waitFor(() => {
      expect(decomposeStructureMock).toHaveBeenCalledWith("Clc1ccccc1");
    });
    await waitFor(() => {
      expect(setSmilesMock).toHaveBeenCalledWith("c1ccc([*:1])cc1.Cl[*:1]");
    });
    expect(screen.getByRole("button", { name: "Display Full Compound" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit Decomposed Scaffold" })).toBeEnabled();
    expect(screen.getByTestId("mock-ketcher-editor")).toHaveTextContent("c1ccc([*:1])cc1.Cl[*:1]");
  });

  it("updates the active structure preview when Ketcher emits a live change", async () => {
    const user = userEvent.setup();
    render(<CompoundExplorationWorkspacePage />);

    await user.click(screen.getByTestId("mock-ketcher-live-change"));

    await waitFor(() => {
      expect(screen.getAllByText("edited-smiles").length).toBeGreaterThan(0);
    });
  });

  it("supports tabbed recommendation previews plus add/show actions", async () => {
    const user = userEvent.setup();
    render(<CompoundExplorationWorkspacePage />);

    await user.click(await screen.findByTestId("compound-space-node-101"));
    await screen.findByRole("tab", { name: "R-group Recommendations" });
    expect(screen.getByRole("heading", { name: "R1" })).toBeInTheDocument();

    await user.click(screen.getByLabelText("Zoom recommendation"));
    expect(await screen.findByRole("dialog", { name: "Zoomed structure" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show" }));
    expect(await screen.findByText("1 map match highlighted.")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Similar Cores" }));
    await screen.findByRole("heading", { name: "Similar Cores" });
    await user.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => {
      expect(setSmilesMock).toHaveBeenCalledWith("c1ccc([*:1])cc1.Cl[*:1].c1ccc([*:1])cc1");
    });
  });

  it("shows the exact-core empty state and nudges users toward similar cores when no exact match exists", async () => {
    const user = userEvent.setup();
    recommendExactCoreRGroupsMock.mockResolvedValue({
      query_core_smiles: "c1ccccc1",
      attachment_points: ["R1"],
      exact_core_found: false,
      columns: []
    });

    render(<CompoundExplorationWorkspacePage />);

    await user.click(await screen.findByTestId("compound-space-node-101"));

    expect(await screen.findByText("No exact core found in the database.")).toBeInTheDocument();
    expect(screen.getByText("Try the Similar Cores tab to explore the nearest matching scaffolds.")).toBeInTheDocument();
  });

  it("keeps the original compound while decomposed mode updates recommendations from pasted core smiles", async () => {
    const user = userEvent.setup();
    render(<CompoundExplorationWorkspacePage />);

    getSmilesMock.mockResolvedValueOnce("Clc1ccccc1");
    await user.click(screen.getByRole("button", { name: "Analyze Scaffold" }));
    const recommendInput = await screen.findByLabelText("Recommend from pasted core SMILES");
    await user.clear(recommendInput);
    await user.click(recommendInput);
    await user.paste("c1ccc([*:2])cc1");
    await user.click(screen.getByRole("button", { name: "Recommend" }));

    await waitFor(() => {
      expect(recommendSimilarCoresMock).toHaveBeenCalledWith("c1ccc([*:2])cc1", 12);
    });
    await waitFor(() => {
      expect(recommendExactCoreRGroupsMock).toHaveBeenCalledWith("c1ccc([*:2])cc1", ["R1"], 12);
    });

    await user.click(screen.getByRole("button", { name: "Display Full Compound" }));
    await waitFor(() => {
      expect(setSmilesMock).toHaveBeenCalledWith("Clc1ccccc1");
    });
  });

  it("collapses and expands the exploration map on demand", async () => {
    const user = userEvent.setup();
    render(<CompoundExplorationWorkspacePage />);
    const toggle = screen.getByRole("button", { name: "Collapse map" });
    const mapContent = document.getElementById("compound-exploration-map-content");

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(mapContent).toHaveClass("is-expanded");

    await user.click(toggle);

    expect(screen.getByRole("button", { name: "Expand map" })).toHaveAttribute("aria-expanded", "false");
    expect(mapContent).toHaveClass("is-collapsed");

    await user.click(screen.getByRole("button", { name: "Expand map" }));

    expect(screen.getByRole("button", { name: "Collapse map" })).toHaveAttribute("aria-expanded", "true");
    expect(mapContent).toHaveClass("is-expanded");
  });

  it("inserts detached R-groups before the CXSMILES suffix in decomposed mode", async () => {
    const user = userEvent.setup();
    decomposeStructureMock.mockResolvedValueOnce({
      canonical_smiles: "Clc1ccccc1",
      reduced_core: "c1ccccc1",
      labeled_core_smiles: "c1ccc([*:1])cc1 |$Core$|",
      attachment_points: ["R1"],
      r_groups: [{ r_label: "R1", r_group: "Cl[*:1]" }]
    });

    render(<CompoundExplorationWorkspacePage />);

    getSmilesMock.mockResolvedValueOnce("Clc1ccccc1");
    await user.click(screen.getByRole("button", { name: "Analyze Scaffold" }));

    await waitFor(() => {
      expect(setSmilesMock).toHaveBeenCalledWith("c1ccc([*:1])cc1.Cl[*:1] |$Core$|");
    });
  });

  it("shows compound-only actions before analysis and decomposed recommendation search after analysis", async () => {
    const user = userEvent.setup();
    render(<CompoundExplorationWorkspacePage />);

    expect(screen.getByRole("button", { name: "Analyze Scaffold" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search Similar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save to DB" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Recommend" })).toBeNull();

    getSmilesMock.mockResolvedValueOnce("Clc1ccccc1");
    await user.click(screen.getByRole("button", { name: "Analyze Scaffold" }));

    expect(await screen.findByRole("button", { name: "Recommend" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Search Similar" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Save to DB" })).toBeNull();
  });

  it("reuses similarity search to highlight the map from compound mode", async () => {
    const user = userEvent.setup();
    render(<CompoundExplorationWorkspacePage />);

    getSmilesMock.mockResolvedValueOnce("CCO");
    await user.click(screen.getByRole("button", { name: "Search Similar" }));

    await waitFor(() => {
      expect(searchBySmilesMock).toHaveBeenCalledWith("CCO", 10, []);
    });
    expect(await screen.findByText("1 highlighted map match")).toBeInTheDocument();
  });
});
