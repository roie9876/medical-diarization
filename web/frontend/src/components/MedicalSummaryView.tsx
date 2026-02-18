import { useEffect, useState } from "react";
import { api } from "../api";
import type { MedicalSummaryData } from "../types";
import ExportPdf from "./ExportPdf";

interface Props {
  runId: string;
}

/** Section header mapping — icons + display names */
const SECTION_META: Record<string, { icon: string; label: string }> = {
  "רקע דמוגרפי": { icon: "👤", label: "רקע דמוגרפי" },
  "רקע רפואי": { icon: "📋", label: "רקע רפואי" },
  "תלונה עיקרית": { icon: "🎯", label: "תלונה עיקרית" },
  "פרטי המחלה הנוכחית": { icon: "📝", label: "פרטי המחלה הנוכחית" },
  "בדיקה גופנית": { icon: "🩺", label: "בדיקה גופנית" },
  "תוצאות מעבדה": { icon: "🧪", label: "תוצאות מעבדה" },
  "דימות ובדיקות עזר": { icon: "📸", label: "דימות ובדיקות עזר" },
  "סיכום רפואי של הרופא": { icon: "👨‍⚕️", label: "סיכום רפואי של הרופא" },
  "המלצות": { icon: "💊", label: "המלצות" },
  "מרשמים": { icon: "📄", label: "מרשמים" },
  "אזהרות בקרת איכות": { icon: "⚠️", label: "אזהרות בקרת איכות" },
};

interface ParsedSection {
  title: string;
  icon: string;
  lines: string[];
}

/** Parse the raw summary text into structured sections */
function parseSummary(text: string): ParsedSection[] {
  const sections: ParsedSection[] = [];
  let current: ParsedSection | null = null;

  for (const line of text.split("\n")) {
    const trimmed = line.trim();

    // Section header: ---סיכום רפואי--- or ---רקע דמוגרפי---
    const headerMatch = trimmed.match(/^---(.+?)---$/);
    if (headerMatch) {
      const title = headerMatch[1].trim();
      const meta = SECTION_META[title] || { icon: "📌", label: title };
      current = { title: meta.label, icon: meta.icon, lines: [] };
      sections.push(current);
      continue;
    }

    // Skip empty lines at the start of a section
    if (current && (trimmed || current.lines.length > 0)) {
      current.lines.push(line);
    }
  }

  // Trim trailing empty lines from each section
  for (const s of sections) {
    while (s.lines.length && !s.lines[s.lines.length - 1].trim()) {
      s.lines.pop();
    }
  }

  return sections;
}

/** Format a single content line — highlight bullet points, labels, warnings */
function formatLine(line: string, idx: number) {
  const trimmed = line.trim();
  if (!trimmed) return null;

  // Warning line
  if (trimmed.startsWith("⚠️") || trimmed.startsWith("• ⚠️")) {
    return (
      <div key={idx} className="summary-line summary-warning">
        <span className="warning-icon">⚠️</span>
        <span>{trimmed.replace(/^•?\s*⚠️\s*/, "")}</span>
      </div>
    );
  }

  // Bullet with label: "• גיל: 79"
  const bulletLabelMatch = trimmed.match(/^•\s*(.+?):\s*(.+)$/);
  if (bulletLabelMatch) {
    const isNotSpecified = bulletLabelMatch[2].trim() === "לא צוין";
    return (
      <div key={idx} className="summary-line summary-bullet">
        <span className="bullet-label">{bulletLabelMatch[1]}:</span>
        <span className={`bullet-value ${isNotSpecified ? "not-specified" : ""}`}>
          {bulletLabelMatch[2]}
        </span>
      </div>
    );
  }

  // Simple bullet: "• המשך טיפול תרופתי"
  if (trimmed.startsWith("•")) {
    return (
      <div key={idx} className="summary-line summary-bullet">
        <span className="bullet-dot" />
        <span>{trimmed.slice(1).trim()}</span>
      </div>
    );
  }

  // Numbered item: "1. שם התרופה: Cipralex"
  const numberedMatch = trimmed.match(/^(\d+)\.\s*(.+)$/);
  if (numberedMatch) {
    return (
      <div key={idx} className="summary-line summary-numbered">
        <span className="numbered-badge">{numberedMatch[1]}</span>
        <span>{numberedMatch[2]}</span>
      </div>
    );
  }

  // Medication line (indented under תרופות כרוניות) — plain name
  if (trimmed && !trimmed.startsWith("•") && !trimmed.startsWith("---")) {
    // Check if it looks like a medication (starts with uppercase or Hebrew)
    return (
      <div key={idx} className="summary-line summary-text">
        {trimmed}
      </div>
    );
  }

  return null;
}

