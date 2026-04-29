import { SmilesStructurePreview } from "../SmilesHoverPreview";

interface RecommendationPreviewCardProps {
  title?: string;
  smiles: string;
  subtitle?: string;
  meta?: string;
  onZoom: (smiles: string, title: string) => void;
  onAdd: (smiles: string) => void | Promise<void>;
  onShow: () => void;
  addLabel?: string;
  showLabel?: string;
  disabled?: boolean;
}

export function RecommendationPreviewCard({
  title,
  smiles,
  subtitle,
  meta,
  onZoom,
  onAdd,
  onShow,
  addLabel = "Add",
  showLabel = "Show",
  disabled = false
}: RecommendationPreviewCardProps) {
  return (
    <article className="recommendation-preview-card">
      {title || meta ? (
        <div className="recommendation-card-topline">
          {title ? <span className="workspace-kicker">{title}</span> : <span />}
          {meta ? <span className="badge badge-neutral">{meta}</span> : null}
        </div>
      ) : null}
      {subtitle ? <p className="muted recommendation-preview-subtitle">{subtitle}</p> : null}
      <button
        type="button"
        className="recommendation-preview-button"
        onClick={() => onZoom(smiles, title ?? "Recommendation")}
        aria-label={`Zoom ${title ?? "recommendation"}`}
      >
        <SmilesStructurePreview smiles={smiles} />
      </button>
      <div className="recommendation-preview-actions">
        <button className="secondary-button xsmall" type="button" onClick={() => void onAdd(smiles)} disabled={disabled}>
          {addLabel}
        </button>
        <button className="secondary-button xsmall" type="button" onClick={onShow}>
          {showLabel}
        </button>
      </div>
    </article>
  );
}
