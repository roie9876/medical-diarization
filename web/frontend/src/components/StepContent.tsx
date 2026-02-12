import React, { useState, useMemo } from "react";
import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";
import type { StepDetail } from "../types";

interface Props {
  currentStep: StepDetail;
  previousStep: StepDetail | null;
}

type ViewMode = "text" | "changes" | "diff-split" | "diff-unified";

/* ── Line-level change detection ────────────────────────────────────── */

interface LineDiff {
  kind: "equal" | "added" | "removed" | "changed";
  lineNum: number;       // 1-based, in the NEW text
  oldLineNum: number;    // 1-based, in the OLD text (0 if added)
  oldText?: string;
  newText?: string;
}

interface ChangeHunk {
  id: number;
  contextBefore: { lineNum: number; text: string }[];
  changes: LineDiff[];
  contextAfter: { lineNum: number; text: string }[];
}

const CONTEXT_LINES = 2;

/**
 * Build line diffs and group into hunks with context.
 * Each hunk shows the actual changes plus a few context lines.
 */
function buildHunks(oldText: string, newText: string): { hunks: ChangeHunk[]; totalChanges: number } {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");

  // Simple LCS on lines for alignment
  const m = oldLines.length;
  const n = newLines.length;

  // For very large texts, use a simpler O(n) approach
  if (m + n > 8000) {
    return buildHunksSimple(oldLines, newLines);
  }

  // Build LCS table
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    new Array<number>(n + 1).fill(0),
  );
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (oldLines[i] === newLines[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  // Trace back to build diff list
  const diffs: LineDiff[] = [];
  let oi = 0, ni = 0;
  while (oi < m && ni < n) {
    if (oldLines[oi] === newLines[ni]) {
      diffs.push({ kind: "equal", lineNum: ni + 1, oldLineNum: oi + 1, newText: newLines[ni] });
      oi++; ni++;
    } else if ((dp[oi + 1]?.[ni] ?? 0) >= (dp[oi]?.[ni + 1] ?? 0)) {
      diffs.push({ kind: "removed", lineNum: ni + 1, oldLineNum: oi + 1, oldText: oldLines[oi] });
      oi++;
    } else {
      diffs.push({ kind: "added", lineNum: ni + 1, oldLineNum: 0, newText: newLines[ni] });
      ni++;
    }
  }
  while (oi < m) {
    diffs.push({ kind: "removed", lineNum: ni + 1, oldLineNum: oi + 1, oldText: oldLines[oi] });
    oi++;
  }
  while (ni < n) {
    diffs.push({ kind: "added", lineNum: ni + 1, oldLineNum: 0, newText: newLines[ni] });
    ni++;
  }

  return groupIntoHunks(diffs, newLines);
}

/** Fallback for very long files: compare line-by-line positionally */
function buildHunksSimple(oldLines: string[], newLines: string[]): { hunks: ChangeHunk[]; totalChanges: number } {
  const diffs: LineDiff[] = [];
  const max = Math.max(oldLines.length, newLines.length);
  for (let i = 0; i < max; i++) {
    const ol = oldLines[i];
    const nl = newLines[i];
    if (ol === nl) {
      diffs.push({ kind: "equal", lineNum: i + 1, oldLineNum: i + 1, newText: nl });
    } else {
      if (ol !== undefined && nl !== undefined) {
        diffs.push({ kind: "removed", lineNum: i + 1, oldLineNum: i + 1, oldText: ol });
        diffs.push({ kind: "added", lineNum: i + 1, oldLineNum: 0, newText: nl });
      } else if (ol !== undefined) {
        diffs.push({ kind: "removed", lineNum: i + 1, oldLineNum: i + 1, oldText: ol });
      } else if (nl !== undefined) {
        diffs.push({ kind: "added", lineNum: i + 1, oldLineNum: 0, newText: nl });
      }
    }
  }
  return groupIntoHunks(diffs, newLines);
}

/** Group diffs into hunks with context */
function groupIntoHunks(diffs: LineDiff[], _newLines?: string[]): { hunks: ChangeHunk[]; totalChanges: number } {
  // Find indices of changed diffs
  const changeIndices: number[] = [];
  for (let i = 0; i < diffs.length; i++) {
    if (diffs[i].kind !== "equal") changeIndices.push(i);
  }

  if (changeIndices.length === 0) return { hunks: [], totalChanges: 0 };

  // Group consecutive changes (merge if gap ≤ CONTEXT_LINES * 2)
  const groups: { start: number; end: number }[] = [];
  let gStart = changeIndices[0];
  let gEnd = changeIndices[0];
  for (let k = 1; k < changeIndices.length; k++) {
    if (changeIndices[k] - gEnd <= CONTEXT_LINES * 2 + 1) {
      gEnd = changeIndices[k];
    } else {
      groups.push({ start: gStart, end: gEnd });
      gStart = changeIndices[k];
      gEnd = changeIndices[k];
    }
  }
  groups.push({ start: gStart, end: gEnd });

  // Build hunks from groups
  const hunks: ChangeHunk[] = groups.map((g, id) => {
    // Context before
    const ctxBefore: { lineNum: number; text: string }[] = [];
    for (let i = Math.max(0, g.start - CONTEXT_LINES); i < g.start; i++) {
      if (diffs[i].kind === "equal" && diffs[i].newText !== undefined) {
        ctxBefore.push({ lineNum: diffs[i].lineNum, text: diffs[i].newText! });
      }
    }

    // The changed diffs
    const changes = diffs.slice(g.start, g.end + 1);

    // Context after
    const ctxAfter: { lineNum: number; text: string }[] = [];
    for (let i = g.end + 1; i <= Math.min(diffs.length - 1, g.end + CONTEXT_LINES); i++) {
      if (diffs[i].kind === "equal" && diffs[i].newText !== undefined) {
        ctxAfter.push({ lineNum: diffs[i].lineNum, text: diffs[i].newText! });
      }
    }

    return { id, contextBefore: ctxBefore, changes, contextAfter: ctxAfter };
  });

  return { hunks, totalChanges: changeIndices.length };
}

/* ── Word-level highlighting within a line pair ─────────────────────── */

interface WordToken { text: string; kind: "equal" | "added" | "removed" }

function wordHighlight(oldLine: string, newLine: string): { oldTokens: WordToken[]; newTokens: WordToken[] } {
  const ow = oldLine.split(/(\s+)/);
  const nw = newLine.split(/(\s+)/);
  const m = ow.length, n = nw.length;

  if (m * n > 250_000) {
    return {
      oldTokens: [{ text: oldLine, kind: "removed" }],
      newTokens: [{ text: newLine, kind: "added" }],
    };
  }

  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--)
    for (let j = n - 1; j >= 0; j--)
      dp[i][j] = ow[i] === nw[j] ? dp[i+1][j+1] + 1 : Math.max(dp[i+1][j], dp[i][j+1]);

  const oldTokens: WordToken[] = [];
  const newTokens: WordToken[] = [];
  let i = 0, j = 0;
  while (i < m && j < n) {
    if (ow[i] === nw[j]) {
      oldTokens.push({ text: ow[i], kind: "equal" });
      newTokens.push({ text: nw[j], kind: "equal" });
      i++; j++;
    } else if ((dp[i+1]?.[j] ?? 0) >= (dp[i]?.[j+1] ?? 0)) {
      oldTokens.push({ text: ow[i], kind: "removed" });
      i++;
    } else {
      newTokens.push({ text: nw[j], kind: "added" });
      j++;
    }
  }
  while (i < m) oldTokens.push({ text: ow[i++], kind: "removed" });
  while (j < n) newTokens.push({ text: nw[j++], kind: "added" });
  return { oldTokens, newTokens };
}

