// Types matching the FastAPI backend models

export interface RunSummary {
  run_id: string;
  created_at: string;
  num_steps: number;
  num_chunks: number;
  has_audio: boolean;
  audio_filename?: string;
}

export interface StepSummary {
  index: number;
  step_id: string;
  step_name: string;
  chunk_index: number | null;
  char_count: number;
  line_count: number;
  duration_seconds: number;
}

export interface StepDetail extends StepSummary {
  metadata: Record<string, unknown>;
  text: string;
}

export interface TraceData {
  run_id: string;
  created_at: string;
  num_chunks: number;
  total_steps: number;
  steps: StepDetail[];
}

export interface PipelineStep {
  step_id: string;
  step_name: string;
  status: "pending" | "running" | "completed";
}

export interface JobStatus {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  run_id?: string;
  error?: string;
  progress?: string;
  current_step?: string;
  steps: PipelineStep[];
  audio_filename?: string;
}

export interface AdminStatus {
  supervisor_active: boolean;
  backend_pid: number | null;
  frontend_pid: number | null;
}

export interface AudioInfo {
  has_audio: boolean;
  filename: string | null;
}

export interface WordTimestamp {
  word: string;
  start_ms: number;
  end_ms: number;
  speaker: string | null;
  is_interpolated: boolean;
  line_index: number;
}

export interface SummaryReport {
  hallucinated_medications: string[];
  duplicate_medications: string[][];
  suspicious_dosages: string[];
  fabricated_info: string[];
  chief_complaint_ok: boolean;
  chief_complaint_note: string;
  faithfulness_score: number;
  meds_in_transcript: string[];
  meds_in_summary: string[];
  deterministic_duplicate_pairs: string[][];
  deterministic_dosage_warnings: string[];
  validation_passed: boolean;
}

export interface MedicalSummaryData {
  summary: string;
  report: SummaryReport | null;
}
