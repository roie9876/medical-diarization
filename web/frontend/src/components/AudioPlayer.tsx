import { useEffect, useState } from "react";
import { api } from "../api";

interface Props {
  runId: string;
  audioRef: React.RefObject<HTMLAudioElement | null>;
}

export default function AudioPlayer({ runId, audioRef }: Props) {
  const [hasAudio, setHasAudio] = useState<boolean | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setHasAudio(null);
    api
      .checkAudio(runId)
      .then((info) => {
        setHasAudio(info.has_audio);
        setFilename(info.filename);
      })
      .catch(() => setHasAudio(false));
  }, [runId]);

  if (hasAudio === null) return null; // loading
  if (!hasAudio) return null; // no audio for this run

  const audioUrl = api.getAudioUrl(runId);

  return (
    <div className={`audio-player ${expanded ? "expanded" : ""}`}>
      <button
        className="audio-toggle"
        onClick={() => setExpanded((p) => !p)}
        title={expanded ? "Collapse audio player" : "Expand audio player"}
      >
        <span className="audio-icon">🔊</span>
        <span className="audio-label">
          {filename ?? "Audio"}{" "}
          <span className="audio-arrow">{expanded ? "▼" : "▶"}</span>
        </span>
      </button>

      {expanded && (
        <div className="audio-controls">
          <audio ref={audioRef} controls preload="metadata" src={audioUrl}>
            Your browser does not support the audio element.
          </audio>
        </div>
      )}
    </div>
  );
}
