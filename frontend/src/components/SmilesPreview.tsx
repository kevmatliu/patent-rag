interface SmilesPreviewProps {
  smiles: string;
  label?: string;
}

export function SmilesPreview({ smiles, label = "SMILES" }: SmilesPreviewProps) {
  return (
    <div className="smiles-preview">
      <span className="smiles-preview-label">{label}</span>
      <code className="smiles-preview-value">{smiles || "n/a"}</code>
    </div>
  );
}
