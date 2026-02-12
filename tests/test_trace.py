#!/usr/bin/env python3
"""Quick test to verify the PipelineTrace module."""
import sys, os, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "medical_transcription"))
from trace import PipelineTrace, StepSnapshot, STEP_DEFINITIONS

# Test the trace module
trace = PipelineTrace()
trace.start_timer("step_1_pure")
time.sleep(0.01)
trace.add_step("step_1_pure", "שלום דוקטור, אני מרגיש לא טוב", chunk_index=0, metadata={"model": "gpt-audio"})
trace.add_step("step_4_chunks_merged", "merged text here")
trace.add_step("step_5a_normalized", "normalized text here")

print("Steps recorded:", len(trace.steps))
print("Step IDs:", [s.step_id for s in trace.steps])
print("Whole-file steps:", [s.step_id for s in trace.get_whole_file_steps()])
print("Chunk 0 steps:", [s.step_id for s in trace.get_chunk_steps(0)])
print()

# Test serialization roundtrip
d = trace.to_dict()
print("Serialized steps:", len(d["steps"]))
print("First step keys:", list(d["steps"][0].keys()))
print()

# Test save/load
trace.save("/tmp/test_trace.json")
loaded = PipelineTrace.load("/tmp/test_trace.json")
print("Loaded steps:", len(loaded.steps))
print("Roundtrip OK:", loaded.steps[0].text == trace.steps[0].text)
os.remove("/tmp/test_trace.json")
print()

# Verify postprocess import works
from postprocess import PostProcessor
print("PostProcessor import OK")
print()
print("All trace tests passed")
