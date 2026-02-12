"""
Pipeline Trace — captures the text state after every step for debugging and UI display.

Usage:
    trace = PipelineTrace()
    trace.add_step("step_1_pure", text, chunk_index=0)
    ...
    trace.save("output/trace.json")
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class StepSnapshot:
    """A snapshot of the text at one point in the pipeline"""
    step_id: str              # e.g. "step_1_pure", "step_5b_spelling"
    step_name: str            # Human-readable: "Pure Transcription"
    text: str                 # Full text at this point
    chunk_index: Optional[int] = None  # None = whole-file step, 0..N = per-chunk
    timestamp: str = ""       # ISO timestamp when step completed
    duration_seconds: float = 0.0  # How long this step took
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extra info (model, params, etc.)

    def char_count(self) -> int:
        return len(self.text)

    def line_count(self) -> int:
        return len(self.text.splitlines())


# Step definitions — order matters for UI display
STEP_DEFINITIONS = [
    ("step_0_chunking",        "Audio Chunking"),
    ("step_1_pure",            "Pure Transcription (no speakers)"),
    ("step_2_diarized",        "Diarized Transcription (with speakers)"),
    ("step_3_merged",          "GPT-5.2 Merge (per chunk)"),
    ("step_4_chunks_merged",   "Chunk Merging"),
    ("step_5a_normalized",     "Post-Process: Normalization"),
    ("step_5b_spelling",       "Post-Process: Spelling Fixes"),
    ("step_5c_deduplicated",   "Post-Process: Deduplication"),
    ("step_5d_semantic",       "Post-Process: Semantic Fix (LLM)"),
    ("step_5e_validated",      "Post-Process: Validation (Final)"),
    ("step_6a_summary_draft",  "Medical Summary: Generation (LLM)"),
    ("step_6b_summary_validation", "Medical Summary: Validation"),
]

STEP_NAME_MAP = dict(STEP_DEFINITIONS)


class PipelineTrace:
    """Accumulates snapshots of every pipeline step for a single transcription run."""

    def __init__(self):
        self.run_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.created_at: str = datetime.now().isoformat()
        self.steps: List[StepSnapshot] = []
        self._step_timers: Dict[str, datetime] = {}

    # -----------------------------------------------------------------
    # Recording
    # -----------------------------------------------------------------

    def start_timer(self, step_id: str):
        """Call before a step begins to track its duration."""
        self._step_timers[step_id] = datetime.now()

    def add_step(
        self,
        step_id: str,
        text: str,
        chunk_index: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record the text state after a pipeline step completes."""
        duration = 0.0
        if step_id in self._step_timers:
            duration = (datetime.now() - self._step_timers.pop(step_id)).total_seconds()

        snapshot = StepSnapshot(
            step_id=step_id,
            step_name=STEP_NAME_MAP.get(step_id, step_id),
            text=text,
            chunk_index=chunk_index,
            timestamp=datetime.now().isoformat(),
            duration_seconds=round(duration, 2),
            metadata=metadata or {},
        )
        self.steps.append(snapshot)

    # -----------------------------------------------------------------
    # Querying
    # -----------------------------------------------------------------

    def get_step(self, step_id: str, chunk_index: Optional[int] = None) -> Optional[StepSnapshot]:
        """Retrieve a specific step snapshot."""
        for s in self.steps:
            if s.step_id == step_id and s.chunk_index == chunk_index:
                return s
        return None

    def get_whole_file_steps(self) -> List[StepSnapshot]:
        """Return only the whole-file (non-chunk) steps in pipeline order."""
        order = [sid for sid, _ in STEP_DEFINITIONS]
        whole = [s for s in self.steps if s.chunk_index is None]
        whole.sort(key=lambda s: order.index(s.step_id) if s.step_id in order else 999)
        return whole

    def get_chunk_steps(self, chunk_index: int) -> List[StepSnapshot]:
        """Return all steps for a specific chunk."""
        return [s for s in self.steps if s.chunk_index == chunk_index]

    def get_num_chunks(self) -> int:
        """How many audio chunks were processed."""
        indices = {s.chunk_index for s in self.steps if s.chunk_index is not None}
        return len(indices)

    # -----------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full trace to a JSON-friendly dict."""
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "num_chunks": self.get_num_chunks(),
            "total_steps": len(self.steps),
            "steps": [
                {
                    "step_id": s.step_id,
                    "step_name": s.step_name,
                    "chunk_index": s.chunk_index,
                    "char_count": s.char_count(),
                    "line_count": s.line_count(),
                    "timestamp": s.timestamp,
                    "duration_seconds": s.duration_seconds,
                    "metadata": s.metadata,
                    "text": s.text,
                }
                for s in self.steps
            ],
        }

    def save(self, output_path: str):
        """Save trace to a JSON file."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "PipelineTrace":
        """Load a trace from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        trace = cls()
        trace.run_id = data["run_id"]
        trace.created_at = data["created_at"]

        for s in data["steps"]:
            trace.steps.append(
                StepSnapshot(
                    step_id=s["step_id"],
                    step_name=s["step_name"],
                    text=s["text"],
                    chunk_index=s.get("chunk_index"),
                    timestamp=s.get("timestamp", ""),
                    duration_seconds=s.get("duration_seconds", 0.0),
                    metadata=s.get("metadata", {}),
                )
            )

        return trace
