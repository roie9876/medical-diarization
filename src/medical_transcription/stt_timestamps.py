"""
Azure Speech Services STT — word-level timestamps.

Sends audio to Azure Speech-to-Text and returns a list of
{word, offset_ms, duration_ms} for every recognized word.

The text quality is *not* used — we only care about the timestamps.
The final text comes from the GPT pipeline; we align timestamps to it
via alignment.py.
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv
from pydub import AudioSegment

load_dotenv()


def _ensure_wav(audio_path: str) -> str:
    """Convert to 16 kHz mono WAV if needed (Speech SDK works best with WAV)."""
    p = Path(audio_path)
    if p.suffix.lower() == ".wav":
        return audio_path

    wav_path = p.with_suffix(".stt.wav")
    if wav_path.exists():
        return str(wav_path)

    audio = AudioSegment.from_file(audio_path)
    audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
    audio.export(str(wav_path), format="wav")
    return str(wav_path)


def transcribe_with_timestamps(
    audio_path: str,
    language: str = "he-IL",
    speech_key: Optional[str] = None,
    speech_region: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run Azure Speech-to-Text on *audio_path* and return word-level timestamps.

    Returns:
        {
            "words": [
                {"word": "שלום", "offset_ms": 500, "duration_ms": 400},
                ...
            ],
            "stt_text": "שלום ...",          # full STT text (for alignment reference)
            "duration_ms": 62000,             # total audio duration recognized
            "processing_time_seconds": 12.3,
        }
    """
    key = speech_key or os.getenv("AZURE_SPEECH_KEY", "")
    region = speech_region or os.getenv("AZURE_SPEECH_REGION", "")
    if not key or not region:
        raise RuntimeError("AZURE_SPEECH_KEY and AZURE_SPEECH_REGION must be set")

    wav_path = _ensure_wav(audio_path)

    # Configure speech recognizer
    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_recognition_language = language
    speech_config.request_word_level_timestamps()
    speech_config.output_format = speechsdk.OutputFormat.Detailed

    audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    # Collect all results (continuous recognition for long audio)
    all_words: List[Dict[str, Any]] = []
    full_text_parts: List[str] = []
    done = False
    cancel_error: Optional[str] = None
    start_time = time.time()

    def _on_recognized(evt: speechsdk.SpeechRecognitionEventArgs):
        result = evt.result
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            full_text_parts.append(result.text)
            print(f"   STT chunk: +{len(result.text)} chars, total words so far: ", end="")

            # Extract word-level timestamps from detailed JSON
            import json
            detailed = json.loads(result.json)
            best = detailed.get("NBest", [{}])[0]
            for w in best.get("Words", []):
                all_words.append({
                    "word": w.get("Word", ""),
                    "offset_ms": w.get("Offset", 0) // 10_000,    # 100-ns ticks → ms
                    "duration_ms": w.get("Duration", 0) // 10_000,
                })
            print(f"{len(all_words)}")

    def _on_canceled(evt: speechsdk.SpeechRecognitionCanceledEventArgs):
        nonlocal done, cancel_error
        if evt.reason == speechsdk.CancellationReason.Error:
            cancel_error = f"STT canceled: code={evt.error_code}, details={evt.error_details}"
            print(f"   ⚠️  {cancel_error}")
        done = True

    def _on_stopped(evt):
        nonlocal done
        done = True

    recognizer.recognized.connect(_on_recognized)
    recognizer.canceled.connect(_on_canceled)
    recognizer.session_stopped.connect(_on_stopped)

    recognizer.start_continuous_recognition()

    # Wait for recognition to finish
    while not done:
        time.sleep(0.2)

    recognizer.stop_continuous_recognition()
    processing_time = time.time() - start_time

    # Raise if canceled with error and no words collected
    if cancel_error and not all_words:
        raise RuntimeError(cancel_error)

    # Compute total duration from last word
    max_end_ms = 0
    if all_words:
        last = all_words[-1]
        max_end_ms = last["offset_ms"] + last["duration_ms"]

    return {
        "words": all_words,
        "stt_text": " ".join(full_text_parts),
        "duration_ms": max_end_ms,
        "processing_time_seconds": round(processing_time, 2),
    }


# ── CLI quick test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json as _json

    if len(sys.argv) < 2:
        print("Usage: python stt_timestamps.py <audio_file>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"🎤 Azure STT: {path}")
    result = transcribe_with_timestamps(path)
    print(f"   Words: {len(result['words'])}")
    print(f"   Duration: {result['duration_ms'] / 1000:.1f}s")
    print(f"   Time: {result['processing_time_seconds']:.1f}s")
    print(f"\n   First 10 words:")
    for w in result["words"][:10]:
        t = w["offset_ms"] / 1000
        print(f"     [{t:.2f}s] {w['word']}")
    print(f"\n   STT text (first 200 chars): {result['stt_text'][:200]}")

    # Save full result
    out = Path(path).with_suffix(".stt_timestamps.json")
    with open(out, "w", encoding="utf-8") as f:
        _json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n   Saved: {out}")
