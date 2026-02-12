import { useEffect, useState, useRef, useCallback } from "react";
import { api } from "../api";

interface Props {
  runId: string;
  audioRef: React.RefObject<HTMLAudioElement | null>;
}

function fmt(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function AudioPlayer({ runId, audioRef }: Props) {
  const [hasAudio, setHasAudio] = useState<boolean | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [seeking, setSeeking] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);

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

  // Sync state from <audio> element
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onTime = () => {
      if (!seeking) {
        setCurrentTime(audio.currentTime);
      }
    };
    const onDur = () => setDuration(audio.duration || 0);
    const onLoaded = () => setDuration(audio.duration || 0);

    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("durationchange", onDur);
    audio.addEventListener("loadedmetadata", onLoaded);

    return () => {
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("durationchange", onDur);
      audio.removeEventListener("loadedmetadata", onLoaded);
    };
  }, [audioRef, seeking]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) audio.play();
    else audio.pause();
  };

  // Seek helpers — compute time from pointer position on the track
  const getTimeFromPointer = useCallback(
    (clientX: number): number => {
      const track = trackRef.current;
      if (!track || !duration) return 0;
      const rect = track.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return ratio * duration;
    },
    [duration],
  );

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      setSeeking(true);
      const t = getTimeFromPointer(e.clientX);
      setCurrentTime(t);
    },
    [getTimeFromPointer],
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!seeking) return;
      const t = getTimeFromPointer(e.clientX);
      setCurrentTime(t);
      // Live-update the audio position while dragging (throttled by pointer events)
      if (audioRef.current) {
        audioRef.current.currentTime = t;
      }
    },
    [seeking, getTimeFromPointer, audioRef],
  );

  const onPointerUp = useCallback(
    (e: React.PointerEvent) => {
      if (!seeking) return;
      const t = getTimeFromPointer(e.clientX);
      if (audioRef.current) {
        audioRef.current.currentTime = t;
      }
      setSeeking(false);
      setCurrentTime(t);
    },
    [seeking, getTimeFromPointer, audioRef],
  );

  // Skip ±5s with keyboard arrows or buttons
  const skip = (delta: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + delta));
  };

  if (hasAudio === null || !hasAudio) return null;

  const audioUrl = api.getAudioUrl(runId);
  const progress = duration ? (currentTime / duration) * 100 : 0;

  return (
    <div className="custom-audio-player">
      {/* Hidden native audio element (used as the playback engine) */}
      <audio ref={audioRef} preload="metadata" src={audioUrl} />

      <div className="player-row">
        {/* Skip back */}
        <button className="player-skip" onClick={() => skip(-5)} title="Back 5s">
          ⏪
        </button>

        {/* Play / Pause */}
        <button className="player-play" onClick={togglePlay} title={playing ? "Pause" : "Play"}>
          {playing ? "⏸" : "▶"}
        </button>

        {/* Skip forward */}
        <button className="player-skip" onClick={() => skip(5)} title="Forward 5s">
          ⏩
        </button>

        {/* Time */}
        <span className="player-time">{fmt(currentTime)}</span>

        {/* Seek track */}
        <div
          className="player-track"
          ref={trackRef}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          <div className="player-track-fill" style={{ width: `${progress}%` }} />
          <div className="player-thumb" style={{ left: `${progress}%` }} />
        </div>

        {/* Duration */}
        <span className="player-time">{fmt(duration)}</span>

        {/* Filename */}
        <span className="player-filename" title={filename ?? "Audio"}>
          🔊 {filename ?? "Audio"}
        </span>
      </div>
    </div>
  );
}
