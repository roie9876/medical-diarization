"""
FastAPI backend for Medical Transcription Pipeline Trace UI.

Endpoints:
  GET  /api/runs                    — list all pipeline runs (from output/)
  GET  /api/runs/{run_id}/trace     — get the full trace for a run
  GET  /api/runs/{run_id}/steps     — get step list (without full text, for sidebar)
  GET  /api/runs/{run_id}/step/{step_index} — get a single step's text
  POST /api/upload                  — upload audio and run pipeline (async)
  GET  /api/jobs/{job_id}           — poll job status
"""

import os
import sys
import json
import uuid
import shutil
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Add source to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "medical_transcription"))

app = FastAPI(title="Medical Transcription Trace UI", version="1.0.0")

# CORS for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
OUTPUT_DIR = PROJECT_ROOT / "output"
UPLOAD_DIR = PROJECT_ROOT / "output" / "uploads"
CONTROL_DIR = Path("/tmp/medical_diarization_ctl")

# In-memory job tracker
jobs: dict = {}


# ─── Models ───────────────────────────────────────────────────────────────────

class RunSummary(BaseModel):
    run_id: str
    created_at: str
    num_steps: int
    num_chunks: int
    has_audio: bool
    audio_filename: Optional[str] = None


class StepSummary(BaseModel):
    index: int
    step_id: str
    step_name: str
    chunk_index: Optional[int]
    char_count: int
    line_count: int
    duration_seconds: float


class StepDetail(BaseModel):
    index: int
    step_id: str
    step_name: str
    chunk_index: Optional[int]
    char_count: int
    line_count: int
    duration_seconds: float
    metadata: dict
    text: str


class PipelineStep(BaseModel):
    step_id: str
    step_name: str
    status: str  # "pending", "running", "completed"


class JobStatus(BaseModel):
    job_id: str
    status: str  # "pending", "running", "completed", "failed"
    run_id: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[str] = None
    current_step: Optional[str] = None
    steps: list[PipelineStep] = []
    audio_filename: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def find_trace_files() -> list[tuple[str, Path]]:
    """Find all trace.json files under output/."""
    traces = []
    if not OUTPUT_DIR.exists():
        return traces

    for trace_path in OUTPUT_DIR.rglob("trace.json"):
        # Use parent dir name as run_id
        run_id = trace_path.parent.name
        traces.append((run_id, trace_path))

    return sorted(traces, key=lambda x: x[0], reverse=True)


