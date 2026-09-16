import { useEffect, useState } from "react";

type Scenario = { scenario_id: string; name: string; description: string };
type PipelineRun = {
  run_id: string;
  scenario_id: string;
  status: string;
  incident_id?: string;
  error?: string;
  record?: {
    status: string;
    diagnostic: { command_executed: string; failed_nodes: unknown[] };
    investigation_output: string;
    correction_output: string;
    patch?: { file_path: string; summary: string; diff_unified: string };
    validation_passed?: boolean;
    pr_url?: string;
  };
};

const statusLabels: Record<string, string> = {
  queued: "En attente",
  running: "Pipeline en cours",
  investigating: "Investigation en cours",
  investigated: "Investigation terminée",
  awaiting_approval: "En attente d’approbation",
  fixing: "Application du correctif",
  resolved: "Résolu",
  pr_created: "Pull request créée",
  needs_human: "Revue humaine nécessaire",
  completed: "Terminé",
  error: "Erreur",
};

export function DbtFailurePipeline() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useState("");
  const [reset, setReset] = useState(true);
  const [run, setRun] = useState<PipelineRun | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("/api/dbt-failure/scenarios").then((response) => response.json()).then((items: Scenario[]) => {
      setScenarios(items);
      setScenarioId(items[0]?.scenario_id || "");
    });
  }, []);

  useEffect(() => {
    if (!run || ["awaiting_approval", "completed", "resolved", "pr_created", "needs_human", "error"].includes(run.status)) return;
    const timer = window.setInterval(() => {
      fetch(`/api/dbt-failure/runs/${run.run_id}`).then((response) => response.json()).then(setRun);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [run]);

  const launch = async () => {
    setLoading(true);
    setRun(null);
    const response = await fetch("/api/dbt-failure/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario_id: scenarioId, reset_before_activate: reset }),
    });
    setRun(await response.json());
    setLoading(false);
  };

  const approve = async () => {
    if (!run) return;
    setLoading(true);
    const response = await fetch(`/api/dbt-failure/runs/${run.run_id}/approve`, { method: "POST" });
    setRun(await response.json());
    setLoading(false);
  };

  const record = run?.record;
  return <main className="pipeline-page">
    <header className="pipeline-header">
      <a className="back-link" href="/">← Retour au dashboard</a>
      <span className="eyebrow">Agentic dbt Failure Investigator</span>
      <h1>Investigation d’un échec dbt</h1>
      <p className="muted">Cette page reprend les étapes et les sorties de l’application Streamlit.</p>
    </header>
    <section className="pipeline-controls">
      <label>Scénario<select value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}>{scenarios.map((scenario) => <option key={scenario.scenario_id} value={scenario.scenario_id}>{scenario.scenario_id} — {scenario.name}</option>)}</select></label>
      <label className="pipeline-check"><input type="checkbox" checked={reset} onChange={(event) => setReset(event.target.checked)} /> Réinitialiser avant activation</label>
      <button onClick={launch} disabled={!scenarioId || loading}> {loading ? "Pipeline en cours…" : "Lancer le pipeline"} </button>
    </section>
    {run && <section className="pipeline-result">
      <div className="pipeline-status"><strong>{statusLabels[run.status] || run.status}</strong><span>{run.incident_id || run.run_id}</span></div>
      {run.error && <div className="pipeline-error">{run.error}</div>}
      {record && <>
        <details open><summary>Diagnostic</summary><pre>{JSON.stringify(record.diagnostic, null, 2)}</pre></details>
        <details open><summary>Investigation</summary><div className="pipeline-output">{record.investigation_output || "(not run)"}</div></details>
        <details open><summary>Proposed patch</summary>{record.patch ? <><p><strong>{record.patch.summary}</strong></p><p className="muted">Fichier : {record.patch.file_path}</p><pre>{record.patch.diff_unified}</pre></> : <div className="pipeline-output">{record.correction_output || "(no patch yet)"}</div>}</details>
        {run.status === "awaiting_approval" && record.patch && <button className="pipeline-approve" onClick={approve} disabled={loading}>Approuver et appliquer le correctif</button>}
        {record.pr_url && <a className="pipeline-pr" href={record.pr_url} target="_blank" rel="noreferrer">Ouvrir la pull request</a>}
      </>}
    </section>}
  </main>;
}
