import { useEffect, useState } from "react";
import { Filters, get, Query } from "../api";
import { FilterSidebar } from "../components/FilterSidebar";
import { KpiCards } from "../components/KpiCards";
import { ChartPanel } from "../components/ChartPanel";
import { ChatPanel } from "../components/ChatPanel";

export function Dashboard() {
  const [filters, setFilters] = useState<Filters | null>(null);
  const [query, setQuery] = useState<Query>({ start: "", end: "", countries: [], channels: [] });
  const [kpis, setKpis] = useState<Record<string, number>>({});
  const [daily, setDaily] = useState<Record<string, unknown>[]>([]);
  const [country, setCountry] = useState<Record<string, unknown>[]>([]);
  const [channel, setChannel] = useState<Record<string, unknown>[]>([]);
  useEffect(() => { get<Filters>("/api/filters").then((f) => { setFilters(f); setQuery({ start: String(f.min_date).slice(0, 10), end: String(f.max_date).slice(0, 10), countries: f.countries, channels: f.channels }); }); }, []);
  useEffect(() => { if (!query.start) return; Promise.all([get<Record<string, number>[]>("/api/kpis", query), get<Record<string, unknown>[]>("/api/charts/daily-trends", query), get<Record<string, unknown>[]>("/api/charts/by-country", query), get<Record<string, unknown>[]>("/api/charts/by-channel", query)]).then(([k, d, c, ch]) => { setKpis(k[0] || {}); setDaily(d); setCountry(c); setChannel(ch); }); }, [query]);
  if (!filters) return <main className="loading">Chargement…</main>;
  return <div className="layout"><FilterSidebar filters={filters} query={query} setQuery={setQuery} /><main className="content"><header className="page-header"><div><span className="eyebrow">Vue d’ensemble</span><h1>Retail Analytics</h1><p>Explorez la performance commerciale et interrogez vos données.</p></div><div className="header-meta"><span className="live-dot" />Actualisé en direct</div></header><KpiCards data={kpis} /><div className="section-heading"><div><span className="eyebrow">Performance</span><h2>Indicateurs clés</h2></div><span className="muted">Sur la période sélectionnée</span></div><div className="grid"><ChartPanel title="CA quotidien" data={daily} x="order_date" y="revenue" /><ChartPanel title="Commandes quotidiennes" data={daily} x="order_date" y="orders" /><ChartPanel title="CA par pays" data={country} x="country_code" y="revenue" kind="bar" /><ChartPanel title="CA par canal" data={channel} x="channel" y="revenue" kind="bar" /></div><ChatPanel query={query} /></main></div>;
}
