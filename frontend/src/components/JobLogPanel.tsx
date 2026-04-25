import type { JobLogItem } from "../api/patents";

interface JobLogPanelProps {
  title: string;
  status: string | null;
  logs: JobLogItem[];
}

export function JobLogPanel({ title, status, logs }: JobLogPanelProps) {
  return (
    <section className="panel">
      <div className="job-log-header">
        <h2>{title}</h2>
        {status && <span className="badge">Job {status}</span>}
      </div>
      {logs.length === 0 ? (
        <p className="muted">No logs yet.</p>
      ) : (
        <div className="job-log-list">
          {logs.map((log) => (
            <article className={`job-log-item ${log.level === "error" ? "job-log-error" : ""}`} key={log.id}>
              <div className="job-log-time">{new Date(log.created_at).toLocaleTimeString()}</div>
              <div>{log.message}</div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
