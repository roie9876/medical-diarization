import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { api } from "../api";
import type { JobStatus, PipelineStep } from "../types";

interface Props {
  onCompleted: (runId: string) => void;
  onProcessing?: (jobId: string) => void;
}

function StepTracker({ steps, status }: { steps: PipelineStep[]; status: string }) {
  return (
    <div className="step-tracker">
      {steps.map((step, i) => (
        <div
          key={step.step_id}
          className={`step-tracker-item ${step.status}`}
        >
          <div className="step-tracker-indicator">
            {step.status === "completed" && <span className="step-check">✓</span>}
            {step.status === "running" && <span className="step-spinner" />}
            {step.status === "pending" && <span className="step-number">{i + 1}</span>}
          </div>
          <span className="step-tracker-label">{step.step_name}</span>
        </div>
      ))}
      {status === "completed" && (
        <div className="step-tracker-done">
          <span className="step-check">✓</span> Pipeline complete — opening trace...
        </div>
      )}
    </div>
  );
}

export default function UploadView({ onCompleted, onProcessing }: Props) {
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string>("");

  const startJob = useCallback(
    (jobId: string) => {
      // Poll for status
      const poll = setInterval(async () => {
        try {
          const status = await api.getJobStatus(jobId);
          setJob(status);
          if (status.status === "completed") {
            clearInterval(poll);
            // Brief delay so user can see "complete" state
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
    },
    [onCompleted],
  );

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;
      setError("");
      setJob(null);

      try {
        const { job_id } = await api.uploadAudio(acceptedFiles[0]);
        // Navigate to full-screen processing view
        if (onProcessing) {
          onProcessing(job_id);
        } else {
          setJob({
            job_id,
            status: "pending",
            progress: "Uploaded, starting...",
            steps: [],
          });
          startJob(job_id);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
      }
    },
    [startJob],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "audio/*": [".mp3", ".wav", ".m4a", ".flac", ".ogg"],
    },
    maxFiles: 1,
  });

  const isProcessing = job && (job.status === "running" || job.status === "pending");

  return (
    <div className="upload-view">
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? "active" : ""} ${isProcessing ? "disabled" : ""}`}
      >
        <input {...getInputProps()} />
        <div className="dropzone-content">
          <span className="dropzone-icon">🎙️</span>
          {isDragActive ? (
            <p>Drop the audio file here...</p>
          ) : isProcessing ? (
            <p>Processing {job?.audio_filename ?? "audio"}...</p>
          ) : (
            <>
              <p>Drag & drop an audio file here</p>
              <p className="subtle">or click to browse (MP3, WAV, M4A, FLAC)</p>
            </>
          )}
        </div>
      </div>

      {job && job.steps.length > 0 && (
        <StepTracker steps={job.steps} status={job.status} />
      )}

      {job && job.steps.length === 0 && job.status === "pending" && (
        <div className="job-status pending">
          <div className="job-status-header">
            <span className="status-dot" />
            <strong>Queued</strong>
          </div>
          {job.progress && <p>{job.progress}</p>}
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}
    </div>
  );
}
