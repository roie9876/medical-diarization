"""
Test: Can GPT-Audio return word-level timestamps?

We send a short audio clip with a prompt requesting [start-end] per word/phrase,
then check if the timestamps look real or hallucinated.
"""

import os
import sys
import base64
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
from pydub import AudioSegment

# Setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "medical_transcription"))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Use the same client as the main pipeline
client = AzureOpenAI(
    azure_endpoint=os.getenv("ENDPOINT_URL", "").rstrip('"'),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2025-01-01-preview",
)

# ── Pick an audio file ──────────────────────────────────────────────────
# Use sample1 or sample2 — take first 60s to keep it short
AUDIO_PATH = os.path.join(PROJECT_ROOT, "samples", "sample1", "audio.mp3")
if not os.path.exists(AUDIO_PATH):
    AUDIO_PATH = os.path.join(PROJECT_ROOT, "samples", "sample2", "audio.mp3")

print(f"Audio: {AUDIO_PATH}")

# Take just the first 60 seconds for a quick test
audio = AudioSegment.from_file(AUDIO_PATH)
snippet = audio[:60_000]  # first 60s
snippet_path = "/tmp/timestamp_test_60s.mp3"
snippet.export(snippet_path, format="mp3")
print(f"Snippet: {len(snippet)/1000:.1f}s exported to {snippet_path}")

# Encode
with open(snippet_path, "rb") as f:
    audio_b64 = base64.standard_b64encode(f.read()).decode("utf-8")


# ── Test 1: Request timestamps inline ───────────────────────────────────
print("\n" + "="*70)
print("TEST 1: Ask for [start-end] per phrase")
print("="*70)

prompt_1 = """Transcribe this audio with timestamps.
For each phrase or sentence, output the start and end time in seconds.
Format: [start_sec - end_sec] transcribed text

Example:
[0.0 - 2.3] שלום, מה שלומך
[2.5 - 5.1] אני מרגיש כאב בצד ימין

Transcribe everything. Medical terms in English."""

messages_1 = [
    {"role": "system", "content": "You are a precise transcriber. You must include timestamps for every phrase."},
    {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt_1},
            {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "mp3"}}
        ]
    }
]

print("\nSending request...")
completion_1 = client.chat.completions.create(
    model="gpt-audio",
    messages=messages_1,
    max_tokens=4096,
    temperature=0,
)

result_1 = completion_1.choices[0].message.content
print("\n--- RESULT (phrase-level timestamps) ---")
print(result_1)


# ── Test 2: Request word-level timestamps ───────────────────────────────
print("\n" + "="*70)
print("TEST 2: Ask for word-level timestamps")
print("="*70)

prompt_2 = """Transcribe this audio word by word with precise timestamps.
For EACH word, output: [start_sec] word

Example:
[0.00] שלום
[0.35] מה
[0.52] שלומך

Be precise with timing. Every single word must have a timestamp."""

messages_2 = [
    {"role": "system", "content": "You are a precise word-by-word transcriber with timestamps."},
    {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt_2},
            {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "mp3"}}
        ]
    }
]

print("\nSending request...")
completion_2 = client.chat.completions.create(
    model="gpt-audio",
    messages=messages_2,
    max_tokens=8192,
    temperature=0,
)

result_2 = completion_2.choices[0].message.content
print("\n--- RESULT (word-level timestamps) ---")
print(result_2)


# ── Summary ─────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("ANALYSIS")
print("="*70)

# Quick check: does the output contain timestamp patterns?
import re

# Test 1 analysis
timestamps_1 = re.findall(r'\[[\d.]+ *[-–] *[\d.]+\]', result_1)
print(f"\nTest 1 (phrase): Found {len(timestamps_1)} timestamp markers")
if timestamps_1:
    print(f"  First: {timestamps_1[0]}")
    print(f"  Last:  {timestamps_1[-1]}")

# Test 2 analysis
timestamps_2 = re.findall(r'\[[\d.]+\]', result_2)
print(f"\nTest 2 (word): Found {len(timestamps_2)} timestamp markers")
if timestamps_2:
    print(f"  First: {timestamps_2[0]}")
    print(f"  Last:  {timestamps_2[-1]}")
    # Check if timestamps are monotonically increasing
    values = [float(re.search(r'[\d.]+', t).group()) for t in timestamps_2]
    is_monotonic = all(a <= b for a, b in zip(values, values[1:]))
    max_ts = max(values) if values else 0
    print(f"  Monotonically increasing: {is_monotonic}")
    print(f"  Max timestamp: {max_ts:.1f}s (audio is 60s)")
    print(f"  Timestamps look {'REAL' if is_monotonic and 50 < max_ts < 65 else 'SUSPICIOUS'}!")

# Save results for inspection
output = {
    "test1_phrase_timestamps": result_1,
    "test2_word_timestamps": result_2,
    "test1_count": len(timestamps_1),
    "test2_count": len(timestamps_2),
}
out_path = "/tmp/timestamp_test_results.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\nResults saved to {out_path}")