def load_trace(trace_path: Path) -> dict:
    with open(trace_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/runs", response_model=list[RunSummary])
def list_runs():
    """List all available pipeline runs."""
    runs = []
    for run_id, trace_path in find_trace_files():
        try:
            data = load_trace(trace_path)
            audio_exists = _find_audio_for_run(run_id) is not None
            # Extract original audio filename from metadata.json
            audio_fname = None
            meta_path = trace_path.parent / "metadata.json"
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                    raw = Path(meta.get("audio_path", "")).name  # e.g. 20260212_100303_מפגש2.wav
                    # Strip the timestamp prefix (YYYYMMDD_HHMMSS_)
                    parts = raw.split("_", 2)
                    audio_fname = parts[2] if len(parts) >= 3 else raw
                except Exception:
                    pass
            runs.append(RunSummary(
                run_id=run_id,
                created_at=data.get("created_at", ""),
                num_steps=data.get("total_steps", 0),
                num_chunks=data.get("num_chunks", 0),
                has_audio=audio_exists,
                audio_filename=audio_fname,
            ))
        except Exception:
            continue
    return runs


@app.get("/api/runs/{run_id}/trace")
def get_trace(run_id: str):
    """Get the full trace JSON for a run."""
    for rid, path in find_trace_files():
        if rid == run_id:
            return load_trace(path)
    raise HTTPException(404, f"Run '{run_id}' not found")


@app.get("/api/runs/{run_id}/steps", response_model=list[StepSummary])
def get_steps(run_id: str):
    """Get step list for sidebar (without full text)."""
    for rid, path in find_trace_files():
        if rid == run_id:
            data = load_trace(path)
            return [
                StepSummary(
                    index=i,
                    step_id=s["step_id"],
                    step_name=s["step_name"],
                    chunk_index=s.get("chunk_index"),
                    char_count=s.get("char_count", 0),
                    line_count=s.get("line_count", 0),
                    duration_seconds=s.get("duration_seconds", 0),
                )
                for i, s in enumerate(data.get("steps", []))
            ]
    raise HTTPException(404, f"Run '{run_id}' not found")


@app.get("/api/runs/{run_id}/step/{step_index}", response_model=StepDetail)
def get_step(run_id: str, step_index: int):
    """Get a single step's full text and metadata."""
    for rid, path in find_trace_files():
        if rid == run_id:
            data = load_trace(path)
            steps = data.get("steps", [])
            if 0 <= step_index < len(steps):
                s = steps[step_index]
                return StepDetail(
                    index=step_index,
                    step_id=s["step_id"],
                    step_name=s["step_name"],
                    chunk_index=s.get("chunk_index"),
                    char_count=s.get("char_count", 0),
                    line_count=s.get("line_count", 0),
                    duration_seconds=s.get("duration_seconds", 0),
                    metadata=s.get("metadata", {}),
                    text=s.get("text", ""),
                )
            raise HTTPException(404, f"Step index {step_index} out of range")
    raise HTTPException(404, f"Run '{run_id}' not found")


# Pipeline step definitions (mirrors trace.py STEP_DEFINITIONS)
PIPELINE_STEP_DEFS = [
    ("step_0_chunking",        "Audio Chunking"),
    ("step_1_pure",            "Pure Transcription"),
    ("step_2_diarized",        "Diarized Transcription"),
    ("step_3_merged",          "GPT Merge (per chunk)"),
    ("step_4_chunks_merged",   "Chunk Merging"),
    ("step_5a_normalized",     "Normalization"),
    ("step_5b_spelling",       "Spelling Fixes"),
    ("step_5c_deduplicated",   "Deduplication"),
    ("step_5d_semantic",       "Semantic Fix (LLM)"),
    ("step_5e_validated",      "Validation (Final)"),
    ("step_6a_summary_draft",  "Medical Summary (LLM)"),
    ("step_6b_summary_validation", "Summary Validation"),
]


def _init_job_steps() -> list[dict]:
    return [{"step_id": sid, "step_name": sn, "status": "pending"} for sid, sn in PIPELINE_STEP_DEFS]


def _update_job_step(job_id: str, step_id: str, status: str):
    """Mark a step as running/completed in the job tracker."""
    if job_id not in jobs:
        return
    for step in jobs[job_id]["steps"]:
        if step["step_id"] == step_id:
            step["status"] = status
            break
    if status == "running":
        jobs[job_id]["current_step"] = step_id
        # Find the step name
        for sid, sname in PIPELINE_STEP_DEFS:
            if sid == step_id:
                jobs[job_id]["progress"] = f"Running: {sname}"
                break


def _run_pipeline(job_id: str, audio_path: str, output_dir: str):
    """Background task: run the transcription pipeline."""
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["progress"] = "Starting pipeline..."

        from transcribe import MedicalTranscriber
        transcriber = MedicalTranscriber()

        # Hook into the trace system to report progress in real-time
        import trace as trace_module
        _orig_add_step = trace_module.PipelineTrace.add_step

        def _hooked_add_step(self, step_id, text, **kwargs):
            # Mark previous as completed, current as running
            for s in jobs.get(job_id, {}).get("steps", []):
                if s["status"] == "running":
                    s["status"] = "completed"
            _update_job_step(job_id, step_id, "running")
            return _orig_add_step(self, step_id, text, **kwargs)

        # Monkey-patch for this run
        trace_module.PipelineTrace.add_step = _hooked_add_step
        try:
            transcriber.transcribe(audio_path, output_dir)
        finally:
            # Restore original method
            trace_module.PipelineTrace.add_step = _orig_add_step

        # Mark all remaining as completed
        for s in jobs[job_id]["steps"]:
            s["status"] = "completed"

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["run_id"] = Path(output_dir).name
        jobs[job_id]["progress"] = "Done"
        jobs[job_id]["current_step"] = None
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


@app.post("/api/upload")
async def upload_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload an audio file and start the pipeline."""
    # Save uploaded file
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = file.filename.replace(" ", "_") if file.filename else "audio.mp3"
    audio_path = UPLOAD_DIR / f"{timestamp}_{safe_name}"

    with open(audio_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Create output directory for this run
    run_output_dir = OUTPUT_DIR / timestamp

    # Create job
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "pending",
        "run_id": None,
        "error": None,
        "progress": "Uploaded, queued for processing",
        "current_step": None,
        "steps": _init_job_steps(),
        "audio_filename": safe_name,
    }

    # Start pipeline in background
    background_tasks.add_task(_run_pipeline, job_id, str(audio_path), str(run_output_dir))

    return {"job_id": job_id, "message": "Pipeline started"}


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
def get_job_status(job_id: str):
    """Poll job status."""
    if job_id not in jobs:
        raise HTTPException(404, f"Job '{job_id}' not found")
    job = jobs[job_id]
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        run_id=job.get("run_id"),
        error=job.get("error"),
        progress=job.get("progress"),
        current_step=job.get("current_step"),
        steps=[PipelineStep(**s) for s in job.get("steps", [])],
        audio_filename=job.get("audio_filename"),
    )


@app.post("/api/rerun/{run_id}")
async def rerun_pipeline(run_id: str, background_tasks: BackgroundTasks):
    """Re-run the pipeline on the same audio file as an existing run."""
    audio_path = _find_audio_for_run(run_id)
    if not audio_path:
        raise HTTPException(404, f"No audio file found for run '{run_id}' — cannot re-run")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = OUTPUT_DIR / timestamp

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "pending",
        "run_id": None,
        "error": None,
        "progress": "Re-run queued",
        "current_step": None,
        "steps": _init_job_steps(),
        "audio_filename": audio_path.name,
    }

    background_tasks.add_task(_run_pipeline, job_id, str(audio_path), str(run_output_dir))

    return {"job_id": job_id, "message": f"Re-running pipeline on {audio_path.name}"}


# ─── Audio serving ────────────────────────────────────────────────────────────

def _find_audio_for_run(run_id: str) -> Optional[Path]:
    """Find the audio file associated with a run, checking metadata.json first."""
    for rid, trace_path in find_trace_files():
        if rid == run_id:
            run_dir = trace_path.parent
            # Check metadata.json for original audio path
            meta_path = run_dir / "metadata.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    audio_path = meta.get("audio_path", "")
                    if audio_path and Path(audio_path).exists():
                        return Path(audio_path)
                except Exception:
                    pass
            # Fallback: look for audio files in run dir and uploads
            for ext in ("mp3", "wav", "m4a", "flac", "ogg"):
                for candidate in run_dir.glob(f"*.{ext}"):
                    return candidate
            # Check uploads dir with run_id timestamp prefix
            if UPLOAD_DIR.exists():
                for candidate in UPLOAD_DIR.glob(f"{run_id}*"):
                    if candidate.suffix.lower() in (".mp3", ".wav", ".m4a", ".flac", ".ogg"):
                        return candidate
            break
    return None


@app.get("/api/runs/{run_id}/audio")
def get_run_audio(run_id: str):
    """Stream the audio file associated with a pipeline run."""
    audio_path = _find_audio_for_run(run_id)
    if not audio_path:
        raise HTTPException(404, f"No audio file found for run '{run_id}'")
    media_types = {
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
        ".flac": "audio/flac", ".ogg": "audio/ogg",
    }
    media_type = media_types.get(audio_path.suffix.lower(), "audio/mpeg")
    return FileResponse(audio_path, media_type=media_type, filename=audio_path.name)


@app.get("/api/runs/{run_id}/has-audio")
def check_run_audio(run_id: str):
    """Check if audio exists for a run (lightweight, no streaming)."""
    audio_path = _find_audio_for_run(run_id)
    return {"has_audio": audio_path is not None, "filename": audio_path.name if audio_path else None}


@app.get("/api/runs/{run_id}/word-timestamps")
def get_word_timestamps(run_id: str):
    """Get word-level timestamps for audio-text sync."""
    for rid, trace_path in find_trace_files():
        if rid == run_id:
            ts_path = trace_path.parent / "word_timestamps.json"
            if ts_path.exists():
                with open(ts_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            raise HTTPException(404, f"No word timestamps for run '{run_id}'")
    raise HTTPException(404, f"Run '{run_id}' not found")


@app.get("/api/runs/{run_id}/medical-summary")
def get_medical_summary(run_id: str):
    """Get the medical summary for a pipeline run."""
    for rid, trace_path in find_trace_files():
        if rid == run_id:
            run_dir = trace_path.parent
            summary_path = run_dir / "medical_summary.txt"
            report_path = run_dir / "summary_report.json"
            result = {"summary": None, "report": None}
            if summary_path.exists():
                result["summary"] = summary_path.read_text(encoding="utf-8")
            if report_path.exists():
                result["report"] = json.loads(report_path.read_text(encoding="utf-8"))
            if result["summary"] is None:
                raise HTTPException(404, f"No medical summary for run '{run_id}'")
            return result
    raise HTTPException(404, f"Run '{run_id}' not found")


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str):
    """Delete a pipeline run and its output directory."""
    for rid, trace_path in find_trace_files():
        if rid == run_id:
            run_dir = trace_path.parent
            # Also remove associated uploaded audio
            audio_path = _find_audio_for_run(run_id)
            shutil.rmtree(run_dir)
            if audio_path and audio_path.exists() and UPLOAD_DIR in audio_path.parents:
                audio_path.unlink(missing_ok=True)
                # Remove .stt.wav if it was generated
                stt_wav = audio_path.with_suffix(".stt.wav")
                if stt_wav.exists():
                    stt_wav.unlink(missing_ok=True)
            return {"status": "deleted", "run_id": run_id}
    raise HTTPException(404, f"Run '{run_id}' not found")


# ─── Admin / restart ──────────────────────────────────────────────────────────

@app.post("/api/admin/restart-backend")
def restart_backend():
    """Signal the run_all.sh supervisor to restart the backend."""
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    (CONTROL_DIR / "restart-backend").touch()
    return {"status": "restart-backend signal sent"}


@app.post("/api/admin/restart-frontend")
def restart_frontend():
    """Signal the run_all.sh supervisor to restart the frontend."""
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    (CONTROL_DIR / "restart-frontend").touch()
    return {"status": "restart-frontend signal sent"}


@app.get("/api/admin/status")
def admin_status():
    """Check if the supervisor control directory is available."""
    backend_pid = None
    frontend_pid = None
    try:
        bp = CONTROL_DIR / "backend.pid"
        fp = CONTROL_DIR / "frontend.pid"
        if bp.exists():
            backend_pid = int(bp.read_text().strip())
        if fp.exists():
            frontend_pid = int(fp.read_text().strip())
    except Exception:
        pass
    return {
        "supervisor_active": CONTROL_DIR.exists(),
        "backend_pid": backend_pid,
        "frontend_pid": frontend_pid,
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "output_dir": str(OUTPUT_DIR)}
