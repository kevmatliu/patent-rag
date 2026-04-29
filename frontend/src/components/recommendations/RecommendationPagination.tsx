interface RecommendationPaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  compact?: boolean;
}

export function RecommendationPagination({
  page,
  totalPages,
  onPageChange,
  compact = false
}: RecommendationPaginationProps) {
  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className={`pagination-controls recommendation-pagination ${compact ? "is-compact" : ""}`}>
      <button
        className="secondary-button pagination-btn"
        type="button"
        disabled={page === 0}
        onClick={() => onPageChange(page - 1)}
      >
        &larr;
      </button>
      <span className="pagination-info">
        Page {page + 1} of {totalPages}
      </span>
      <button
        className="secondary-button pagination-btn"
        type="button"
        disabled={page >= totalPages - 1}
        onClick={() => onPageChange(page + 1)}
      >
        &rarr;
      </button>
    </div>
  );
}
