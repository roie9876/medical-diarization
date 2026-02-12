"""
Azure Speech Services STT — word-level timestamps via Fast Transcription API.

Uses the Azure Fast Transcription REST API (synchronous, faster-than-real-time)
instead of the real-time Speech SDK.  A 20-minute audio file typically completes
in 1–3 minutes rather than 20.

Returns a list of {word, offset_ms, duration_ms} for every recognized word.
The text quality is *not* used — we only care about the timestamps.
The final text comes from the GPT pipeline; we align timestamps to it
via alignment.py.

API reference:
  https://learn.microsoft.com/azure/ai-services/speech-service/fast-transcription-create
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

# Fast Transcription API version
_API_VERSION = "2025-10-15"


def transcribe_with_timestamps(
    audio_path: str,
    language: str = "he-IL",
    speech_key: Optional[str] = None,
    speech_region: Optional[str] = None,
    max_speakers: int = 4,
) -> Dict[str, Any]:
    """
    Run Azure Fast Transcription on *audio_path* and return word-level timestamps.

    This is *much* faster than real-time — a 20-min file finishes in ~1–3 min.

    Args:
        audio_path:   Path to audio file (mp3, wav, m4a, ogg, flac, …).
        language:     BCP-47 locale.  Default ``"he-IL"`` for Hebrew.
        speech_key:   Azure Speech resource key (falls back to env var).
        speech_region: Azure Speech resource region (falls back to env var).
        max_speakers: Hint for diarization — maximum number of speakers.

    Returns:
        {
            "words": [
                {"word": "שלום", "offset_ms": 500, "duration_ms": 400},
                ...
            ],
            "stt_text": "שלום ...",          # full STT text (for alignment reference)
            "duration_ms": 62000,             # total audio duration recognized
            "processing_time_seconds": 3.4,
            "phrases": [ ... ],              # raw phrases from the API (optional)
        }
    """
    key = speech_key or os.getenv("AZURE_SPEECH_KEY", "")
    region = speech_region or os.getenv("AZURE_SPEECH_REGION", "")
    if not key or not region:
        raise RuntimeError("AZURE_SPEECH_KEY and AZURE_SPEECH_REGION must be set")

    url = (
        f"https://{region}.api.cognitive.microsoft.com"
        f"/speechtotext/transcriptions:transcribe"
        f"?api-version={_API_VERSION}"
    )

    # Build the JSON definition (passed as a form field)
    import json

    definition = {
        "locales": [language],
        "diarization": {
            "enabled": True,
            "maxSpeakers": max_speakers,
        },
    }

    headers = {
        "Ocp-Apim-Subscription-Key": key,
    }

    start_time = time.time()

    # POST multipart/form-data: audio file + definition
    audio_file_path = Path(audio_path)
    content_type_map = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".wma": "audio/x-ms-wma",
        ".aac": "audio/aac",
        ".webm": "audio/webm",
    }
    audio_content_type = content_type_map.get(
        audio_file_path.suffix.lower(), "application/octet-stream"
    )

    # Retry with exponential backoff for 429 (throttling) and 5xx errors
    MAX_RETRIES = 5
    retry_delay = 10  # seconds

    for attempt in range(1, MAX_RETRIES + 1):
        with open(audio_path, "rb") as af:
            files = {
                "audio": (audio_file_path.name, af, audio_content_type),
                "definition": (None, json.dumps(definition), "application/json"),
            }
            print(f"   🚀 Fast Transcription API: uploading {audio_file_path.name} …")
            resp = requests.post(url, headers=headers, files=files, timeout=600)

        if resp.status_code == 200:
            break

        if resp.status_code == 429 or resp.status_code >= 500:
            # Use Retry-After header if available, else exponential backoff
            wait = int(resp.headers.get("Retry-After", retry_delay))
            print(
                f"   ⚠️  {resp.status_code} ({resp.text[:120].strip()}) — "
                f"retry {attempt}/{MAX_RETRIES} in {wait}s …"
            )
            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"Fast Transcription API error {resp.status_code} after "
                    f"{MAX_RETRIES} retries: {resp.text[:500]}"
                )
            time.sleep(wait)
            retry_delay = min(retry_delay * 2, 120)  # cap at 2 minutes
            continue

        # Non-retryable error
        raise RuntimeError(
            f"Fast Transcription API error {resp.status_code}: {resp.text[:500]}"
        )

    processing_time = time.time() - start_time

    data = resp.json()

    # ── Parse response into our standard format ──────────────────────────
    all_words: List[Dict[str, Any]] = []
    full_text_parts: List[str] = []
    total_duration_ms = data.get("durationMilliseconds", 0)

    for phrase in data.get("phrases", []):
        full_text_parts.append(phrase.get("text", ""))
        for w in phrase.get("words", []):
            all_words.append({
                "word": w["text"],
                "offset_ms": w["offsetMilliseconds"],
                "duration_ms": w["durationMilliseconds"],
            })

    # Also grab the combined text
    combined = ""
    for cp in data.get("combinedPhrases", []):
        combined += cp.get("text", "") + " "
    stt_text = combined.strip() or " ".join(full_text_parts)

    # If duration not in top-level, compute from last word
    if not total_duration_ms and all_words:
        last = all_words[-1]
        total_duration_ms = last["offset_ms"] + last["duration_ms"]

    print(
        f"   ✅ Fast Transcription done: {len(all_words)} words, "
        f"{total_duration_ms / 1000:.1f}s audio, "
        f"{processing_time:.1f}s elapsed"
    )

    return {
        "words": all_words,
        "stt_text": stt_text,
        "duration_ms": total_duration_ms,
        "processing_time_seconds": round(processing_time, 2),
        "phrases": data.get("phrases", []),
    }


# ── CLI quick test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json as _json

    if len(sys.argv) < 2:
        print("Usage: python stt_timestamps.py <audio_file>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"🎤 Azure Fast Transcription: {path}")
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
