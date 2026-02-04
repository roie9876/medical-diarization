"""
Medical Transcription System - Main Script
Three-step approach:
1. GPT-Audio: Pure transcription (accurate text)
2. GPT-Audio: With diarization (identify all speakers)
3. GPT-5.2: Smart merge - combine best of both

Supports long audio files by chunking with overlap.
"""

import os
import sys
import base64
import json
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI
from pydub import AudioSegment

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evaluation import calculate_all_metrics, format_metrics_report

load_dotenv()

# Audio chunking settings
MAX_CHUNK_DURATION_MS = 4 * 60 * 1000  # 4 minutes in milliseconds
OVERLAP_DURATION_MS = 30 * 1000        # 30 seconds overlap


class MedicalTranscriber:
    """Medical conversation transcription with speaker diarization"""
    
    def __init__(self):
        # GPT-Audio client
        self.audio_client = AzureOpenAI(
            azure_endpoint=os.getenv("ENDPOINT_URL", "").rstrip('"'),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2025-01-01-preview",
        )
        
        # GPT-5.2 client for post-processing
        self.gpt52_client = AzureOpenAI(
            azure_endpoint=os.getenv("GPT52_ENDPOINT", "").strip(),
            api_key=os.getenv("GPT52_KEY"),
            api_version="2025-01-01-preview",
        )
    
    def encode_audio(self, audio_path: str) -> str:
        """Encode audio file to base64"""
        with open(audio_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")
    
    def get_audio_duration_ms(self, audio_path: str) -> int:
        """Get audio duration in milliseconds"""
        audio = AudioSegment.from_file(audio_path)
        return len(audio)
    
    def split_audio(self, audio_path: str, temp_dir: str) -> list:
        """
        Split audio into chunks with overlap
        
        Returns:
            List of tuples: (chunk_path, start_ms, end_ms, is_last)
        """
        audio = AudioSegment.from_file(audio_path)
        duration_ms = len(audio)
        
        # If short enough, no need to split
        if duration_ms <= MAX_CHUNK_DURATION_MS:
            return [(audio_path, 0, duration_ms, True)]
        
        chunks = []
        start_ms = 0
        chunk_num = 0
        
        while start_ms < duration_ms:
            # Calculate end position
            end_ms = min(start_ms + MAX_CHUNK_DURATION_MS, duration_ms)
            is_last = (end_ms >= duration_ms)
            
            # Extract chunk
            chunk = audio[start_ms:end_ms]
            
            # Save chunk
            chunk_path = os.path.join(temp_dir, f"chunk_{chunk_num:03d}.mp3")
            chunk.export(chunk_path, format="mp3")
            
            chunks.append((chunk_path, start_ms, end_ms, is_last))
            
            # Move to next chunk with overlap (unless this is the last)
            if not is_last:
                start_ms = end_ms - OVERLAP_DURATION_MS
            else:
                break
            
            chunk_num += 1
        
        return chunks
    
    def _call_audio_pure_transcription(self, audio_base64: str, audio_format: str = "mp3") -> str:
        """Step 1: Pure transcription - focus on text accuracy"""
        
        system_prompt = """אתה מתמלל מקצועי. תמלל בדיוק מילה במילה.
- מונחים רפואיים באנגלית: DVT, Ultrasound, Euthyrox, Lipitor, MRI, CT, ECG
- אל תוסיף סימוני דוברים
- תמלל הכל, כולל היסוסים"""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "תמלל את ההקלטה בדיוק. בלי סימוני דוברים."},
                    {"type": "input_audio", "input_audio": {"data": audio_base64, "format": audio_format}}
                ]
            }
        ]
        
        completion = self.audio_client.chat.completions.create(
            model="gpt-audio",
            messages=messages,
            max_tokens=16384,
            temperature=0,
        )
        
        return completion.choices[0].message.content
    
    def _call_audio_with_diarization(self, audio_base64: str, audio_format: str = "mp3") -> str:
        """Step 2: Transcription with speaker diarization"""
        
        system_prompt = """אתה מתמלל עם הפרדת דוברים.
זוהי שיחה רפואית - יכולים להיות:
- רופא/ים
- מטופל
- בני משפחה (אשה, ילדים וכו')

סמן כל דובר: [דובר 1], [דובר 2], [דובר 3] וכו'
תמלל כל מילה. מונחים רפואיים באנגלית."""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "תמלל עם הפרדת דוברים. זהה את כל הדוברים כולל בני משפחה."},
                    {"type": "input_audio", "input_audio": {"data": audio_base64, "format": audio_format}}
                ]
            }
        ]
        
        completion = self.audio_client.chat.completions.create(
            model="gpt-audio",
            messages=messages,
            max_tokens=16384,
            temperature=0.2,
        )
        
        return completion.choices[0].message.content
    
    def _call_gpt52_merge(self, pure_text: str, diarized_text: str) -> str:
        """Step 3: GPT-5.2 smart merge for a single chunk"""
        
        prompt = f"""יש לך שני תמלולים של אותה שיחה רפואית:

=== תמלול 1 (טקסט מדויק, בלי דוברים) ===
{pure_text}

=== תמלול 2 (עם הפרדת דוברים) ===
{diarized_text}

המשימה:
1. קח את מבנה הדוברים מתמלול 2 (כמה דוברים יש, מי אומר מה)
2. קח את הטקסט המדויק מתמלול 1 כשיש הבדלים
3. שמור על כל הדוברים שזוהו (כולל דובר 3 אם יש)
4. החלף מונחים רפואיים לאנגלית: DVT, Ultrasound, Euthyrox, Lipitor, MRI, CT, ECG

סימון דוברים:
- [רופא]: מי ששואל שאלות רפואיות
- [מטופל]: מי שעונה על שאלות על מצבו
- [בן משפחה]: אם יש מישהו נוסף

פורמט הפלט:
- רק התמלול, בלי הסברים, בלי כותרות
- כל שורה מתחילה ב-[רופא]: או [מטופל]: או [בן משפחה]:
- בלי Markdown, בלי כוכביות, בלי עיצוב

החזר רק את התמלול המאוחד:"""

        completion = self.gpt52_client.chat.completions.create(
            model="gpt-5.2-chat",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=16384,
        )
        
        return completion.choices[0].message.content
    
    def _fix_spelling_errors(self, text: str) -> str:
        """Fix spelling and semantic errors in Hebrew medical transcription"""
        
        prompt = f"""תקן שגיאות כתיב ושגיאות סמנטיות בתמלול הרפואי הבא.

הנה רשימה של שגיאות נפוצות שצריך לתקן:
- "עזות" → "הזעות"
- "עקומול" / "לעקומול" → "אקמול" / "לאקמול"
- "תחילות" → "בחילות"  
- "הרמונית" / "ההרמונית" → "ערמונית" / "הערמונית"
- "מייחה" → "ליחה"
- "מערך העצם" / "מהעצם" → "מח העצם" / "ממח העצם"
- "פרוטיק" → "פרטי"
- "העתק עדבק" → "העתק הדבק"
- "כהי מים" / "כואי מים" → "כולי מים"
- "הסמינים" → "הסימפטומים" או "הסימנים"
- "במקריב" → "בערב"
- "יציאה תקינות" → "יציאות תקינות"
- "דחיפות או דחיפות" → "דחיפות או תכיפות"
- "בליסה" → "בלעיסה"
- "אצלנו" (כשרופא בודד) → "אצלי"
- "בכום הלב" → "בקרום הלב"
- "הורידו לי ציטורציה" → "ירדה לי הסטורציה"
- "היו באדום" → "נבהלו"
- "רגישה יותר בנוח" → "מרגישה יותר בנוח"
- "בנועל" → "בנוהל"
- "קרדיולוק" → "קרדילול"
- "מולטאק" → "Multaq"
- "חומס" → "חום"
- "המסתרמות" → "המסתמיות"
- "קרדיטי" → "אנדוקרדיטיס"
- "ברעומת" → "ראומטולוגיה"
- "חטפם" → "התקף"
- "שאירו" → "שלנו"
- "לדיין" → "לדון"

כללים:
1. תקן רק שגיאות ברורות - אל תשנה מילים שנכתבו נכון
2. שמור על המבנה המדויק - כל סימוני הדוברים [רופא], [מטופל], [בן משפחה]
3. שמור על אורך הטקסט - אל תקצר ואל תוסיף תוכן
4. מונחים רפואיים באנגלית: TEE, CT, PET-CT, IgG4, Ultrasound, Multaq
5. החזר את כל הטקסט המתוקן, לא רק את השינויים

הטקסט לתיקון:
{text}

החזר את הטקסט המתוקן בלבד, בלי הסברים:"""

        completion = self.gpt52_client.chat.completions.create(
            model="gpt-5.2-chat",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=32000,
        )
        
        result = completion.choices[0].message.content
        
        # Verify we didn't lose too much content
        if len(result) < len(text) * 0.9:
            print(f"   ⚠️  Warning: Fixed text is too short, keeping original")
            return text
        
        return result
    
    def _call_gpt52_merge_chunks(self, chunk_transcriptions: list) -> str:
        """Merge multiple chunk transcriptions using algorithmic overlap detection"""
        
        if len(chunk_transcriptions) == 1:
            return chunk_transcriptions[0]
        
        # Algorithmic merge: find overlap between consecutive chunks
        merged = chunk_transcriptions[0]
        
        for i in range(1, len(chunk_transcriptions)):
            merged = self._merge_two_chunks_algorithmic(merged, chunk_transcriptions[i])
            print(f"      Merged chunk {i+1}/{len(chunk_transcriptions)}: {len(merged)} chars")
        
        return merged
    
    def _find_overlap(self, text1: str, text2: str, min_overlap: int = 50, max_overlap: int = 800) -> int:
        """Find the overlap between end of text1 and start of text2"""
        
        # Get the last part of text1 and first part of text2
        end1 = text1[-max_overlap:] if len(text1) > max_overlap else text1
        start2 = text2[:max_overlap] if len(text2) > max_overlap else text2
        
        best_overlap = 0
        
        # Try to find matching sequences
        for overlap_size in range(min_overlap, min(len(end1), len(start2)) + 1):
            # Check if end of text1 matches start of text2
            if end1[-overlap_size:] == start2[:overlap_size]:
                best_overlap = overlap_size
        
        # If exact match not found, try fuzzy matching on sentence boundaries
        if best_overlap == 0:
            # Split into sentences
            import re
            sentences1 = re.split(r'[\n.?!]', text1[-1500:])
            sentences2 = re.split(r'[\n.?!]', text2[:1500])
            
            # Clean sentences
            sentences1 = [s.strip() for s in sentences1 if len(s.strip()) > 20]
            sentences2 = [s.strip() for s in sentences2 if len(s.strip()) > 20]
            
            # Find matching sentence
            for s1 in reversed(sentences1[-10:]):  # Last 10 sentences of chunk 1
                for j, s2 in enumerate(sentences2[:10]):  # First 10 sentences of chunk 2
                    # Check for similar content (at least 80% match)
                    if len(s1) > 30 and len(s2) > 30:
                        common = sum(1 for a, b in zip(s1, s2) if a == b)
                        similarity = common / max(len(s1), len(s2))
                        if similarity > 0.7:
                            # Found overlap - return position in text2
                            pos = text2.find(s2)
                            if pos > 0:
                                return pos
        
        return best_overlap
    
    def _merge_two_chunks_algorithmic(self, chunk1: str, chunk2: str) -> str:
        """Merge two chunks by finding and removing overlap algorithmically"""
        
        overlap = self._find_overlap(chunk1, chunk2)
        
        if overlap > 0:
            # Remove overlapping part from chunk2
            return chunk1 + "\n" + chunk2[overlap:]
        else:
            # No overlap found - just concatenate with a newline
            return chunk1 + "\n" + chunk2
    
    def _merge_two_chunks(self, chunk1: str, chunk2: str, chunk2_num: int, total_chunks: int) -> str:
        """Merge two consecutive chunks, removing only the overlapping part"""
        
        prompt = f"""יש לך שני חלקים עוקבים של תמלול שיחה רפואית.
יש חפיפה של כ-30 שניות בין סוף חלק 1 לתחילת חלק 2.

=== חלק 1 (קודם) ===
{chunk1}

=== חלק 2 (המשך) ===
{chunk2}

המשימה: אחד את שני החלקים לתמלול אחד רציף.

כללים קריטיים:
1. זהה את החלק החופף - בדרך כלל 2-5 משפטים שמופיעים גם בסוף חלק 1 וגם בתחילת חלק 2
2. הסר רק את הכפילות - את המשפטים שמופיעים פעמיים
3. **שמור על כל שאר התוכן!** אסור למחוק משפטים שלא חוזרים על עצמם
4. התוצאה צריכה להיות ארוכה כמעט כמו שני החלקים יחד (פחות החפיפה)
5. שמור על סימוני הדוברים: [רופא], [מטופל], [בן משפחה]

פורמט הפלט:
- רק התמלול המאוחד, בלי הסברים
- בלי Markdown

החזר את התמלול המאוחד:"""

        completion = self.gpt52_client.chat.completions.create(
            model="gpt-5.2-chat",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=32000,
        )
        
        return completion.choices[0].message.content
    
    def transcribe_chunk(self, audio_path: str, chunk_num: int, total_chunks: int) -> dict:
        """Transcribe a single audio chunk using the three-step approach"""
        
        print(f"\n   📍 Chunk {chunk_num}/{total_chunks}")
        
        audio_format = os.path.splitext(audio_path)[1][1:].lower() or "mp3"
        audio_base64 = self.encode_audio(audio_path)
        
        # Step 1: Pure transcription
        print(f"      Step 1: Pure transcription...")
        pure_text = self._call_audio_pure_transcription(audio_base64, audio_format)
        
        # Step 2: Diarization
        print(f"      Step 2: Diarization...")
        diarized_text = self._call_audio_with_diarization(audio_base64, audio_format)
        
        # Step 3: Merge
        print(f"      Step 3: Merge...")
        merged_text = self._call_gpt52_merge(pure_text, diarized_text)
        
        print(f"      ✅ Done ({len(merged_text)} chars)")
        
        return {
            "pure": pure_text,
            "diarized": diarized_text,
            "merged": merged_text,
        }
    
    def transcribe(self, audio_path: str, output_dir: str = None) -> dict:
        """
        Full transcription pipeline with support for long audio files
        
        Args:
            audio_path: Path to audio file (mp3, wav, etc.)
            output_dir: Directory to save results (optional)
        
        Returns:
            Dictionary with transcription results and metadata
        """
        print("="*70)
        print("MEDICAL TRANSCRIPTION - THREE STEP APPROACH")
        print("="*70)
        
        # Check audio duration
        duration_ms = self.get_audio_duration_ms(audio_path)
        duration_min = duration_ms / 1000 / 60
        print(f"\n📂 Audio: {audio_path}")
        print(f"   Duration: {duration_min:.1f} minutes")
        
        # Determine if we need to chunk
        needs_chunking = duration_ms > MAX_CHUNK_DURATION_MS
        
        if needs_chunking:
            print(f"\n⚠️  Audio is longer than {MAX_CHUNK_DURATION_MS/1000/60:.0f} minutes")
            print(f"   Will split into chunks with {OVERLAP_DURATION_MS/1000:.0f}s overlap")
        
        start_time = datetime.now()
        
        # Create temp directory for chunks
        with tempfile.TemporaryDirectory() as temp_dir:
            # Split audio if needed
            chunks = self.split_audio(audio_path, temp_dir)
            total_chunks = len(chunks)
            
            print(f"\n🔄 Processing {total_chunks} chunk(s)...")
            
            # Process each chunk
            chunk_results = []
            for i, (chunk_path, start_ms, end_ms, is_last) in enumerate(chunks, 1):
                result = self.transcribe_chunk(chunk_path, i, total_chunks)
                chunk_results.append(result)
            
            # Merge all chunk transcriptions
            if total_chunks > 1:
                print(f"\n🔄 Merging {total_chunks} chunks (pairwise)...")
                chunk_transcriptions = [r["merged"] for r in chunk_results]
                final_text = self._call_gpt52_merge_chunks(chunk_transcriptions)
                print(f"   ✅ Merged ({len(final_text)} chars)")
            else:
                final_text = chunk_results[0]["merged"]
        
        total_time = (datetime.now() - start_time).total_seconds()
        
        # Step 4: Fix spelling and semantic errors
        print(f"\n🔧 Fixing spelling and semantic errors...")
        final_text = self._fix_spelling_errors(final_text)
        print(f"   ✅ Fixed ({len(final_text)} chars)")
        
        # Build result
        result = {
            "final_transcription": final_text,
            "metadata": {
                "audio_path": audio_path,
                "duration_minutes": duration_min,
                "num_chunks": total_chunks,
                "timestamp": datetime.now().isoformat(),
                "processing_time_seconds": total_time,
            }
        }
        
        # Save if output_dir provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
            with open(os.path.join(output_dir, "final_transcription.txt"), "w", encoding="utf-8") as f:
                f.write(final_text)
            
            with open(os.path.join(output_dir, "metadata.json"), "w", encoding="utf-8") as f:
                json.dump(result["metadata"], f, indent=2, ensure_ascii=False)
            
            # Save chunk details if chunked
            if total_chunks > 1:
                chunks_dir = os.path.join(output_dir, "chunks")
                os.makedirs(chunks_dir, exist_ok=True)
                for i, chunk_result in enumerate(chunk_results, 1):
                    with open(os.path.join(chunks_dir, f"chunk_{i:03d}.txt"), "w", encoding="utf-8") as f:
                        f.write(chunk_result["merged"])
            
            print(f"\n💾 Results saved to: {output_dir}")
        
        # Print final result
        print("\n" + "="*70)
        print("FINAL TRANSCRIPTION")
        print("="*70)
        # Print first 2000 chars for long transcriptions
        if len(final_text) > 2000:
            print(final_text[:2000])
            print(f"\n... [{len(final_text) - 2000} more characters]")
        else:
            print(final_text)
        
        print(f"\n⏱️  Total processing time: {total_time:.1f} seconds")
        
        return result


