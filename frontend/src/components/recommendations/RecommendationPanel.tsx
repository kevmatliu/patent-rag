import type {
  ExactCoreRGroupRecommendationResponse,
  RGroupRecommendationItem,
  SimilarCoreRecommendationItem
} from "../../api/patents";
import { RecommendationEmptyState } from "./RecommendationEmptyState";
import { RecommendationPagination } from "./RecommendationPagination";
import { RecommendationPreviewCard } from "./RecommendationPreviewCard";
import { RecommendationTabs, type RecommendationTabId } from "./RecommendationTabs";

const SIMILAR_CORES_PER_PAGE = 4;
const RGROUP_COLUMNS_PER_ROW = 2;

interface RecommendationPanelProps {
  activeTab: RecommendationTabId;
  onTabChange: (tab: RecommendationTabId) => void;
  exactCoreRecommendations: ExactCoreRGroupRecommendationResponse | null;
  exactCoreLoading: boolean;
  exactCoreError: string | null;
  similarCoreItems: SimilarCoreRecommendationItem[];
  similarCoresLoading: boolean;
  similarCoresError: string | null;
  similarCorePage: number;
  onSimilarCorePageChange: (page: number) => void;
  exactColumnPages: Record<string, number>;
  onExactColumnPageChange: (attachmentPoint: string, page: number) => void;
  onZoom: (smiles: string, title: string) => void;
  onAddRGroup: (smiles: string) => void | Promise<void>;
  onShowRGroup: (item: RGroupRecommendationItem, attachmentPoint: string) => void;
  onAddCore: (item: SimilarCoreRecommendationItem) => void | Promise<void>;
  onShowCore: (item: SimilarCoreRecommendationItem) => void;
  addDisabled?: boolean;
}

export function RecommendationPanel({
  activeTab,
  onTabChange,
  exactCoreRecommendations,
  exactCoreLoading,
  exactCoreError,
  similarCoreItems,
  similarCoresLoading,
  similarCoresError,
  similarCorePage,
  onSimilarCorePageChange,
  exactColumnPages,
  onExactColumnPageChange,
  onZoom,
  onAddRGroup,
  onShowRGroup,
  onAddCore,
  onShowCore,
  addDisabled = false
}: RecommendationPanelProps) {
  const similarCoreTotalPages = Math.max(1, Math.ceil(similarCoreItems.length / SIMILAR_CORES_PER_PAGE));
  const exactCoreRows = exactCoreRecommendations
    ? Array.from(
        { length: Math.ceil(exactCoreRecommendations.columns.length / RGROUP_COLUMNS_PER_ROW) },
        (_, rowIndex) =>
          exactCoreRecommendations.columns.slice(
            rowIndex * RGROUP_COLUMNS_PER_ROW,
            rowIndex * RGROUP_COLUMNS_PER_ROW + RGROUP_COLUMNS_PER_ROW
          )
      )
    : [];
  const visibleSimilarCores = similarCoreItems.slice(
    similarCorePage * SIMILAR_CORES_PER_PAGE,
    (similarCorePage + 1) * SIMILAR_CORES_PER_PAGE
  );

  return (
    <div className="recommendation-panel-shell">
      <RecommendationTabs activeTab={activeTab} onChange={onTabChange} />

      {activeTab === "rgroup-recommendations" ? (
        <div className="recommendation-panel-body">
          {exactCoreLoading ? (
            <RecommendationEmptyState title="Loading R-group recommendations" description="Collecting exact-core matches and attachment-specific fragments." />
          ) : exactCoreError ? (
            <div className="workspace-inline-state workspace-inline-state-error" role="alert">
              <strong>Could not load R-group recommendations</strong>
              <p>{exactCoreError}</p>
            </div>
          ) : !exactCoreRecommendations ? (
            <RecommendationEmptyState
              title="Analyze a scaffold to start recommendations"
              description="Recommendation columns will populate from the detected core and any pasted core SMILES."
            />
          ) : !exactCoreRecommendations?.exact_core_found ? (
            <RecommendationEmptyState
              title="No exact core found in the database."
              description="Try the Similar Cores tab to explore the nearest matching scaffolds."
            />
          ) : exactCoreRecommendations.columns.length === 0 ? (
            <RecommendationEmptyState
              title="No attachment points available"
              description="Analyze the current structure again if you expected labeled attachment points."
            />
          ) : (
            <div className="recommendation-rgroup-grid">
              {exactCoreRows.map((row, rowIndex) => (
                <div key={`rgroup-row-${rowIndex}`} className="recommendation-rgroup-row">
                  {row.map((column) => {
                    const page = Math.min(exactColumnPages[column.attachment_point] ?? 0, Math.max(0, column.items.length - 1));
                    const item = column.items[page] ?? null;
                    const totalPages = Math.max(1, column.items.length);
                    return (
                      <section key={column.attachment_point} className="recommendation-rgroup-column">
                        <div className="recommendation-column-header">
                          <div>
                            <span className="workspace-kicker">Attachment</span>
                            <h3>{column.attachment_point}</h3>
                          </div>
                          <RecommendationPagination
                            page={page}
                            totalPages={totalPages}
                            onPageChange={(nextPage) => onExactColumnPageChange(column.attachment_point, nextPage)}
                            compact
                          />
                        </div>
                        {item ? (
                          <RecommendationPreviewCard
                            title={undefined}
                            subtitle={item.reason}
                            meta={`${item.count} hit${item.count === 1 ? "" : "s"}`}
                            smiles={item.rgroup_smiles}
                            onZoom={onZoom}
                            onAdd={onAddRGroup}
                            onShow={() => onShowRGroup(item, column.attachment_point)}
                            disabled={addDisabled}
                          />
                        ) : (
                          <RecommendationEmptyState
                            title={`No ${column.attachment_point} suggestions`}
                            description="No exact-core fragment suggestions are stored for this attachment point yet."
                          />
                        )}
                      </section>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="recommendation-panel-body">
          <div className="recommendation-cluster-header">
            <div>
              <span className="workspace-kicker">Nearest matches</span>
              <h3>Similar Cores</h3>
            </div>
            <RecommendationPagination
              page={Math.min(similarCorePage, similarCoreTotalPages - 1)}
              totalPages={similarCoreTotalPages}
              onPageChange={onSimilarCorePageChange}
            />
          </div>
          {similarCoresLoading ? (
            <RecommendationEmptyState title="Loading similar cores" description="Ranking nearby scaffolds for the current active core." />
          ) : similarCoresError ? (
            <div className="workspace-inline-state workspace-inline-state-error" role="alert">
              <strong>Could not load similar cores</strong>
              <p>{similarCoresError}</p>
            </div>
          ) : visibleSimilarCores.length === 0 ? (
            <RecommendationEmptyState
              title="No similar cores available"
              description="Analyze a scaffold or paste a core SMILES to seed the recommendation engine."
            />
          ) : (
            <div className="recommendation-similar-grid">
              {visibleSimilarCores.map((item) => (
                <RecommendationPreviewCard
                  key={`${item.core_smiles}-${item.apply_core_smiles}-${item.score}`}
                  title={undefined}
                  subtitle={item.reason}
                  meta={`${item.support_count} compound${item.support_count === 1 ? "" : "s"}`}
                  smiles={item.apply_core_smiles || item.core_smiles}
                  onZoom={onZoom}
                  onAdd={() => onAddCore(item)}
                  onShow={() => onShowCore(item)}
                  disabled={addDisabled}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
