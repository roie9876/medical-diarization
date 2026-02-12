import { useEffect, useState } from "react";
import { api } from "../api";
import type { TraceData } from "../types";
import StepSidebar from "./StepSidebar";
import StepContent from "./StepContent";
import AudioPlayer from "./AudioPlayer";

interface Props {
  runId: string;
  onBack: () => void;
  onRerun?: (jobId: string) => void;
}

export default function TraceViewer({ runId, onBack, onRerun }: Props) {
  const [trace, setTrace] = useState<TraceData | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rerunning, setRerunning] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .getTrace(runId)
      .then((data) => {
        setTrace(data);
        // Default to the first whole-file step (step_4) if it exists
        const firstWholeFile = data.steps.findIndex((s) => s.chunk_index === null);
        setSelectedIndex(firstWholeFile >= 0 ? firstWholeFile : 0);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [runId]);

  const handleRerun = async () => {
    setRerunning(true);
    try {
      const res = await api.rerunPipeline(runId);
      if (onRerun) onRerun(res.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Re-run failed");
      setRerunning(false);
    }
  };

  if (loading) return <div className="center-message">Loading trace...</div>;
  if (error) return <div className="center-message error">{error}</div>;
  if (!trace) return null;

  const currentStep = trace.steps[selectedIndex];

  // Find the "previous" step for diffing
  // For whole-file steps, previous = the prior whole-file step
  // For chunk steps, previous = the prior step of the same chunk
  let previousStep = null;
  if (selectedIndex > 0) {
    if (currentStep.chunk_index === null) {
      // Whole-file step → find the preceding whole-file step
      for (let i = selectedIndex - 1; i >= 0; i--) {
        if (trace.steps[i].chunk_index === null) {
          previousStep = trace.steps[i];
          break;
        }
      }
    } else {
      // Chunk step → find the preceding step of the same chunk
      for (let i = selectedIndex - 1; i >= 0; i--) {
        if (trace.steps[i].chunk_index === currentStep.chunk_index) {
          previousStep = trace.steps[i];
          break;
        }
      }
    }
  }

  return (
    <div className="trace-viewer">
      <div className="trace-header">
        <button className="back-btn" onClick={onBack}>
          ← Back
        </button>
        <h2>Run: {runId}</h2>
        <AudioPlayer runId={runId} />
        <button
          className="rerun-btn"
          onClick={handleRerun}
          disabled={rerunning}
          title="Re-run pipeline on the same audio file"
        >
          {rerunning ? "Starting..." : "⟳ Re-run"}
        </button>
        <span className="trace-meta">
          {trace.total_steps} steps · {trace.num_chunks} chunk(s) · {trace.created_at.slice(0, 19)}
        </span>
      </div>

      <div className="trace-body">
        <StepSidebar
          steps={trace.steps}
          selectedIndex={selectedIndex}
          onSelect={setSelectedIndex}
        />
        <StepContent currentStep={currentStep} previousStep={previousStep} />
      </div>
    </div>
  );
}
