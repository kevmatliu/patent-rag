interface RecommendationEmptyStateProps {
  title: string;
  description: string;
}

export function RecommendationEmptyState({ title, description }: RecommendationEmptyStateProps) {
  return (
    <div className="workspace-inline-state workspace-inline-state-soft recommendation-empty-state">
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}
