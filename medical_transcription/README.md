# Medical Transcription System

Hebrew medical conversation transcription with speaker diarization using Azure OpenAI.

## 🎯 What It Does

Transcribes Hebrew medical conversations (doctor-patient dialogues) with:
- **Speaker diarization**: Identifies who said what ([רופא], [מטופל], [בן משפחה])
- **Medical terminology**: Keeps medical terms in English (DVT, CT, TEE, etc.)
- **Long audio support**: Handles files up to 20+ minutes by chunking
- **Spelling correction**: Fixes common Hebrew transcription errors

## 🔄 Processing Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AUDIO INPUT                                  │
│                    (MP3, WAV, M4A, etc.)                            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STEP 0: AUDIO CHUNKING                           │
│         (If > 4 minutes, split into 4-min chunks with overlap)      │
└─────────────────────────────────────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
      ┌─────────┐         ┌─────────┐         ┌─────────┐
      │ Chunk 1 │         │ Chunk 2 │   ...   │ Chunk N │
      └─────────┘         └─────────┘         └─────────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                │
                    FOR EACH CHUNK:
                                │
            ┌───────────────────┴───────────────────┐
            │                                       │
            ▼                                       ▼
┌─────────────────────────┐         ┌─────────────────────────┐
│   STEP 1: GPT-Audio     │         │   STEP 2: GPT-Audio     │
│   Pure Transcription    │         │   With Diarization      │
│   (No speaker labels)   │         │   (Speaker labels)      │
│   Focus: Text accuracy  │         │   Focus: Who said what  │
└─────────────────────────┘         └─────────────────────────┘
            │                                       │
            └───────────────────┬───────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STEP 3: GPT-5.2 MERGE                            │
│         Combine accurate text + correct speaker identification      │
│         Medical terms → English | Speaker labels → Hebrew           │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                STEP 4: MERGE ALL CHUNKS                             │
│         Algorithmic overlap detection (no content loss)             │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                STEP 5: SPELLING CORRECTION                          │
│         GPT-5.2 fixes Hebrew spelling/semantic errors               │
│         Examples: עזות→הזעות, עקומול→אקמול, הרמונית→ערמונית        │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       FINAL OUTPUT                                   │
│                  final_transcription.txt                            │
└─────────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure
```
medical diarization/
├── .env                      # API keys (see below)
├── samples/                  # Audio samples
│   ├── sample1/
│   │   ├── audio.mp3         # 19 min audio
│   │   ├── ground_truth.txt  # Human transcription
│   │   └── our_result/
│   │       ├── final_transcription.txt
│   │       ├── metadata.json
│   │       └── chunks/       # Individual chunk results
│   └── sample2/
│       └── ...
└── medical_transcription/    # Code
    ├── transcribe.py         # Main transcription script
    ├── evaluation.py         # Metrics and evaluation
    └── README.md             # This file
```

## ⚙️ Configuration

### Environment Variables (.env)
```
# GPT-Audio (for transcription)
ENDPOINT_URL=https://your-endpoint.openai.azure.com/
DEPLOYMENT_NAME=gpt-audio
AZURE_OPENAI_API_KEY=your-key-here

# GPT-5.2 (for merging and spelling correction)
GPT52_ENDPOINT=https://your-gpt52-endpoint.openai.azure.com/
GPT52_KEY=your-gpt52-key-here
GPT52_DEPLOYMENT=gpt-5.2-chat
```

### Audio Chunking Settings
```python
MAX_CHUNK_DURATION_MS = 4 * 60 * 1000  # 4 minutes
OVERLAP_DURATION_MS = 30 * 1000        # 30 seconds overlap
```

## 🚀 Usage

### Transcribe a sample
```bash
cd "medical diarization"
python medical_transcription/transcribe.py sample1
```

### Transcribe a new audio file
```python
from medical_transcription.transcribe import MedicalTranscriber

transcriber = MedicalTranscriber()
result = transcriber.transcribe("path/to/audio.mp3", "output/folder")

print(result["final_transcription"])
print(f"Duration: {result['metadata']['duration_minutes']:.1f} min")
print(f"Chunks: {result['metadata']['num_chunks']}")
```

### Add a new sample
1. Create folder: `samples/sample3/`
2. Add audio file: `samples/sample3/audio.mp3`
3. (Optional) Add ground truth: `samples/sample3/ground_truth.txt`
4. Run: `python medical_transcription/transcribe.py sample3`

## 🏷️ Speaker Labels
| Label | Hebrew | Description |
|-------|--------|-------------|
| `[רופא]` | Doctor | Asks medical questions |
| `[מטופל]` | Patient | Answers about their condition |
| `[בן משפחה]` | Family | Accompanying person |

## 🏥 Medical Terms (kept in English)
- Diagnoses: DVT, PE, IgG4
- Tests: CT, PET-CT, TEE, Ultrasound, MRI, ECG
- Medications: Euthyrox, Lipitor, Multaq
- Procedures: ביופסיה (biopsy), אנדוקרדיטיס (endocarditis)

## 📊 Performance
| Metric | Sample 1 (19 min) | Sample 2 (2.5 min) |
|--------|-------------------|---------------------|
| Processing Time | ~3.5 min | ~30 sec |
| Chunks | 6 | 1 |
| Word Accuracy | ~64% | ~58% |

## 🔧 Spelling Corrections
The system automatically fixes common GPT-Audio errors in Hebrew:

| Error | Correction |
|-------|------------|
| עזות | הזעות |
| עקומול | אקמול |
| תחילות | בחילות |
| הרמונית | ערמונית |
| מייחה | ליחה |
| מערך העצם | מח העצם |
| בליסה | בלעיסה |
| העתק עדבק | העתק הדבק |

## 📝 Output Files
- `final_transcription.txt` - The complete corrected transcription
- `metadata.json` - Processing info (duration, chunks, timestamp)
- `chunks/` - Individual chunk transcriptions (for long audio)
- `metrics.json` - Evaluation metrics (if ground_truth exists)

## Adding New Samples

1. Create folder: `samples/sample_name/`
2. Add audio file: `audio.mp3`
3. Add ground truth (optional): `ground_truth.txt`
4. Run: `python transcribe.py sample_name`
