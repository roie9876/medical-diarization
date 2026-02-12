import { useState } from "react";
import UploadView from "./components/UploadView";
import RunList from "./components/RunList";
import TraceViewer from "./components/TraceViewer";
import AdminPanel from "./components/AdminPanel";
import PipelineProgress from "./components/PipelineProgress";
import "./App.css";

type View =
  | { kind: "home" }
  | { kind: "trace"; runId: string }
  | { kind: "processing"; jobId: string };

function App() {
  const [view, setView] = useState<View>({ kind: "home" });

  if (view.kind === "processing") {
    return (
      <PipelineProgress
        jobId={view.jobId}
        onCompleted={(runId) => setView({ kind: "trace", runId })}
        onBack={() => setView({ kind: "home" })}
      />
    );
  }

  if (view.kind === "trace") {
    return (
      <TraceViewer
        runId={view.runId}
        onBack={() => setView({ kind: "home" })}
        onRerun={(jobId) => setView({ kind: "processing", jobId })}
      />
    );
  }

  return (
    <div className="home">
      <header className="app-header">
        <h1>🏥 Medical Transcription</h1>
        <p className="subtitle">Pipeline Trace Viewer</p>
        <AdminPanel />
      </header>

      <UploadView
        onCompleted={(runId) => setView({ kind: "trace", runId })}
        onProcessing={(jobId) => setView({ kind: "processing", jobId })}
      />

      <RunList
        onSelectRun={(runId) => setView({ kind: "trace", runId })}
        onRerun={(jobId) => setView({ kind: "processing", jobId })}
      />
    </div>
  );
}

export default App;
