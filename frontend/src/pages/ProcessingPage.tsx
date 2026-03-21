import { useEffect, useState } from "react";
import {
  cancelJob,
  getJobStatus,
  getUnprocessedCount,
  type JobLogItem,
  processImages,
  type ProcessImagesResponse
} from "../api/patents";
import { JobLogPanel } from "../components/JobLogPanel";

export function ProcessingPage() {
  const [count, setCount] = useState<number | null>(null);
  const [limit, setLimit] = useState(10);
  const [order, setOrder] = useState<"oldest" | "newest">("oldest");
  const [patentCodesText, setPatentCodesText] = useState("");
  const [summary, setSummary] = useState<ProcessImagesResponse | null>(null);
  const [logs, setLogs] = useState<JobLogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);

  const refreshCount = async () => {
    try {
      const response = await getUnprocessedCount();
      setCount(response.count);
    } catch (countError) {
      setError(countError instanceof Error ? countError.message : "Failed to load count");
    }
  };

  useEffect(() => {
    void refreshCount();
  }, []);

  useEffect(() => {
    if (!jobId) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    const poll = async () => {
      try {
        const response = await getJobStatus(jobId);
        if (cancelled) {
          return;
        }

        setLogs(response.logs);
        setJobStatus(response.status);
        if (response.summary && "processed_count" in response.summary) {
          setSummary(response.summary);
        }

        if (response.status === "completed" || response.status === "failed" || response.status === "cancelled") {
          setLoading(false);
          await refreshCount();
          if (response.status === "failed" && response.error) {
            setError(response.error);
          }
          return;
        }

        timeoutId = window.setTimeout(() => {
          void poll();
        }, 250);
      } catch (pollError) {
        if (!cancelled) {
          setLoading(false);
          setError(pollError instanceof Error ? pollError.message : "Failed to load job status");
        }
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [jobId]);

  const handleProcess = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setSummary(null);
    setLogs([]);
    setJobStatus("pending");

    try {
      const patentCodes = patentCodesText
        .split(/[\n,\s]+/)
        .map((value) => value.trim())
        .filter(Boolean);
      const response = await processImages(limit, order, patentCodes);
      setJobId(response.job_id);
      setJobStatus(response.status);
    } catch (processError) {
      setError(processError instanceof Error ? processError.message : "Image processing failed");
      setJobStatus("failed");
      setLoading(false);
    }
  };

  const handleStop = async () => {
    if (!jobId) {
      return;
    }
    try {
      const response = await cancelJob(jobId);
      setJobStatus(response.status);
    } catch (stopError) {
      setError(stopError instanceof Error ? stopError.message : "Failed to stop processing");
    }
  };

  return (
    <>
      <section className="panel">
        <h2>Queue status</h2>
        <p className="muted">
          Unprocessed images: <strong>{count ?? "..."}</strong>
        </p>
      </section>

      <section className="panel">
        <form className="grid two" onSubmit={handleProcess}>
          <div className="field">
            <label htmlFor="limit">Batch size</label>
            <input
              id="limit"
              type="number"
              min={1}
              max={1000}
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
            />
          </div>
          <div className="field">
            <label htmlFor="order">Order</label>
            <select
              id="order"
              value={order}
              onChange={(event) => setOrder(event.target.value as "oldest" | "newest")}
            >
              <option value="oldest">Oldest first</option>
              <option value="newest">Newest first</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="patent-codes">Patent codes (optional)</label>
            <textarea
              id="patent-codes"
              rows={5}
              placeholder="WO2025015269A1&#10;US20250042916A1"
              value={patentCodesText}
              onChange={(event) => setPatentCodesText(event.target.value)}
            />
          </div>
          <div>
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? "Processing..." : "Run processing"}
            </button>
            {loading && (
              <button className="secondary-button" type="button" onClick={handleStop}>
                Stop processing
              </button>
            )}
          </div>
        </form>
        {error && <p className="status-error">{error}</p>}
      </section>

      <section className="panel">
        <h2>Last run</h2>
        {!summary ? (
          <p className="muted">No processing run yet.</p>
        ) : (
          <div className="result-list">
            <article className="result-card">
              <div className="badge-row">
                <span className="badge">Processed {summary.processed_count}</span>
                <span className="badge">Failed {summary.failed_count}</span>
                {summary.stopped_early && <span className="badge">Stopped early</span>}
              </div>
              <p className="muted">
                Processed image IDs: {summary.processed_image_ids.length > 0 ? summary.processed_image_ids.join(", ") : "none"}
              </p>
              {summary.failures.length > 0 && (
                <div>
                  <p>
                    <strong>Failures</strong>
                  </p>
                  {summary.failures.map((failure) => (
                    <p className="status-error" key={failure.image_id}>
                      #{failure.image_id}: {failure.error}
                    </p>
                  ))}
                </div>
              )}
            </article>
          </div>
        )}
      </section>

      <JobLogPanel title="Processing Logs" status={jobStatus} logs={logs} />
    </>
  );
}
