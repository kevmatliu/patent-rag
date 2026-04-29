import { useState } from "react";

interface SmilesPreviewProps {
  smiles: string;
  label?: string;
  copyable?: boolean;
}

export function SmilesPreview({ smiles, label = "SMILES", copyable = false }: SmilesPreviewProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const nextSmiles = smiles || "";
    if (!nextSmiles) {
      return;
    }
    try {
      await navigator.clipboard.writeText(nextSmiles);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch (error) {
      console.error("Failed to copy SMILES", error);
    }
  };

  return (
    <div className="smiles-preview">
      <div className="smiles-preview-header">
        <span className="smiles-preview-label">{label}</span>
        {copyable ? (
          <button className="smiles-preview-copy" type="button" onClick={() => void handleCopy()}>
            {copied ? "Copied" : "Copy"}
          </button>
        ) : null}
      </div>
      <code className="smiles-preview-value">{smiles || "n/a"}</code>
    </div>
  );
}
