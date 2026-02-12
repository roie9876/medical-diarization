import { useState } from "react";
import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";
import type { StepDetail } from "../types";

interface Props {
  currentStep: StepDetail;
  previousStep: StepDetail | null;
}

type ViewMode = "text" | "diff-split" | "diff-unified";

export default function StepContent({ currentStep, previousStep }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>(
    previousStep ? "diff-split" : "text",
  );

  return (
    <div className="step-content">
      {/* Header */}
      <div className="step-content-header">
        <div>
          <h2>{currentStep.step_name}</h2>
          {currentStep.chunk_index !== null && (
            <span className="badge">Chunk {currentStep.chunk_index + 1}</span>
          )}
          <span className="badge outline">
            {currentStep.line_count} lines · {currentStep.char_count.toLocaleString()} chars
          </span>
          {currentStep.duration_seconds > 0 && (
            <span className="badge outline">
              {currentStep.duration_seconds.toFixed(1)}s
            </span>
          )}
          {Object.keys(currentStep.metadata).length > 0 && (
            <span className="badge outline">
              {Object.entries(currentStep.metadata)
                .map(([k, v]) => `${k}: ${v}`)
                .join(" · ")}
            </span>
          )}
        </div>

        {/* View toggle */}
        <div className="view-toggle">
          <button
            className={viewMode === "text" ? "active" : ""}
            onClick={() => setViewMode("text")}
          >
            Text
          </button>
          {previousStep && (
            <>
              <button
                className={viewMode === "diff-split" ? "active" : ""}
                onClick={() => setViewMode("diff-split")}
              >
                Diff (Split)
              </button>
              <button
                className={viewMode === "diff-unified" ? "active" : ""}
                onClick={() => setViewMode("diff-unified")}
              >
                Diff (Unified)
              </button>
            </>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="step-content-body">
        {viewMode === "text" ? (
          <pre className="text-view" dir="rtl">
            {currentStep.text}
          </pre>
        ) : previousStep ? (
          <div className="diff-wrapper">
            <ReactDiffViewer
              oldValue={previousStep.text}
              newValue={currentStep.text}
              splitView={viewMode === "diff-split"}
              compareMethod={DiffMethod.WORDS}
              leftTitle={previousStep.step_name}
              rightTitle={currentStep.step_name}
              styles={{
                contentText: { direction: "rtl", fontFamily: "monospace", fontSize: "13px" },
                line: { direction: "rtl" },
              }}
            />
          </div>
        ) : (
          <pre className="text-view" dir="rtl">
            {currentStep.text}
          </pre>
        )}
      </div>
    </div>
  );
}
