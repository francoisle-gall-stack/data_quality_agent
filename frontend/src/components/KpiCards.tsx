export function KpiCards({ data }: { data: Record<string, number> }) {
  const cards = [
    ["revenue", "Chiffre d’affaires", (v: number) => `${v.toLocaleString("fr-FR")} €`, "€", "kpi--blue"],
    ["orders", "Commandes", (v: number) => v.toLocaleString("fr-FR"), "↗", "kpi--violet"],
    ["active_customers", "Clients actifs", (v: number) => v.toLocaleString("fr-FR"), "◎", "kpi--green"],
    ["avg_basket", "Panier moyen", (v: number) => `${v.toFixed(2).replace(".", ",")} €`, "⌁", "kpi--orange"],
  ] as const;

  return <div className="kpis">{cards.map(([key, label, format, icon, tone]) => <article className={`kpi ${tone}`} key={key}><div className="kpi__top"><span>{label}</span><span className="kpi__icon">{icon}</span></div><strong>{format(data[key] ?? 0)}</strong><small>Sur la période sélectionnée</small></article>)}</div>;
}
