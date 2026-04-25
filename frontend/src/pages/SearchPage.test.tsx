import React from "react";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const searchByImageJobMock = vi.fn();
const searchBySmilesJobMock = vi.fn();

vi.mock("../api/patents", async () => {
  const actual = await vi.importActual("../api/patents");
  return {
    ...actual,
    getJobStatus: vi.fn(),
    searchByImageJob: (...args: unknown[]) => searchByImageJobMock(...args),
    searchBySmilesJob: (...args: unknown[]) => searchBySmilesJobMock(...args)
  };
});

import { SearchPage } from "./SearchPage";

describe("SearchPage", () => {
  const clickSmilesInputToggle = async (user: ReturnType<typeof userEvent.setup>) => {
    const toggle = screen.getByRole("tablist", { name: "Search input type" });
    await user.click(within(toggle).getByRole("button", { name: "SMILES Similarity" }));
  };

  const clickImageInputToggle = async (user: ReturnType<typeof userEvent.setup>) => {
    const toggle = screen.getByRole("tablist", { name: "Search input type" });
    await user.click(within(toggle).getByRole("button", { name: "Image Recognition" }));
  };

  beforeEach(() => {
    vi.clearAllMocks();
    searchByImageJobMock.mockResolvedValue({ job_id: "job-image", status: "pending" });
    searchBySmilesJobMock.mockResolvedValue({ job_id: "job-smiles", status: "pending" });
  });

  afterEach(() => {
    cleanup();
  });

  it("toggles between SMILES and image inputs", async () => {
    const user = userEvent.setup();
    render(<SearchPage />);

    expect(screen.getByLabelText("SMILES Query")).toBeInTheDocument();
    expect(screen.queryByTestId("image-dropzone")).not.toBeInTheDocument();

    await clickImageInputToggle(user);

    expect(screen.getByTestId("image-dropzone")).toBeInTheDocument();
    expect(screen.queryByLabelText("SMILES Query")).not.toBeInTheDocument();
  });

  it("submits typed SMILES directly without using the editor", async () => {
    const user = userEvent.setup();
    render(<SearchPage />);

    await clickSmilesInputToggle(user);
    await user.type(screen.getByLabelText("SMILES Query"), "CCO");
    await user.click(screen.getByRole("button", { name: "Execute Search" }));

    await waitFor(() => {
      expect(searchBySmilesJobMock).toHaveBeenCalledWith("CCO", 12);
    });
  });
});
