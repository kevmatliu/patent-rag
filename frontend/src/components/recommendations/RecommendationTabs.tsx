export type RecommendationTabId = "rgroup-recommendations" | "similar-cores";

interface RecommendationTabsProps {
  activeTab: RecommendationTabId;
  onChange: (tab: RecommendationTabId) => void;
}

const TABS: Array<{ id: RecommendationTabId; label: string }> = [
  { id: "rgroup-recommendations", label: "R-group Recommendations" },
  { id: "similar-cores", label: "Similar Cores" }
];

export function RecommendationTabs({ activeTab, onChange }: RecommendationTabsProps) {
  return (
    <div className="recommendation-tab-row recommendation-tab-row-workspace" role="tablist" aria-label="Recommendation tabs">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={activeTab === tab.id}
          className={activeTab === tab.id ? "active" : ""}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