/* ── Component ──────────────────────────────────────────────────────── */

export default function StepContent({ currentStep, previousStep }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>(
    previousStep ? "changes" : "text",
  );

  const { hunks, totalChanges } = useMemo(() => {
    if (!previousStep) return { hunks: [] as ChangeHunk[], totalChanges: 0 };
    return buildHunks(previousStep.text, currentStep.text);
  }, [previousStep, currentStep]);

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
                className={viewMode === "changes" ? "active" : ""}
                onClick={() => setViewMode("changes")}
              >
                Changes
                {totalChanges > 0 && (
                  <span className="change-count-badge">{totalChanges}</span>
                )}
              </button>
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
        ) : viewMode === "changes" && previousStep ? (
          <div className="changes-view" dir="rtl">
            <div className="changes-banner">
              <span className="changes-banner-label">
                Comparing: <strong>{previousStep.step_name}</strong> → <strong>{currentStep.step_name}</strong>
              </span>
              <span className="changes-banner-stats">
                {hunks.length} region{hunks.length !== 1 ? "s" : ""} changed · {totalChanges} line{totalChanges !== 1 ? "s" : ""} affected
              </span>
            </div>

            {hunks.length === 0 ? (
              <div className="changes-empty">
                <span className="changes-empty-icon">✅</span>
                <p>No changes between these steps</p>
              </div>
            ) : (
              <div className="changes-hunks">
                {hunks.map((hunk) => (
                  <div key={hunk.id} className="change-hunk">
                    <div className="hunk-header">
                      Change {hunk.id + 1} of {hunks.length}
                      <span className="hunk-lines">
                        {hunk.changes[0]?.kind === "removed" || hunk.changes[0]?.kind === "changed"
                          ? `line ${hunk.changes[0].oldLineNum}`
                          : `line ${hunk.changes[0].lineNum}`}
                      </span>
                    </div>

                    {/* Context before */}
                    {hunk.contextBefore.map((ctx, i) => (
                      <div key={`cb-${i}`} className="hunk-line hunk-context" dir="rtl">
                        <span className="hunk-line-num">{ctx.lineNum}</span>
                        <span className="hunk-line-text">{ctx.text || "\u00A0"}</span>
                      </div>
                    ))}

                    {/* Changed lines */}
                    {renderHunkChanges(hunk.changes)}

                    {/* Context after */}
                    {hunk.contextAfter.map((ctx, i) => (
                      <div key={`ca-${i}`} className="hunk-line hunk-context" dir="rtl">
                        <span className="hunk-line-num">{ctx.lineNum}</span>
                        <span className="hunk-line-text">{ctx.text || "\u00A0"}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : previousStep && (viewMode === "diff-split" || viewMode === "diff-unified") ? (
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

/* ── Render changed lines with word-level highlighting ──────────────── */

function renderHunkChanges(changes: LineDiff[]) {
  const elements: React.ReactNode[] = [];

  // Pair up consecutive removed+added as "changed" lines for word-level highlight
  let i = 0;
  while (i < changes.length) {
    const c = changes[i];

    if (c.kind === "removed" && i + 1 < changes.length && changes[i + 1].kind === "added") {
      // Paired change: show word-level diff
      const removed = c;
      const added = changes[i + 1];
      const { oldTokens, newTokens } = wordHighlight(removed.oldText || "", added.newText || "");

      elements.push(
        <div key={`r-${i}`} className="hunk-line hunk-removed" dir="rtl">
          <span className="hunk-line-num">{removed.oldLineNum}</span>
          <span className="hunk-line-prefix">−</span>
          <span className="hunk-line-text">
            {oldTokens.map((tok, ti) =>
              tok.kind === "removed" ? (
                <span key={ti} className="hw-removed">{tok.text}</span>
              ) : (
                <span key={ti}>{tok.text}</span>
              ),
            )}
          </span>
        </div>,
      );
      elements.push(
        <div key={`a-${i}`} className="hunk-line hunk-added" dir="rtl">
          <span className="hunk-line-num">{added.lineNum}</span>
          <span className="hunk-line-prefix">+</span>
          <span className="hunk-line-text">
            {newTokens.map((tok, ti) =>
              tok.kind === "added" ? (
                <span key={ti} className="hw-added">{tok.text}</span>
              ) : (
                <span key={ti}>{tok.text}</span>
              ),
            )}
          </span>
        </div>,
      );
      i += 2;
    } else if (c.kind === "removed") {
      elements.push(
        <div key={`r-${i}`} className="hunk-line hunk-removed" dir="rtl">
          <span className="hunk-line-num">{c.oldLineNum}</span>
          <span className="hunk-line-prefix">−</span>
          <span className="hunk-line-text">{c.oldText || "\u00A0"}</span>
        </div>,
      );
      i++;
    } else if (c.kind === "added") {
      elements.push(
        <div key={`a-${i}`} className="hunk-line hunk-added" dir="rtl">
          <span className="hunk-line-num">{c.lineNum}</span>
          <span className="hunk-line-prefix">+</span>
          <span className="hunk-line-text">{c.newText || "\u00A0"}</span>
        </div>,
      );
      i++;
    } else {
      // equal line inside a hunk gap
      elements.push(
        <div key={`e-${i}`} className="hunk-line hunk-context" dir="rtl">
          <span className="hunk-line-num">{c.lineNum}</span>
          <span className="hunk-line-text">{c.newText || "\u00A0"}</span>
        </div>,
      );
      i++;
    }
  }

  return <>{elements}</>;
}
