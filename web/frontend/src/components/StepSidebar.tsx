import { useState } from "react";
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
  if (stepId.startsWith("step_6a")) return "#c77dff";
  if (stepId.startsWith("step_6b")) return "#9d4edd";
  return "#999";
}

/** Determine which group a step belongs to */
function stepGroup(step: StepDetail): string {
  const id = step.step_id;
  if (id.startsWith("step_0")) return "chunking";
  if (
    id.startsWith("step_1") ||
    id.startsWith("step_2") ||
    id.startsWith("step_3")
  ) {
    return step.chunk_index !== null ? "chunks" : "transcription";
  }
  if (id.startsWith("step_4")) return "merging";
  if (id.startsWith("step_5")) return "postprocess";
  if (id.startsWith("step_6")) return "summary";
  return "other";
}

interface GroupDef {
  key: string;
  label: string;
  icon: string;
  color: string;
}

const GROUP_DEFS: GroupDef[] = [
  { key: "chunking", label: "Audio Chunking", icon: "✂️", color: "#999" },
  { key: "chunks", label: "Per-Chunk Transcription", icon: "🎙️", color: "#4ea8de" },
  { key: "transcription", label: "Transcription", icon: "🎙️", color: "#4ea8de" },
  { key: "merging", label: "Chunk Merging", icon: "🔗", color: "#64dfdf" },
  { key: "postprocess", label: "Post-Processing", icon: "🔧", color: "#f9844a" },
  { key: "summary", label: "Medical Summary", icon: "📋", color: "#c77dff" },
  { key: "other", label: "Other", icon: "📌", color: "#999" },
];

interface GroupedSteps {
  group: GroupDef;
  items: { step: StepDetail; globalIndex: number }[];
}

function groupSteps(steps: StepDetail[]): GroupedSteps[] {
  const groups: GroupedSteps[] = [];
  const groupMap = new Map<string, GroupedSteps>();

  for (let i = 0; i < steps.length; i++) {
    const key = stepGroup(steps[i]);
    if (!groupMap.has(key)) {
      const def = GROUP_DEFS.find((g) => g.key === key) ||
        GROUP_DEFS[GROUP_DEFS.length - 1];
      const grouped: GroupedSteps = { group: def, items: [] };
      groupMap.set(key, grouped);
      groups.push(grouped);
    }
    groupMap.get(key)!.items.push({ step: steps[i], globalIndex: i });
  }

  return groups;
}

function formatChunk(chunkIndex: number | null): string {
  if (chunkIndex === null) return "";
  return ` (chunk ${chunkIndex + 1})`;
}

export default function StepSidebar({ steps, selectedIndex, onSelect }: Props) {
  const grouped = groupSteps(steps);

  // Which groups are collapsed — start with "chunks" collapsed if there are many
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    for (const g of grouped) {
      if (g.group.key === "chunks" && g.items.length > 6) {
        initial.add("chunks");
      }
    }
    return initial;
  });

  const toggleGroup = (key: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Check if the selected step is in a group
  const selectedGroup = steps[selectedIndex]
    ? stepGroup(steps[selectedIndex])
    : "";

  return (
    <aside className="step-sidebar">
      <h3>Pipeline Steps</h3>
      <div className="step-groups">
        {grouped.map((g) => {
          const isCollapsed = collapsed.has(g.group.key);
          const hasSelected = g.items.some((it) => it.globalIndex === selectedIndex);
          const selectedInGroup = selectedGroup === g.group.key;

          return (
            <div
              key={g.group.key}
              className={`step-group ${hasSelected ? "has-selected" : ""}`}
            >
              <div
                className="step-group-header"
                onClick={() => toggleGroup(g.group.key)}
              >
                <span className="group-chevron">{isCollapsed ? "▸" : "▾"}</span>
                <span
                  className="group-bar"
                  style={{ backgroundColor: g.group.color }}
                />
                <span className="group-icon">{g.group.icon}</span>
                <span className="group-label">{g.group.label}</span>
                <span className="group-count">{g.items.length}</span>
                {isCollapsed && selectedInGroup && (
                  <span className="group-active-dot" />
                )}
              </div>

              {!isCollapsed && (
                <ul className="step-group-items">
                  {g.items.map(({ step, globalIndex }) => (
                    <li
                      key={globalIndex}
                      className={`step-item ${globalIndex === selectedIndex ? "selected" : ""}`}
                      onClick={() => onSelect(globalIndex)}
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
                          {step.line_count} lines ·{" "}
                          {step.char_count.toLocaleString()} chars
                          {step.duration_seconds > 0 &&
                            ` · ${step.duration_seconds.toFixed(1)}s`}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
