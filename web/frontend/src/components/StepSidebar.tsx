import type { StepDetail } from "../types";

interface Props {
  steps: StepDetail[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

/** Colour-code step IDs for visual grouping */
function stepColor(stepId: string): string {
  if (stepId.startsWith("step_1")) return "#4ea8de";
  if (stepId.startsWith("step_2")) return "#48bfe3";
  if (stepId.startsWith("step_3")) return "#56cfe1";
  if (stepId.startsWith("step_4")) return "#64dfdf";
  if (stepId.startsWith("step_5a")) return "#f9c74f";
  if (stepId.startsWith("step_5b")) return "#f9844a";
  if (stepId.startsWith("step_5c")) return "#f3722c";
  if (stepId.startsWith("step_5d")) return "#f94144";
  if (stepId.startsWith("step_5e")) return "#90be6d";
  return "#999";
}

function formatChunk(chunkIndex: number | null): string {
  if (chunkIndex === null) return "";
  return ` (chunk ${chunkIndex + 1})`;
}

export default function StepSidebar({ steps, selectedIndex, onSelect }: Props) {
  return (
    <aside className="step-sidebar">
      <h3>Pipeline Steps</h3>
      <ul>
        {steps.map((step, i) => (
          <li
            key={i}
            className={`step-item ${i === selectedIndex ? "selected" : ""}`}
            onClick={() => onSelect(i)}
          >
            <span
              className="step-dot"
              style={{ backgroundColor: stepColor(step.step_id) }}
            />
            <div className="step-info">
              <span className="step-name">
                {step.step_name}
                {formatChunk(step.chunk_index)}
              </span>
              <span className="step-meta">
                {step.line_count} lines · {step.char_count.toLocaleString()} chars
                {step.duration_seconds > 0 && ` · ${step.duration_seconds.toFixed(1)}s`}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}
