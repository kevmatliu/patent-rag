import type { PropsWithChildren, ReactNode } from "react";

interface WorkspacePanelShellProps extends PropsWithChildren {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function WorkspacePanelShell({
  title,
  description,
  actions,
  className,
  bodyClassName,
  children
}: WorkspacePanelShellProps) {
  const panelClassName = ["workspace-panel-shell", className].filter(Boolean).join(" ");
  const panelBodyClassName = ["workspace-panel-body", bodyClassName].filter(Boolean).join(" ");

  return (
    <section className={panelClassName}>
      <header className="workspace-panel-header">
        <div>
          <p className="workspace-panel-eyebrow">Workspace Panel</p>
          <h2>{title}</h2>
          {description ? <p className="muted">{description}</p> : null}
        </div>
        {actions ? <div className="workspace-panel-actions">{actions}</div> : null}
      </header>
      <div className={panelBodyClassName}>{children}</div>
    </section>
  );
}
