import { type PropsWithChildren, useEffect, useState } from "react";
import { renderSmilesSvg } from "../api/patents";

const svgCache = new Map<string, string>();

interface SmilesHoverPreviewProps extends PropsWithChildren {
  smiles: string;
}

export function SmilesHoverPreview({ smiles, children }: SmilesHoverPreviewProps) {
  const [open, setOpen] = useState(false);
  const [svg, setSvg] = useState<string | null>(svgCache.get(smiles) ?? null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSvg(svgCache.get(smiles) ?? null);
    setError(null);
  }, [smiles]);

  useEffect(() => {
    if (!open || !smiles.trim() || svgCache.has(smiles)) {
      return;
    }

    let cancelled = false;

    const loadPreview = async () => {
      try {
        const response = await renderSmilesSvg(smiles);
        if (cancelled) {
          return;
        }
        svgCache.set(smiles, response.svg);
        setSvg(response.svg);
      } catch (previewError) {
        if (!cancelled) {
          setError(previewError instanceof Error ? previewError.message : "Unable to render structure preview");
        }
      }
    };

    void loadPreview();
    return () => {
      cancelled = true;
    };
  }, [open, smiles]);

  return (
    <div
      className="smiles-hover-preview"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {children}
      {open ? (
        <div className="smiles-hover-preview-popover" data-testid="smiles-hover-preview">
          <div className="smiles-hover-preview-header">
            <span className="workspace-kicker">Structure Preview</span>
          </div>
          {svg ? (
            <div className="smiles-hover-preview-canvas" dangerouslySetInnerHTML={{ __html: svg }} />
          ) : error ? (
            <p className="muted">{error}</p>
          ) : (
            <p className="muted">Rendering preview...</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
