import { useState, useRef } from "react";
import type { StepDetail } from "../types";

interface Props {
  steps: StepDetail[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

/* ── Hebrew step explanations with examples ─────────────────────────── */

interface StepTooltip {
  title: string;
  desc: string;
  example?: string;
}

const STEP_TOOLTIPS: Record<string, StepTooltip> = {
  step_0: {
    title: "חלוקת אודיו לקטעים",
    desc: "מפצל את הקובץ לקטעים של 4 דקות עם חפיפה של 30 שניות, כדי לעבד כל קטע בנפרד.",
    example: "קובץ של 20 דקות → 6 קטעים עם חפיפה",
  },
  step_1: {
    title: "תמלול טהור (GPT-Audio)",
    desc: "תמלול מילה-במילה בלי זיהוי דוברים. מתמקד בדיוק הטקסט — שמות תרופות, מספרים, מונחים רפואיים באנגלית.",
    example: '...לוקח אקמול 500 מ"ג פעמיים ביום, ויש לו DVT...',
  },
  step_2: {
    title: "תמלול עם זיהוי דוברים (GPT-Audio)",
    desc: "תמלול עם תיוג של מי אמר מה. הטקסט פחות מדויק, אבל זיהוי הדוברים טוב יותר.",
    example: "[דובר 1]: מה הסיבה שהגעת?\n[דובר 2]: כאבים בחזה כבר שבוע.",
  },
  step_3: {
    title: "מיזוג חכם (GPT-5.2)",
    desc: "ממזג את שני התמלולים: לוקח את הטקסט המדויק משלב 1 ואת זיהוי הדוברים משלב 2. ממפה דוברים לתפקידים.",
    example: "[דובר 1] → [רופא]\n[דובר 2] → [מטופל]",
  },
  step_4: {
    title: "איחוד קטעים",
    desc: "מאחד את כל הקטעים בחזרה לטקסט אחד. משתמש בחפיפה של 30 השניות כדי למצוא את נקודת החיבור ולמנוע כפילויות.",
    example: "סוף קטע 1: \"...קח את האקמול\"\nתחילת קטע 2: \"קח את האקמול ותחזור...\" → מחובר",
  },
  step_5a: {
    title: "נרמול (דטרמיניסטי)",
    desc: "תיקוני עיצוב אוטומטיים — בלי LLM. מוסיף נקודתיים אחרי תגית דובר, מכווץ רווחים, מתקן סימני פיסוק, מתקן שמות מונחים.",
    example: "[רופא] טקסט → [רופא]: טקסט\nPET CT → PET-CT\ntee → TEE",
  },
  step_5b: {
    title: "תיקון איות (מילון)",
    desc: "מחליף שגיאות כתיב ידועות של GPT בעברית רפואית. רק התאמות מדויקות — ללא ניחושים.",
    example: "עזות → הזעות\nעקומול → אקמול\nמולטאק → Multaq\nבכום הלב → בקרום הלב",
  },
  step_5c: {
    title: "הסרת כפילויות",
    desc: "מזהה ומסיר שורות כפולות שנוצרו בתמלול או באיחוד הקטעים. בודק כפילויות מדויקות וגם כפילויות עם דמיון מעל 85%.",
    example: "[רופא]: מה שלומך?\n[רופא]: מה שלומך? ← מוסר",
  },
  step_5d: {
    title: "תיקון סמנטי (LLM מוגבל)",
    desc: "GPT-5.2 מתקן דקדוק עברי ומילים שבורות. אסור לו להמציא, לקצר, או לשנות מספרים ומונחים רפואיים.",
    example: "\"היא אומר שהיא לא מרגיש טוב\"\n→ \"היא אומרת שהיא לא מרגישה טוב\"",
  },
  step_5e: {
    title: "אימות סופי (דטרמיניסטי)",
    desc: "בודק שכל המספרים והמונחים הרפואיים נשמרו אחרי העיבוד. מזהה הזיות — מונחים חדשים שלא היו במקור.",
    example: "37.3 נמצא בקלט ✓\nDVT נמצא בקלט ✓\nMRI לא היה במקור ⚠️ הזיה אפשרית",
  },
  step_6a: {
    title: "יצירת סיכום רפואי (GPT-5.2)",
    desc: "מייצר סיכום רפואי מובנה בעברית מתוך התמלול. כולל: רקע, תלונה עיקרית, בדיקות, המלצות ומרשמים. לא ממציא — שדה חסר מסומן \"לא צוין\".",
    example: "תלונה עיקרית: כאבים בחזה\nרקע: יל\"ד, סוכרת סוג 2\nתרופות: Ramipril 5mg, Metformin 1000mg",
  },
  step_6b: {
    title: "אימות סיכום רפואי",
    desc: "בדיקה כפולה — דטרמיניסטית + LLM. מזהה תרופות כפולות (שם מסחרי = גנרי), מינונים חשודים, ומידע שהומצא.",
    example: "Ramipril + Tritace = כפילות ⚠️\nRamipril 25mg → מינון חשוד (טווח: 1.25-10mg) ⚠️",
  },
};

/** Find tooltip for a step ID */
function getTooltip(stepId: string): StepTooltip | null {
  // Try exact prefix match (most specific first)
  const prefixes = Object.keys(STEP_TOOLTIPS).sort((a, b) => b.length - a.length);
  for (const prefix of prefixes) {
    if (stepId.startsWith(prefix)) return STEP_TOOLTIPS[prefix];
  }
  return null;
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

/* ── Tooltip component ──────────────────────────────────────────────── */

function StepTooltipPopup({ tooltip, anchorEl }: { tooltip: StepTooltip; anchorEl: HTMLElement | null }) {
  if (!anchorEl) return null;

  // Position tooltip to the right of the sidebar
  const rect = anchorEl.getBoundingClientRect();

  return (
    <div
      className="step-tooltip"
      style={{
        top: Math.min(rect.top, window.innerHeight - 220),
        left: rect.right + 8,
      }}
    >
      <div className="step-tooltip-title">{tooltip.title}</div>
      <div className="step-tooltip-desc">{tooltip.desc}</div>
      {tooltip.example && (
        <div className="step-tooltip-example">
          <span className="step-tooltip-example-label">דוגמה:</span>
          <pre>{tooltip.example}</pre>
        </div>
      )}
    </div>
  );
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

  // Tooltip hover state
  const [hoveredStep, setHoveredStep] = useState<{ tooltip: StepTooltip; el: HTMLElement } | null>(null);
  const hoverTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseEnter = (stepId: string, el: HTMLElement) => {
    if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    hoverTimeout.current = setTimeout(() => {
      const tip = getTooltip(stepId);
      if (tip) setHoveredStep({ tooltip: tip, el });
    }, 400); // 400ms delay to avoid flickering
  };

  const handleMouseLeave = () => {
    if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    setHoveredStep(null);
  };

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
                      onMouseEnter={(e) => handleMouseEnter(step.step_id, e.currentTarget)}
                      onMouseLeave={handleMouseLeave}
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

      {/* Tooltip popup */}
      {hoveredStep && (
        <StepTooltipPopup tooltip={hoveredStep.tooltip} anchorEl={hoveredStep.el} />
      )}
    </aside>
  );
}
