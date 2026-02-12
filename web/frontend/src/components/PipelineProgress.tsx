import { useEffect, useState } from "react";
import { api } from "../api";
import type { JobStatus, PipelineStep } from "../types";

interface Props {
  jobId: string;
  onCompleted: (runId: string) => void;
  onBack: () => void;
}

function StepTracker({ steps }: { steps: PipelineStep[] }) {
  const completedCount = steps.filter((s) => s.status === "completed").length;
  const total = steps.length;
  const pct = total > 0 ? Math.round((completedCount / total) * 100) : 0;

  return (
    <div className="pipeline-steps">
      <div className="pipeline-progress-bar">
        <div className="pipeline-progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="pipeline-progress-label">
        {completedCount} / {total} steps ({pct}%)
      </span>

      <div className="pipeline-step-list">
        {steps.map((step, i) => (
          <div key={step.step_id} className={`pipeline-step ${step.status}`}>
            <div className="pipeline-step-icon">
              {step.status === "completed" && (
                <span className="step-check">✓</span>
              )}
              {step.status === "running" && <span className="step-spinner" />}
              {step.status === "pending" && (
                <span className="step-number">{i + 1}</span>
              )}
            </div>
            <span className="pipeline-step-name">{step.step_name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PipelineProgress({
  jobId,
  onCompleted,
  onBack,
}: Props) {
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    // Start polling immediately
    const poll = setInterval(async () => {
      try {
        const status = await api.getJobStatus(jobId);
        setJob(status);
        if (status.status === "completed") {
          clearInterval(poll);
          setTimeout(() => {
            if (status.run_id) onCompleted(status.run_id);
          }, 1200);
        } else if (status.status === "failed") {
          clearInterval(poll);
          setError(status.error ?? "Pipeline failed");
        }
      } catch {
        clearInterval(poll);
        setError("Lost connection to server");
      }
    }, 1000);

    return () => clearInterval(poll);
  }, [jobId, onCompleted]);

  return (
    <div className="pipeline-progress-view">
      <div className="pipeline-progress-header">
        <button className="back-btn" onClick={onBack}>
          ← Cancel
        </button>
        <h2>
          {job?.status === "completed"
            ? "Pipeline Complete"
            : "Running Pipeline..."}
        </h2>
        {job?.audio_filename && (
          <span className="pipeline-filename">{job.audio_filename}</span>
        )}
      </div>

      <div className="pipeline-progress-body">
        {job && job.steps.length > 0 ? (
          <StepTracker steps={job.steps} />
        ) : (
          <div className="center-message">
            <span className="step-spinner" /> Initializing pipeline...
          </div>
        )}

        {job?.status === "completed" && (
          <div className="pipeline-done-banner">
            ✓ Opening trace viewer...
          </div>
        )}

        {error && <div className="error-banner">{error}</div>}
      </div>
    </div>
  );
}
