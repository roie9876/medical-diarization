import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../api";
import type { WordTimestamp } from "../types";

interface Props {
  runId: string;
  audioRef: React.RefObject<HTMLAudioElement | null>;
}

/**
 * Displays the final transcription with word-level highlighting
 * synced to the audio player. Clicking a word seeks the audio.
 */
export default function SyncedTranscript({ runId, audioRef }: Props) {
  const [words, setWords] = useState<WordTimestamp[] | null>(null);
  const [error, setError] = useState("");
  const [activeIdx, setActiveIdx] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const wordRefs = useRef<(HTMLSpanElement | null)[]>([]);

  // Load word timestamps — auto-retry every 5s if not yet available
  useEffect(() => {
    setWords(null);
    setError("");
    let timer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const tryLoad = () => {
      api
        .getWordTimestamps(runId)
        .then((data) => {
          if (!cancelled) setWords(data);
        })
        .catch(() => {
          if (!cancelled) {
            setError("loading");
            // Retry every 5 seconds (STT runs in background)
            timer = setTimeout(tryLoad, 5000);
          }
        });
    };

    tryLoad();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [runId]);

  // Sync highlight to audio currentTime
  // Find the word index at a given timestamp (ms) via binary search
  const findWordAtMs = useCallback(
    (ms: number): number => {
      if (!words) return -1;
      let lo = 0,
        hi = words.length - 1,
        best = -1;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (words[mid].start_ms <= ms) {
          best = mid;
          lo = mid + 1;
        } else {
          hi = mid - 1;
        }
      }
      // Verify the word's end hasn't passed
      if (best >= 0 && words[best].end_ms < ms) {
        if (ms - words[best].end_ms > 500) best = -1;
      }
      return best;
    },
    [words],
  );

  const syncHighlight = useCallback(
    (scrollBehavior: ScrollBehavior = "smooth") => {
      if (!words || !audioRef.current) return;
      const ms = audioRef.current.currentTime * 1000;
      const best = findWordAtMs(ms);

      if (best !== activeIdx) {
        setActiveIdx(best);
        if (best >= 0 && wordRefs.current[best]) {
          wordRefs.current[best]!.scrollIntoView({
            behavior: scrollBehavior,
            block: "center",
          });
        }
      }
    },
    [words, activeIdx, audioRef, findWordAtMs],
  );

  const onTimeUpdate = useCallback(() => syncHighlight("smooth"), [syncHighlight]);

  // On seek (scrubbing), jump instantly — no smooth scroll lag
  const onSeeked = useCallback(() => syncHighlight("instant" as ScrollBehavior), [syncHighlight]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !words) return;
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("seeked", onSeeked);
    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("seeked", onSeeked);
    };
  }, [audioRef, words, onTimeUpdate, onSeeked]);

  // Click word → seek audio
  const handleWordClick = (idx: number) => {
    if (!audioRef.current || !words) return;
    audioRef.current.currentTime = words[idx].start_ms / 1000;
    audioRef.current.play();
  };

  if (error === "loading") {
    return (
      <div className="synced-transcript" dir="rtl">
        <div className="synced-header">
          <span className="synced-badge loading">🎤 Processing</span>
          <span className="synced-meta">Word timestamps are being generated in the background...</span>
        </div>
        <div className="synced-body">
          <div className="synced-loading">
            <div className="synced-spinner" />
            <p>Azure Fast Transcription is processing the audio.</p>
            <p className="subtle">This usually completes in 1–3 minutes. This page will update automatically.</p>
          </div>
        </div>
      </div>
    );
  }
  if (!words) return null;

  // Group words by line_index
  const lines: { lineIdx: number; speaker: string | null; words: { w: WordTimestamp; globalIdx: number }[] }[] = [];
  let currentLine: typeof lines[0] | null = null;

  words.forEach((w, i) => {
    if (!currentLine || w.line_index !== currentLine.lineIdx) {
      currentLine = { lineIdx: w.line_index, speaker: w.speaker, words: [] };
      lines.push(currentLine);
    }
    currentLine.words.push({ w, globalIdx: i });
  });

  return (
    <div className="synced-transcript" ref={containerRef} dir="rtl">
      <div className="synced-header">
        <span className="synced-badge">🔊 Live Sync</span>
        <span className="synced-meta">{words.length} words</span>
      </div>
      <div className="synced-body">
        {lines.map((line, li) => (
          <div key={li} className="synced-line">
            {line.speaker && (
              <span className="synced-speaker">[{line.speaker}]:</span>
            )}
            {line.words.map(({ w, globalIdx }) => (
              <span
                key={globalIdx}
                ref={(el) => { wordRefs.current[globalIdx] = el; }}
                className={[
                  "synced-word",
                  globalIdx === activeIdx ? "active" : "",
                  w.is_interpolated ? "interpolated" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => handleWordClick(globalIdx)}
                title={`${(w.start_ms / 1000).toFixed(2)}s${w.is_interpolated ? " (interpolated)" : ""}`}
              >
                {w.word}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
