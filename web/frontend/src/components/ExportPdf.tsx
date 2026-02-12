import { useState } from "react";

interface Props {
  summaryText: string;
  runId: string;
  faithfulnessScore?: number;
  validationPassed?: boolean;
}

/**
 * Professional medical summary PDF export.
 * Renders a hidden print-ready document and converts it to PDF using html2pdf.js.
 */
export default function ExportPdf({
  summaryText,
  runId,
  faithfulnessScore,
  validationPassed,
}: Props) {
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);

    try {
      // Dynamic import to avoid bundling issues
      const html2pdf = (await import("html2pdf.js")).default;

      const now = new Date();
      const dateStr = now.toLocaleDateString("he-IL", {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
      const timeStr = now.toLocaleTimeString("he-IL", {
        hour: "2-digit",
        minute: "2-digit",
      });

      // Build the professional PDF HTML
      const html = buildPdfHtml(summaryText, runId, dateStr, timeStr, faithfulnessScore, validationPassed);

      // Create a temporary container
      const tempDiv = document.createElement("div");
      tempDiv.innerHTML = html;
      document.body.appendChild(tempDiv);

      const filename = `medical_summary_${runId}_${now.toISOString().slice(0, 10)}.pdf`;

      await html2pdf()
        .set({
          margin: [10, 12, 15, 12], // top, left, bottom, right (mm)
          filename,
          image: { type: "jpeg", quality: 0.98 },
          html2canvas: {
            scale: 2,
            useCORS: true,
            letterRendering: true,
          },
          jsPDF: {
            unit: "mm",
            format: "a4",
            orientation: "portrait",
          },
          pagebreak: { mode: ["avoid-all", "css", "legacy"] },
        })
        .from(tempDiv.firstElementChild)
        .save();

      document.body.removeChild(tempDiv);
    } catch (err) {
      console.error("PDF export failed:", err);
      alert("שגיאה בייצוא PDF");
    } finally {
      setExporting(false);
    }
  };

  return (
    <button
      className="export-pdf-btn"
      onClick={handleExport}
      disabled={exporting}
      title="ייצוא סיכום רפואי כ-PDF"
    >
      {exporting ? (
        <>
          <span className="export-spinner" /> מייצא...
        </>
      ) : (
        <>📄 ייצוא PDF</>
      )}
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Build the print-ready HTML for the PDF
// ─────────────────────────────────────────────────────────────────────────────

function buildPdfHtml(
  summaryText: string,
  runId: string,
  dateStr: string,
  timeStr: string,
  faithfulnessScore?: number,
  validationPassed?: boolean,
): string {
  // Parse sections from raw text
  const sections = parseSections(summaryText);

  const sectionIcons: Record<string, string> = {
    "רקע דמוגרפי": "👤",
    "רקע רפואי": "📋",
    "תלונה עיקרית": "🎯",
    "פרטי המחלה הנוכחית": "📝",
    "בדיקה גופנית": "🩺",
    "תוצאות מעבדה": "🧪",
    "דימות ובדיקות עזר": "📸",
    "סיכום רפואי של הרופא": "👨‍⚕️",
    "המלצות": "💊",
    "מרשמים": "📄",
    "אזהרות בקרת איכות": "⚠️",
  };

  const sectionsHtml = sections
    .map((s) => {
      const icon = sectionIcons[s.title] || "📌";
      const isWarning = s.title === "אזהרות בקרת איכות";
      const linesHtml = s.lines
        .filter((l) => l.trim())
        .map((line) => formatPdfLine(line, isWarning))
        .join("");

      return `
        <div class="pdf-section ${isWarning ? "pdf-warning-section" : ""}" style="page-break-inside: avoid;">
          <div class="pdf-section-header">
            <span class="pdf-section-icon">${icon}</span>
            <span class="pdf-section-title">${s.title}</span>
          </div>
          <div class="pdf-section-body">
            ${linesHtml || '<div class="pdf-not-specified">לא צוין</div>'}
          </div>
        </div>
      `;
    })
    .join("");

  const validationHtml =
    faithfulnessScore !== undefined
      ? `
    <div class="pdf-validation-bar">
      <span class="pdf-validation-icon">${validationPassed ? "✅" : "⚠️"}</span>
      <span class="pdf-validation-text">
        ציון נאמנות: <strong>${faithfulnessScore}/10</strong>
        &nbsp;|&nbsp;
        ${validationPassed ? "ולידציה עברה בהצלחה" : "נמצאו בעיות — יש לבדוק"}
      </span>
    </div>
  `
      : "";

  return `
    <div class="pdf-document" dir="rtl" style="
      font-family: 'David', 'Noto Sans Hebrew', 'Arial', sans-serif;
      color: #1a1a2e;
      background: #fff;
      padding: 0;
      width: 100%;
      line-height: 1.65;
      font-size: 13px;
    ">
      <style>
        .pdf-document * { box-sizing: border-box; }

        .pdf-header {
          text-align: center;
          border-bottom: 3px solid #1a5276;
          padding-bottom: 14px;
          margin-bottom: 16px;
        }
        .pdf-header-title {
          font-size: 24px;
          font-weight: 700;
          color: #1a5276;
          margin: 0 0 4px 0;
          letter-spacing: 1px;
        }
        .pdf-header-subtitle {
          font-size: 13px;
          color: #555;
          margin: 0;
        }
        .pdf-header-meta {
          margin-top: 8px;
          font-size: 11px;
          color: #777;
        }

        .pdf-validation-bar {
          display: flex;
          align-items: center;
          gap: 8px;
          background: ${validationPassed ? "#e8f5e9" : "#fff3e0"};
          border: 1px solid ${validationPassed ? "#a5d6a7" : "#ffcc80"};
          border-radius: 6px;
          padding: 8px 14px;
          margin-bottom: 16px;
          font-size: 12px;
        }
        .pdf-validation-icon { font-size: 16px; }
        .pdf-validation-text { color: #333; }

        .pdf-section {
          margin-bottom: 14px;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          overflow: hidden;
        }
        .pdf-warning-section {
          border-color: #f4a460;
          background: #fffbf0;
        }
        .pdf-section-header {
          display: flex;
          align-items: center;
          gap: 8px;
          background: #f0f4f8;
          padding: 8px 14px;
          border-bottom: 1px solid #e0e0e0;
        }
        .pdf-warning-section .pdf-section-header {
          background: #fff3e0;
          border-bottom-color: #f4a460;
        }
        .pdf-section-icon { font-size: 16px; }
        .pdf-section-title {
          font-size: 15px;
          font-weight: 700;
          color: #1a5276;
        }
        .pdf-warning-section .pdf-section-title {
          color: #bf360c;
        }
        .pdf-section-body {
          padding: 10px 16px;
        }

        .pdf-line {
          margin-bottom: 4px;
          font-size: 13px;
          line-height: 1.7;
        }
        .pdf-bullet {
          display: flex;
          gap: 6px;
        }
        .pdf-bullet-label {
          font-weight: 600;
          color: #1a5276;
          min-width: fit-content;
        }
        .pdf-bullet-value { color: #333; }
        .pdf-not-specified {
          color: #999;
          font-style: italic;
          font-size: 12px;
        }
        .pdf-bullet-dot {
          display: inline-block;
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #1a5276;
          margin-top: 8px;
          margin-left: 6px;
          flex-shrink: 0;
        }
        .pdf-warning-line {
          display: flex;
          gap: 6px;
          background: #fff3e0;
          border-radius: 4px;
          padding: 4px 8px;
          margin-bottom: 4px;
          color: #bf360c;
          font-size: 12px;
        }
        .pdf-numbered {
          display: flex;
          gap: 8px;
          align-items: baseline;
        }
        .pdf-numbered-badge {
          background: #1a5276;
          color: #fff;
          border-radius: 50%;
          width: 20px;
          height: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 11px;
          font-weight: 700;
          flex-shrink: 0;
        }

        .pdf-footer {
          margin-top: 20px;
          padding-top: 10px;
          border-top: 2px solid #e0e0e0;
          text-align: center;
          font-size: 10px;
          color: #999;
        }
        .pdf-footer-disclaimer {
          margin-top: 4px;
          font-size: 9px;
          color: #bbb;
        }
      </style>

      <!-- Header -->
      <div class="pdf-header">
        <div class="pdf-header-title">🏥 סיכום רפואי</div>
        <div class="pdf-header-subtitle">Medical Summary Report</div>
        <div class="pdf-header-meta">
          תאריך: ${dateStr} &nbsp;|&nbsp; שעה: ${timeStr} &nbsp;|&nbsp; מזהה ריצה: ${runId}
        </div>
      </div>

      <!-- Validation -->
      ${validationHtml}

      <!-- Sections -->
      ${sectionsHtml}

      <!-- Footer -->
      <div class="pdf-footer">
        <div>מסמך זה הופק אוטומטית ממערכת תמלול רפואי מבוססת בינה מלאכותית</div>
        <div class="pdf-footer-disclaimer">
          יש לבדוק ולאמת את תוכן הסיכום מול התמלול המקורי. אין להסתמך על מסמך זה בלבד לצורך קבלת החלטות רפואיות.
        </div>
      </div>
    </div>
  `;
}

// ─────────────────────────────────────────────────────────────────────────────

interface Section {
  title: string;
  lines: string[];
}

function parseSections(text: string): Section[] {
  const sections: Section[] = [];
  let current: Section | null = null;

  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    const headerMatch = trimmed.match(/^---(.+?)---$/);
    if (headerMatch) {
      current = { title: headerMatch[1].trim(), lines: [] };
      sections.push(current);
      continue;
    }
    if (current && (trimmed || current.lines.length > 0)) {
      current.lines.push(line);
    }
  }

  // Trim trailing empty lines
  for (const s of sections) {
    while (s.lines.length && !s.lines[s.lines.length - 1].trim()) s.lines.pop();
  }

  return sections;
}

function formatPdfLine(line: string, isWarning: boolean): string {
  const trimmed = line.trim();
  if (!trimmed) return "";

  // Warning line
  if (trimmed.startsWith("⚠️") || trimmed.startsWith("• ⚠️")) {
    const text = trimmed.replace(/^•?\s*⚠️\s*/, "");
    return `<div class="pdf-warning-line"><span>⚠️</span><span>${text}</span></div>`;
  }

  // Bullet with label: "• גיל: 79"
  const bulletLabelMatch = trimmed.match(/^•\s*(.+?):\s*(.+)$/);
  if (bulletLabelMatch) {
    const val = bulletLabelMatch[2].trim();
    const cls = val === "לא צוין" ? "pdf-not-specified" : "pdf-bullet-value";
    return `<div class="pdf-line pdf-bullet"><span class="pdf-bullet-label">${bulletLabelMatch[1]}:</span><span class="${cls}">${val}</span></div>`;
  }

  // Simple bullet
  if (trimmed.startsWith("•")) {
    return `<div class="pdf-line pdf-bullet"><span class="pdf-bullet-dot"></span><span>${trimmed.slice(1).trim()}</span></div>`;
  }

  // Numbered item
  const numberedMatch = trimmed.match(/^(\d+)\.\s*(.+)$/);
  if (numberedMatch) {
    return `<div class="pdf-line pdf-numbered"><span class="pdf-numbered-badge">${numberedMatch[1]}</span><span>${numberedMatch[2]}</span></div>`;
  }

  // Plain text
  return `<div class="pdf-line">${trimmed}</div>`;
}
