import type { ReactNode } from "react";

interface CompoundExplorationLayoutProps {
  topRow: ReactNode;
  middleRow: ReactNode;
  bottomLeft: ReactNode;
  bottomRight: ReactNode;
}

export function CompoundExplorationLayout({
  topRow,
  middleRow,
  bottomLeft,
  bottomRight
}: CompoundExplorationLayoutProps) {
  return (
    <div className="compound-exploration-page">
      <div className="compound-exploration-row compound-exploration-row-top">{topRow}</div>
      <div className="compound-exploration-row compound-exploration-row-middle">{middleRow}</div>
      <div className="compound-exploration-workspace-row">
        <div className="compound-exploration-workspace-main">{bottomLeft}</div>
        <div className="compound-exploration-workspace-side">{bottomRight}</div>
      </div>
    </div>
  );
}
