import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getSmilesMock = vi.fn();
const setSmilesMock = vi.fn();

const recommendSimilarCoresMock = vi.fn();
const recommendRGroupsMock = vi.fn();
const applyModificationMock = vi.fn();

vi.mock("../api/patents", async () => {
  const actual = await vi.importActual("../api/patents");
  return {
    ...actual,
    recommendSimilarCores: (...args: unknown[]) => recommendSimilarCoresMock(...args),
    recommendRGroups: (...args: unknown[]) => recommendRGroupsMock(...args),
    applyModification: (...args: unknown[]) => applyModificationMock(...args)
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

import { RecommendationWorkbenchPage } from "./RecommendationWorkbenchPage";

describe("RecommendationWorkbenchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSmilesMock.mockResolvedValue("canvas-smiles");
    setSmilesMock.mockImplementation(async (smiles: string) => smiles);
    recommendSimilarCoresMock.mockResolvedValue([]);
    recommendRGroupsMock.mockResolvedValue([]);
    applyModificationMock.mockResolvedValue({
      smiles: "CCN",
      core_smiles: "c1ccc([*:1])cc1"
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("loads typed SMILES into the editor", async () => {
    const user = userEvent.setup();
    render(<RecommendationWorkbenchPage />);

    const inputSmiles = "c1ccc(CCc2cc(-c3ccccc3)ccn2)cc1";
    await user.type(screen.getByLabelText("SMILES input"), inputSmiles);
    await user.click(screen.getByRole("button", { name: "Load into editor" }));

    await waitFor(() => {
      expect(setSmilesMock).toHaveBeenCalledWith(inputSmiles);
    });
    expect(screen.getByTestId("mock-ketcher-editor")).toHaveTextContent(inputSmiles);
  });

  it("appends the labeled apply core when append core is pressed", async () => {
    const user = userEvent.setup();
    recommendSimilarCoresMock.mockResolvedValue([
      {
        core_smiles: "c1ccccc1",
        apply_core_smiles: "c1ccc([*:1])cc1",
        score: 0.91,
        support_count: 3,
        reason: "embedding similarity"
      }
    ]);

    render(<RecommendationWorkbenchPage />);

    await user.type(screen.getByLabelText("SMILES input"), "CCO");
    await user.click(screen.getByRole("button", { name: "Load into editor" }));
    await screen.findByRole("button", { name: "Append core" });
    await user.click(screen.getByRole("button", { name: "Append core" }));

    await waitFor(() => {
      expect(setSmilesMock).toHaveBeenCalledWith("c1ccc([*:1])cc1");
    });
    expect(applyModificationMock).not.toHaveBeenCalled();
  });

  it("uses the selected labeled core when apply R-group is pressed", async () => {
    const user = userEvent.setup();
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

    render(<RecommendationWorkbenchPage />);

    await user.type(screen.getByLabelText("SMILES input"), "CCO");
    await user.click(screen.getByRole("button", { name: "Load into editor" }));
    await screen.findByRole("button", { name: "R-group suggestions" });
    await user.click(screen.getByRole("button", { name: "R-group suggestions" }));
    await screen.findByRole("button", { name: "Apply R1" });
    await user.click(screen.getByRole("button", { name: "Apply R1" }));

    await waitFor(() => {
      expect(applyModificationMock).toHaveBeenCalledWith({
        current_smiles: "canvas-smiles",
        target_core_smiles: "c1ccc([*:1])cc1",
        attachment_point: "R1",
        rgroup_smiles: "Cl[*:1]"
      });
    });
  });
});
