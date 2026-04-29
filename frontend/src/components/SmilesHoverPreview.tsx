import { type PropsWithChildren, useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import { renderSmilesSvg } from "../api/patents";

const svgCache = new Map<string, string>();

interface SmilesHoverPreviewProps extends PropsWithChildren {
  smiles: string;
}

interface SmilesStructurePreviewProps {
  smiles: string;
  loadingText?: string;
  errorText?: string;
  testId?: string;
}

export function SmilesStructurePreview({
  smiles,
  loadingText = "Rendering preview...",
  errorText = "Unable to render structure preview",
  testId
}: SmilesStructurePreviewProps) {
  const [svg, setSvg] = useState<string | null>(svgCache.get(smiles) ?? null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSvg(svgCache.get(smiles) ?? null);
    setError(null);
  }, [smiles]);

  useEffect(() => {
    if (!smiles.trim() || svgCache.has(smiles)) {
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
          setError(previewError instanceof Error ? previewError.message : errorText);
        }
      }
    };

    void loadPreview();
    return () => {
      cancelled = true;
    };
  }, [errorText, smiles]);

  if (svg) {
    return <div className="smiles-hover-preview-canvas" data-testid={testId} dangerouslySetInnerHTML={{ __html: svg }} />;
  }

  if (error) {
    return <p className="muted">{error}</p>;
  }

  return <p className="muted">{loadingText}</p>;
}

export function SmilesHoverPreview({ smiles, children }: SmilesHoverPreviewProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  useEffect(() => {
    if (open && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const popoverWidth = 300;
      let calculatedLeft = rect.left + window.scrollX - (popoverWidth - rect.width) / 2;
      const margin = 12;
      if (calculatedLeft < margin) calculatedLeft = margin;
      if (calculatedLeft + popoverWidth > window.innerWidth - margin) {
        calculatedLeft = window.innerWidth - popoverWidth - margin;
      }
      setCoords({
        top: rect.bottom + window.scrollY + 10,
        left: calculatedLeft
      });
    }
  }, [open]);

  return (
    <div
      ref={triggerRef}
      className="smiles-hover-preview"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {children}
      {open && typeof document !== "undefined" ? createPortal(
        <div 
          className="smiles-hover-preview-popover" 
          data-testid="smiles-hover-preview"
          style={{ position: 'absolute', top: `${coords.top}px`, left: `${coords.left}px`, zIndex: 99999 }}
        >
          <div className="smiles-hover-preview-header">
            <span className="workspace-kicker">Structure Preview</span>
          </div>
          <SmilesStructurePreview smiles={smiles} />
        </div>,
        document.body
      ) : null}
    </div>
  );
}