def transcribe_sample(sample_name: str):
    """Transcribe a sample from the samples folder"""
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sample_dir = os.path.join(project_root, "samples", sample_name)
    
    # Find audio file
    audio_path = None
    for ext in [".mp3", ".wav", ".m4a", ".ogg", ".flac"]:
        path = os.path.join(sample_dir, f"audio{ext}")
        if os.path.exists(path):
            audio_path = path
            break
    
    if not audio_path:
        print(f"❌ Audio file not found in: {sample_dir}")
        return None
    
    output_dir = os.path.join(sample_dir, "our_result")
    
    transcriber = MedicalTranscriber()
    result = transcriber.transcribe(audio_path, output_dir)
    
    # Evaluate if ground truth exists
    gt_path = os.path.join(sample_dir, "ground_truth.txt")
    if os.path.exists(gt_path):
        print("\n" + "="*70)
        print("EVALUATION")
        print("="*70)
        
        with open(gt_path, "r", encoding="utf-8") as f:
            ground_truth = f.read()
        
        metrics = calculate_all_metrics(ground_truth, result["final_transcription"])
        print(format_metrics_report(metrics))
        
        # Save metrics
        with open(os.path.join(output_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
    
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sample_name = sys.argv[1]
    else:
        sample_name = "sample2"
    
    transcribe_sample(sample_name)
