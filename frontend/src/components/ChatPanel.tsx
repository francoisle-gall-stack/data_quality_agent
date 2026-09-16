import { useState } from "react";
import { Query } from "../api";

export function ChatPanel({ query, chartId }: { query: Query; chartId?: string }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  const formatError = (status: number, body: string) => {
    if (status === 504 || body.includes("504 Gateway Time-out")) {
      return "L’agent met trop de temps à répondre. La passerelle a interrompu la requête avant la fin de l’analyse. Réessayez dans quelques instants.";
    }
    if (status >= 500) {
      return "Le service de l’agent rencontre un problème temporaire. Réessayez dans quelques instants.";
    }
    return "La question n’a pas pu être traitée. Vérifiez la demande puis réessayez.";
  };

  const ask = async () => {
    if (!question.trim() || loading) return;
    const submittedQuestion = question.trim();
    setLoading(true);
    setAnswer("");
    const payload = { question, dashboard_context: { query, chart_id: chartId } };
    try {
      const response = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!response.ok) { setAnswer(formatError(response.status, await response.text())); return; }
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let text = "";
      while (reader) { const { done, value } = await reader.read(); if (done) break; text += decoder.decode(value); setAnswer(text.replace(/^data:\s*/gm, "")); }
      setQuestion("");
    } catch {
      setAnswer(`Impossible de joindre l’agent pour « ${submittedQuestion} ». Vérifiez que le service API est démarré puis réessayez.`);
    } finally {
      setLoading(false);
    }
  };

  return <section className="chat"><div className="chat__intro"><span className="chat__icon">✦</span><div><span className="eyebrow">Analyse augmentée</span><h2>Assistant métier</h2><p className="muted">Interrogez vos indicateurs et vos données en langage naturel.</p></div></div><div className={`answer${loading ? " answer--loading" : ""}`}>{loading ? <><span className="loading-dots" aria-hidden="true"><i /><i /><i /></span><span>L’agent analyse votre question…</span></> : answer || "Exemple : comment est calculé le CA ?"}</div><div className="chat-input"><input value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} placeholder="Posez votre question..." disabled={loading} /><button onClick={ask} disabled={loading}>{loading ? "Analyse…" : <>Envoyer <span>→</span></>}</button></div></section>;
}
