"""Quick test: alignment between Azure STT timestamps and GPT final text."""
import json
import sys
sys.path.insert(0, "src/medical_transcription")
from alignment import align_timestamps

# Load STT timestamps
with open("/tmp/stt_test_60s.stt_timestamps.json") as f:
    stt_data = json.load(f)

# Load first 15 lines of final transcription (roughly covering 60s)
with open("samples/sample1/our_result/final_transcription.txt") as f:
    lines = f.read().splitlines()

text = "\n".join(lines[:15])
print(f"Text lines: {len(lines[:15])}, chars: {len(text)}")
print(f"STT words: {len(stt_data['words'])}")

aligned = align_timestamps(stt_data["words"], text)
matched = sum(1 for w in aligned if not w["is_interpolated"])
total = len(aligned)
print(f"Aligned: {matched}/{total} words ({100*matched/total:.0f}%)\n")

for w in aligned[:30]:
    t = f"[{w['start_ms']/1000:.2f}s]"
    flag = " ~" if w["is_interpolated"] else ""
    spk = f" ({w.get('speaker', '')})" if w.get("speaker") else ""
    print(f"  {t} {w['word']}{spk}{flag}")