export default function MedicalSummaryView({ runId }: Props) {
  const [data, setData] = useState<MedicalSummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    api
      .getMedicalSummary(runId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) {
    return (
      <div className="medical-summary-view">
        <div className="summary-loading">
          <div className="synced-spinner" />
          <p>טוען סיכום רפואי...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="medical-summary-view">
        <div className="summary-empty">
          <span className="summary-empty-icon">📋</span>
          <p>אין סיכום רפואי לריצה זו</p>
          <p className="subtle">הסיכום הרפואי זמין רק לריצות שכוללות את שלב 6</p>
        </div>
      </div>
    );
  }

  if (!data?.summary) return null;

  const sections = parseSummary(data.summary);
  const report = data.report;
  const isWarningSection = (title: string) => title === "אזהרות בקרת איכות";

  return (
    <div className="medical-summary-view">
      {/* Export button */}
      {data?.summary && (
        <div className="summary-export-bar">
          <ExportPdf
            summaryText={data.summary}
            runId={runId}
            faithfulnessScore={report?.faithfulness_score}
            validationPassed={report?.validation_passed}
          />
        </div>
      )}

      {/* Validation banner */}
      {report && (
        <div className={`summary-validation-banner ${report.validation_passed ? "passed" : "failed"}`}>
          <div className="validation-score">
            <span className="score-value">{report.faithfulness_score ?? "—"}</span>
            <span className="score-label">/ 10</span>
          </div>
          <div className="validation-details">
            <span className="validation-title">
              {report.validation_passed ? "✅ ולידציה עברה בהצלחה" : "⚠️ נמצאו בעיות"}
            </span>
            <div className="validation-chips">
              {(report.hallucinated_medications?.length ?? 0) > 0 && (
                <span className="chip chip-error">
                  💊 {report.hallucinated_medications!.length} תרופות חשודות
                </span>
              )}
              {(report.deterministic_duplicate_groups?.length ?? 0) > 0 && (
                <span className="chip chip-warning">
                  🔄 {report.deterministic_duplicate_groups!.length} כפילויות
                </span>
              )}
              {(report.deterministic_dosage_warnings?.length ?? 0) > 0 && (
                <span className="chip chip-warning">
                  💉 {report.deterministic_dosage_warnings!.length} אזהרות מינון
                </span>
              )}
              {(report.fabricated_info?.length ?? 0) > 0 && (
                <span className="chip chip-error">
                  🚫 {report.fabricated_info!.length} מידע בדוי
                </span>
              )}
              {report.chief_complaint_ok && (
                <span className="chip chip-success">🎯 תלונה עיקרית תקינה</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Sections */}
      <div className="summary-sections">
        {sections.map((section, si) => (
          <div
            key={si}
            className={`summary-section ${isWarningSection(section.title) ? "warning-section" : ""}`}
          >
            <div className="section-header">
              <span className="section-icon">{section.icon}</span>
              <h3 className="section-title">{section.title}</h3>
            </div>
            <div className="section-body">
              {section.lines.map((line, li) => formatLine(line, li))}
              {section.lines.every((l) => !l.trim()) && (
                <div className="summary-line not-specified">לא צוין</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
