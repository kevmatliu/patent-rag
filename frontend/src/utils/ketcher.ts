export const KETCHER_LOAD_TIMEOUT_MS = 12000;

interface KetcherBridge {
  isReady(): boolean;
  getSmiles(): Promise<string>;
  setSmiles(smiles: string): Promise<string>;
}

function getKetcherBridge(frame: HTMLIFrameElement): KetcherBridge | null {
  const contentWindow = frame.contentWindow as (Window & { ketcherBridge?: KetcherBridge }) | null;
  return contentWindow?.ketcherBridge ?? null;
}

export async function waitForKetcherBridge(
  frame: HTMLIFrameElement,
  timeoutMs = KETCHER_LOAD_TIMEOUT_MS
): Promise<KetcherBridge> {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const bridge = getKetcherBridge(frame);
    if (bridge?.isReady()) {
      return bridge;
    }

    await new Promise((resolve) => window.setTimeout(resolve, 25));
  }

  throw new Error("Ketcher is still loading");
}

export async function setKetcherSmiles(
  frame: HTMLIFrameElement,
  smiles: string,
  timeoutMs = KETCHER_LOAD_TIMEOUT_MS
): Promise<string> {
  const bridge = await waitForKetcherBridge(frame, timeoutMs);
  return bridge.setSmiles(smiles);
}
