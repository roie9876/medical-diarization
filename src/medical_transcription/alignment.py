"""
Fuzzy word alignment — maps Azure STT word timestamps onto the GPT final text.

The GPT pipeline produces the "authoritative" text (with speaker labels, spelling
corrections, etc.).  Azure STT produces word-level timestamps but lower-quality
Hebrew text.  This module aligns the two so every word in the final text gets a
(start_ms, end_ms) timestamp.

The approach:
1. Strip speaker labels from GPT text → plain word list.
2. Use difflib.SequenceMatcher to find matching blocks between STT words and GPT words.
3. Matched words inherit the STT timestamp directly.
4. Unmatched (inserted/corrected) words get interpolated timestamps.
5. Re-attach speaker labels and produce the final annotated word list.
"""

import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple

# Pattern to match speaker labels like [רופא]: or [מטופל]: or [דובר 1]:
SPEAKER_LABEL_RE = re.compile(r"\[([^\]]+)\]:\s*")


def _strip_speaker_labels(text: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Split GPT final text into a flat word list, tracking speaker label positions.
    
    Returns:
        words:  list of plain words (no labels)
        labels: list of {label, before_word_index} — where each label appears
    """
    words: List[str] = []
    labels: List[Dict[str, Any]] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Check for speaker label at start of line
        m = SPEAKER_LABEL_RE.match(line)
        if m:
            labels.append({"label": m.group(1), "before_word_index": len(words)})
            line = line[m.end():]

        for w in line.split():
            if w:
                words.append(w)

    return words, labels


def _normalize_word(w: str) -> str:
    """Normalize a word for comparison — strip punctuation, lowercase."""
    # Remove common Hebrew punctuation and diacritics
    w = re.sub(r'[.,;:!?"\'-—–…()״׳]', "", w)
    return w.strip().lower()


def align_timestamps(
    stt_words: List[Dict[str, Any]],
    final_text: str,
) -> List[Dict[str, Any]]:
    """
    Align STT word timestamps onto the GPT final text.

    Args:
        stt_words: list of {"word": str, "offset_ms": int, "duration_ms": int}
                   from Azure STT.
        final_text: the final text from the GPT pipeline (with speaker labels).

    Returns:
        List of annotated words:
        [
            {
                "word": "שלום",
                "start_ms": 500,
                "end_ms": 900,
                "speaker": "רופא" | null,
                "is_interpolated": false,
                "line_index": 0
            },
            ...
        ]
    """
    gpt_words, speaker_labels = _strip_speaker_labels(final_text)

    if not gpt_words or not stt_words:
        # Fallback: no alignment possible — return words without timestamps
        return _build_fallback(gpt_words, speaker_labels)

    # Normalize for matching
    stt_norm = [_normalize_word(w["word"]) for w in stt_words]
    gpt_norm = [_normalize_word(w) for w in gpt_words]

    # Find matching blocks
    matcher = SequenceMatcher(None, gpt_norm, stt_norm, autojunk=False)
    matching_blocks = matcher.get_matching_blocks()

    # Build a map: gpt_index → stt_index for matched words
    gpt_to_stt: Dict[int, int] = {}
    for block in matching_blocks:
        for k in range(block.size):
            gpt_idx = block.a + k
            stt_idx = block.b + k
            gpt_to_stt[gpt_idx] = stt_idx

    # Assign timestamps
    # Matched words get direct timestamps; unmatched get interpolated
    annotated: List[Dict[str, Any]] = []
    for i, word in enumerate(gpt_words):
        if i in gpt_to_stt:
            stt_w = stt_words[gpt_to_stt[i]]
            annotated.append({
                "word": word,
                "start_ms": stt_w["offset_ms"],
                "end_ms": stt_w["offset_ms"] + stt_w["duration_ms"],
                "is_interpolated": False,
            })
        else:
            # Placeholder — will be interpolated below
            annotated.append({
                "word": word,
                "start_ms": None,
                "end_ms": None,
                "is_interpolated": True,
            })

    # Interpolate missing timestamps
    _interpolate_gaps(annotated)

    # Attach speaker labels and line indices
    _attach_speakers(annotated, speaker_labels, final_text)

    return annotated


def _interpolate_gaps(annotated: List[Dict[str, Any]]):
    """
    Fill in None timestamps by linear interpolation between known neighbors.
    """
    n = len(annotated)
    i = 0
    while i < n:
        if annotated[i]["start_ms"] is not None:
            i += 1
            continue

        # Find the gap: i..j-1 are all None
        j = i
        while j < n and annotated[j]["start_ms"] is None:
            j += 1

        # Get bounding timestamps
        left_end = annotated[i - 1]["end_ms"] if i > 0 and annotated[i - 1]["end_ms"] is not None else 0
        right_start = annotated[j]["start_ms"] if j < n and annotated[j]["start_ms"] is not None else (left_end + (j - i) * 200)

        gap_count = j - i
        duration = right_start - left_end
        per_word = max(duration / gap_count, 0) if gap_count > 0 else 0

        for k in range(gap_count):
            start = int(left_end + k * per_word)
            end = int(left_end + (k + 1) * per_word)
            annotated[i + k]["start_ms"] = start
            annotated[i + k]["end_ms"] = end

        i = j


def _attach_speakers(
    annotated: List[Dict[str, Any]],
    speaker_labels: List[Dict[str, Any]],
    final_text: str,
):
    """Attach speaker labels to each word and compute line_index."""
    # Build a map of word_index → speaker
    current_speaker = None
    speaker_map: Dict[int, str] = {}
    label_positions = {lbl["before_word_index"]: lbl["label"] for lbl in speaker_labels}

    for i in range(len(annotated)):
        if i in label_positions:
            current_speaker = label_positions[i]
        speaker_map[i] = current_speaker

    # Assign speaker + compute line indices from original text
    lines = [l.strip() for l in final_text.splitlines() if l.strip()]
    word_idx = 0
    for line_idx, line in enumerate(lines):
        # Strip speaker label from line for word counting
        m = SPEAKER_LABEL_RE.match(line)
        if m:
            line = line[m.end():]
        line_words = line.split()
        for _ in line_words:
            if word_idx < len(annotated):
                annotated[word_idx]["speaker"] = speaker_map.get(word_idx)
                annotated[word_idx]["line_index"] = line_idx
                word_idx += 1


def _build_fallback(
    gpt_words: List[str],
    speaker_labels: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return words with no timestamps (when STT data is unavailable)."""
    label_positions = {lbl["before_word_index"]: lbl["label"] for lbl in speaker_labels}
    current_speaker = None
    result = []
    for i, word in enumerate(gpt_words):
        if i in label_positions:
            current_speaker = label_positions[i]
        result.append({
            "word": word,
            "start_ms": None,
            "end_ms": None,
            "speaker": current_speaker,
            "is_interpolated": True,
            "line_index": 0,
        })
    return result


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 3:
        print("Usage: python alignment.py <stt_timestamps.json> <final_text.txt>")
        sys.exit(1)

    stt_path = sys.argv[1]
    text_path = sys.argv[2]

    with open(stt_path, "r", encoding="utf-8") as f:
        stt_data = json.load(f)

    with open(text_path, "r", encoding="utf-8") as f:
        final_text = f.read()

    aligned = align_timestamps(stt_data["words"], final_text)

    matched = sum(1 for w in aligned if not w["is_interpolated"])
    total = len(aligned)
    print(f"Aligned: {matched}/{total} words matched ({100 * matched / total:.0f}%)")
    print(f"\nFirst 20 words:")
    for w in aligned[:20]:
        t = f"[{w['start_ms'] / 1000:.2f}s]" if w["start_ms"] is not None else "[?.??s]"
        flag = " ~" if w["is_interpolated"] else ""
        spk = f" ({w.get('speaker', '')})" if w.get("speaker") else ""
        print(f"  {t} {w['word']}{spk}{flag}")

    out = text_path.replace(".txt", "_aligned.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(aligned, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out}")
