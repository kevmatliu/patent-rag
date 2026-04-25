import { API_BASE_URL } from "../api/client";
import type { SearchResultItem } from "../api/patents";

interface ResultCardProps {
  result: SearchResultItem;
  searchMode: "smiles" | "image" | "structure";
}

export function ResultCard({ result, searchMode }: ResultCardProps) {
  const similarityPercent = Math.round(result.similarity * 100);
  const similarityLabel = searchMode === "structure" ? "Core Similarity" : "SMILES Similarity";

  return (
    <article className="result-card-premium">
      <div className="result-card-left">
        <div className="result-image-container">
          <img src={`${API_BASE_URL}${result.image_url}`} alt={`Compound ${result.image_id}`} />
        </div>
        
        <a 
          href={result.patent_source_url} 
          target="_blank" 
          rel="noreferrer" 
          className="view-patent-btn-premium"
        >
          Explore Patent
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
            <polyline points="15 3 21 3 21 9"></polyline>
            <line x1="10" y1="14" x2="21" y2="3"></line>
          </svg>
        </a>
      </div>

      <div className="result-info">
        <div className="result-header">
          <div className="result-meta">
            <span className="result-badge">ID: {result.image_id}</span>
            <span className="result-badge patent">Patent: {result.patent_code}</span>
            <span className="result-badge">Page: {result.page_number ?? "n/a"}</span>
          </div>
        </div>

        <div className="result-smiles-block">
          <span className="result-smiles-label">SMILES Structure</span>
          <div className="result-smiles-value">{result.smiles || "No SMILES available"}</div>
        </div>

        <div className="result-footer">
          <div className="similarity-meter-container">
            <div className="similarity-label">
              <span>{similarityLabel}</span>
              <strong>{similarityPercent}%</strong>
            </div>
            <div className="similarity-bar-bg">
              <div 
                className="similarity-bar-fill" 
                style={{ width: `${similarityPercent}%` }}
              ></div>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}
