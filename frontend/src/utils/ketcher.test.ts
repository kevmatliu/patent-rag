import { describe, expect, it } from "vitest";
import { KETCHER_LOAD_TIMEOUT_MS, setKetcherSmiles, waitForKetcherBridge } from "./ketcher";

function makeFrameWithBridge(bridge: {
  isReady(): boolean;
  getSmiles(): Promise<string>;
  setSmiles(smiles: string): Promise<string>;
}): HTMLIFrameElement {
  return {
    contentWindow: {
      ketcherBridge: bridge
    }
  } as HTMLIFrameElement;
}

describe("ketcher bridge helpers", () => {
  it("returns the confirmed SMILES from the iframe bridge", async () => {
    const frame = makeFrameWithBridge({
      isReady: () => true,
      getSmiles: async () => "CCN",
      setSmiles: async (smiles: string) => `${smiles}-confirmed`
    });

    await expect(setKetcherSmiles(frame, "c1ccccc1", KETCHER_LOAD_TIMEOUT_MS)).resolves.toBe("c1ccccc1-confirmed");
  });

  it("waits for a ready bridge and throws if the iframe never becomes ready", async () => {
    const frame = makeFrameWithBridge({
      isReady: () => false,
      getSmiles: async () => "",
      setSmiles: async () => ""
    });

    await expect(waitForKetcherBridge(frame, 10)).rejects.toThrow("Ketcher is still loading");
  });
});
