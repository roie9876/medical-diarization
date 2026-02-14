import { useEffect, useState } from "react";
import { api } from "../api";
import type { RunSummary } from "../types";

interface Props {
  onSelectRun: (runId: string) => void;
  onRerun?: (jobId: string) => void;
}

export default function RunList({ onSelectRun, onRerun }: Props) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [rerunningId, setRerunningId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    api
      .listRuns()
      .then(setRuns)
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, []);

  const handleRerun = async (runId: string) => {
    setRerunningId(runId);
    try {
      const res = await api.rerunPipeline(runId);
      if (onRerun) onRerun(res.job_id);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Re-run failed");
      setRerunningId(null);
    }
  };

  const handleDelete = async (runId: string) => {
    if (!confirm(`Delete run ${runId}? This cannot be undone.`)) return;
    setDeletingId(runId);
    try {
      await api.deleteRun(runId);
      setRuns((prev) => prev.filter((r) => r.run_id !== runId));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) return <div className="center-message">Loading runs...</div>;

  if (runs.length === 0) {
    return (
      <div className="empty-state">
        <p>No pipeline runs found.</p>
        <p className="subtle">Upload an audio file to create your first trace.</p>
      </div>
    );
  }

  return (
    <div className="run-list">
      <h3>Previous Runs</h3>
      <table>
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Date</th>
            <th>Steps</th>
            <th>Chunks</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.run_id}>
              <td className="mono">
                {run.run_id}
                {run.audio_filename && (
                  <span className="run-audio-name"> — {run.audio_filename}</span>
                )}
              </td>
              <td>{run.created_at.slice(0, 19).replace("T", " ")}</td>
              <td>{run.num_steps}</td>
              <td>{run.num_chunks}</td>
              <td className="run-actions">
                <button className="view-btn" onClick={() => onSelectRun(run.run_id)}>
                  View Trace →
                </button>
                {run.has_audio && (
                  <button
                    className="rerun-btn-small"
                    onClick={() => handleRerun(run.run_id)}
                    disabled={rerunningId === run.run_id}
                    title="Re-run pipeline on the same audio"
                  >
                    {rerunningId === run.run_id ? "..." : "⟳"}
                  </button>
                )}
                <button
                  className="delete-btn-small"
                  onClick={() => handleDelete(run.run_id)}
                  disabled={deletingId === run.run_id}
                  title="Delete this run"
                >
                  {deletingId === run.run_id ? "..." : "✕"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
