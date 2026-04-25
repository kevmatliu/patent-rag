import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getSmilesMock = vi.fn();
const setSmilesMock = vi.fn();
const recommendSimilarCoresMock = vi.fn();
const recommendRGroupsMock = vi.fn();
const applyModificationMock = vi.fn();
const decomposeStructureMock = vi.fn();
const renderSmilesSvgMock = vi.fn();

vi.mock("../api/patents", async () => {
  const actual = await vi.importActual("../api/patents");
  return {
    ...actual,
    recommendSimilarCores: (...args: unknown[]) => recommendSimilarCoresMock(...args),
    recommendRGroups: (...args: unknown[]) => recommendRGroupsMock(...args),
    applyModification: (...args: unknown[]) => applyModificationMock(...args),
    decomposeStructure: (...args: unknown[]) => decomposeStructureMock(...args),
    renderSmilesSvg: (...args: unknown[]) => renderSmilesSvgMock(...args)
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

      return <div data-testid="mock-ketcher-editor">{value}</div>;
    })
  };
});

import { CompoundExplorationWorkspacePage } from "./CompoundExplorationWorkspacePage";

describe("CompoundExplorationWorkspacePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSmilesMock.mockResolvedValue("canvas-smiles");
    setSmilesMock.mockImplementation(async (smiles: string) => smiles);
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
        reason: "frequent at R1"
      }
    ]);
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
  });

  afterEach(() => {
    cleanup();
  });

  it("loads typed SMILES into the center editor", async () => {
    const user = userEvent.setup();
    render(<CompoundExplorationWorkspacePage />);

    await user.type(screen.getByLabelText("SMILES Input"), "CCO");
    await user.click(screen.getByRole("button", { name: "Load into editor" }));

    await waitFor(() => {
      expect(setSmilesMock).toHaveBeenCalledWith("CCO");
    });
    expect(screen.getByTestId("mock-ketcher-editor")).toHaveTextContent("CCO");
  });

  it("syncs Ketcher content back into the panel and analyzes scaffold state", async () => {
    const user = userEvent.setup();
    render(<CompoundExplorationWorkspacePage />);

    await user.click(screen.getByRole("button", { name: "Use editor SMILES" }));
    await waitFor(() => {
      expect(screen.getByLabelText("SMILES Input")).toHaveValue("canvas-smiles");
    });

    getSmilesMock.mockResolvedValueOnce("Clc1ccccc1");
    await user.click(screen.getByRole("button", { name: "Analyze Scaffold" }));

    await waitFor(() => {
      expect(decomposeStructureMock).toHaveBeenCalledWith("Clc1ccccc1");
    });
    expect(screen.getByText("Current decomposition")).toBeInTheDocument();
    expect(screen.getAllByText("Cl[*:1]").length).toBeGreaterThan(0);
  });

  it("shows hover previews and supports both integrate and scaffold-aware apply actions", async () => {
    const user = userEvent.setup();
    render(<CompoundExplorationWorkspacePage />);

    await user.type(screen.getByLabelText("SMILES Input"), "CCO");
    await user.click(screen.getByRole("button", { name: "Load into editor" }));
    await screen.findByText("Similar Core Recommendations");

    const integrateButtons = await screen.findAllByRole("button", { name: "Integrate" });
    await user.hover(screen.getByText("c1ccc([*:1])cc1"));

    await waitFor(() => {
      expect(renderSmilesSvgMock).toHaveBeenCalledWith("c1ccc([*:1])cc1");
    });
    expect(await screen.findByTestId("smiles-hover-preview")).toBeInTheDocument();

    await user.click(integrateButtons[0]);
    await waitFor(() => {
      expect(setSmilesMock).toHaveBeenCalledWith("c1ccc([*:1])cc1");
    });

    getSmilesMock.mockResolvedValueOnce("Clc1ccccc1");
    await user.click(screen.getByRole("button", { name: "Analyze Scaffold" }));
    await waitFor(() => {
      expect(decomposeStructureMock).toHaveBeenCalledWith("Clc1ccccc1");
    });

    await waitFor(() => {
      expect(recommendRGroupsMock).toHaveBeenCalled();
    });
    await user.click(await screen.findByRole("button", { name: "Apply to R1" }));
    await waitFor(() => {
      expect(applyModificationMock).toHaveBeenCalledWith({
        current_smiles: "canvas-smiles",
        target_core_smiles: "c1ccc([*:1])cc1",
        attachment_point: "R1",
        rgroup_smiles: "Cl[*:1]"
      });
    });

    await user.click(screen.getByRole("button", { name: "Apply to scaffold" }));
    await waitFor(() => {
      expect(applyModificationMock).toHaveBeenCalledWith({
        current_smiles: "canvas-smiles",
        target_core_smiles: "c1ccc([*:1])cc1"
      });
    });
  });
});
