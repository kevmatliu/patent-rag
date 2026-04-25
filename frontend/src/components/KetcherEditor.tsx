import { forwardRef, useImperativeHandle, useRef, useState, useEffect } from "react";
import { Editor } from "ketcher-react";
// @ts-ignore
import { StandaloneStructServiceProvider } from "ketcher-standalone";
import "ketcher-react/dist/index.css";

export interface KetcherEditorHandle {
  getSmiles: () => Promise<string>;
  setSmiles: (smiles: string) => Promise<string>;
  appendSmiles: (smiles: string) => Promise<string>;
  clear: () => Promise<void>;
}

interface KetcherEditorProps {
  value: string;
  onSmilesChange?: (smiles: string) => void;
  height?: number | string;
}

const structServiceProvider = new StandaloneStructServiceProvider();

export const KetcherEditor = forwardRef<KetcherEditorHandle, KetcherEditorProps>(function KetcherEditor(
  { value, onSmilesChange, height = 600 },
  ref
) {
  const [ketcherInstance, setKetcherInstance] = useState<any>(null);
  const lastAppliedSmilesRef = useRef("");
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if ((window as any).ketcher === ketcherInstance) {
        (window as any).ketcher = null;
      }
    };
  }, [ketcherInstance]);

  useImperativeHandle(
    ref,
    () => ({
      async getSmiles() {
        if (!ketcherInstance) return "";
        try {
          return await ketcherInstance.getSmiles();
        } catch (e) {
          console.error("Ketcher native getSmiles error", e);
          return "";
        }
      },
      async setSmiles(smiles: string) {
        const nextSmiles = smiles.trim();
        if (!ketcherInstance) {
          return "";
        }
        try {
          await ketcherInstance.setMolecule(nextSmiles);
          lastAppliedSmilesRef.current = nextSmiles;
          return nextSmiles;
        } catch (e) {
          console.error("Ketcher native setMolecule error", e);
          return "";
        }
      },
      async appendSmiles(smiles: string) {
        const nextSmiles = smiles.trim();
        if (!ketcherInstance || !nextSmiles) {
          return "";
        }
        try {
          await ketcherInstance.addFragment(nextSmiles);
          await ketcherInstance.layout();
          return nextSmiles;
        } catch (e) {
          console.error("Ketcher native addFragment error", e);
          return "";
        }
      },
      async clear() {
        if (!ketcherInstance) {
          return;
        }
        try {
          await ketcherInstance.setMolecule("");
          lastAppliedSmilesRef.current = "";
        } catch (e) {
          console.error("Ketcher native clear error", e);
        }
      }
    }),
    [ketcherInstance]
  );

  useEffect(() => {
    const nextSmiles = value.trim();
    if (!ketcherInstance || nextSmiles === lastAppliedSmilesRef.current) {
      return;
    }

    void (async () => {
      try {
        await ketcherInstance.setMolecule(nextSmiles);
        if (isMountedRef.current) {
          lastAppliedSmilesRef.current = nextSmiles;
        }
      } catch (error) {
        if (isMountedRef.current) {
          console.error("Failed to load generic SMILES into Ketcher", error);
        }
      }
    })();
  }, [value, ketcherInstance]);

  return (
    <div className="ketcher-frame-wrap" style={{ height, position: "relative" }}>
      <Editor
        staticResourcesUrl=""
        structServiceProvider={structServiceProvider}
        errorHandler={(message: string) => console.error(message)}
        onInit={(ketcher) => {
          setKetcherInstance(ketcher);
          (window as any).ketcher = ketcher;
        }}
      />
    </div>
  );
});
