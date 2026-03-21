import { API_BASE_URL } from "../api/client";
import type { SearchResultItem } from "../api/patents";

interface ResultCardProps {
  result: SearchResultItem;
}

export function ResultCard({ result }: ResultCardProps) {
  return (
    <article className="result-card">
      <div className="badge-row">
        <span className="badge">Image #{result.image_id}</span>
        <span className="badge">Patent {result.patent_code}</span>
        <span className="badge">Page {result.page_number ?? "n/a"}</span>
        <span className="badge">Similarity {result.similarity.toFixed(4)}</span>
      </div>
      <div className="grid two">
        <div>
          <img src={`${API_BASE_URL}${result.image_url}`} alt={`Compound ${result.image_id}`} />
        </div>
        <div>
          <p>
            <strong>SMILES</strong>
          </p>
          <p className="muted">{result.smiles || "No SMILES stored"}</p>
          <p>
            <strong>Patent URL</strong>
          </p>
          <a href={result.patent_source_url} target="_blank" rel="noreferrer">
            {result.patent_source_url}
          </a>
        </div>
      </div>
    </article>
  );
}
