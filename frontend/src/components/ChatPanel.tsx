import { useState } from "react";
import { Query } from "../api";

export function ChatPanel({ query, chartId }: { query: Query; chartId?: string }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  const ask = async () => {
    if (!question.trim()) return;
    const payload = { question, dashboard_context: { query, chart_id: chartId } };
    try {
      const response = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!response.ok) { setAnswer(await response.text()); return; }
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let text = "";
      while (reader) { const { done, value } = await reader.read(); if (done) break; text += decoder.decode(value); setAnswer(text.replace(/^data:\s*/gm, "")); }
      setQuestion("");
    } catch {
      setAnswer("Erreur lors de l'appel de l'agent.");
    }
  };

  return <section className="chat"><div className="chat__intro"><span className="chat__icon">✦</span><div><span className="eyebrow">Analyse augmentée</span><h2>Assistant métier</h2><p className="muted">Interrogez vos indicateurs et vos données en langage naturel.</p></div></div><div className="answer">{answer || "Exemple : comment est calculé le CA ?"}</div><div className="chat-input"><input value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} placeholder="Posez votre question..." /><button onClick={ask}>Envoyer <span>→</span></button></div></section>;
}
