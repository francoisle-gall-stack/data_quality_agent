import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Overlay = { date_start?: string; date_end?: string; label: string; severity: string };
const formatValue = (value: unknown) => typeof value === "number" ? value.toLocaleString("fr-FR") : String(value ?? "—");

function AnomalyLabel({ viewBox, value }: { viewBox?: { x?: number; y?: number; width?: number }; value: string }) {
  const x = (viewBox?.x ?? 0) + (viewBox?.width ?? 0) / 2;
  const y = viewBox?.y ?? 0;
  return (
    <g className="anomaly-label" transform={`translate(${x}, ${y + 10})`}>
      <circle className="anomaly-label__dot" r="5" />
      <foreignObject className="anomaly-label__tooltip" x="-100" y="10" width="200" height="48">
        <div>{value}</div>
      </foreignObject>
    </g>
  );
}

export function ChartPanel({ title, data, x, y, kind = "line", overlays = [] }: { title: string; data: Record<string, unknown>[]; x: string; y: string; kind?: "line" | "bar"; overlays?: Overlay[] }) {
  const Chart = kind === "bar" ? BarChart : LineChart;
  return (
    <section className="chart">
      <div className="chart__header">
        <div>
          <span className="eyebrow">Tendance</span>
          <h2>{title}</h2>
        </div>
        {overlays.length > 0 && <span className="status-pill status-pill--warning"><span className="status-dot" />{overlays.length} anomalie{overlays.length > 1 ? "s" : ""}</span>}
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <Chart data={data} margin={{ top: 12, right: 12, left: -12, bottom: 4 }}>
          <CartesianGrid vertical={false} stroke="#e7edf5" />
          <XAxis dataKey={x} axisLine={false} tickLine={false} tick={{ fill: "#8995a7", fontSize: 11 }} />
          <YAxis axisLine={false} tickLine={false} tick={{ fill: "#8995a7", fontSize: 11 }} tickFormatter={formatValue} />
          <Tooltip
            cursor={{ fill: "#edf4ff" }}
            contentStyle={{ border: "1px solid #dce5f0", borderRadius: 12, boxShadow: "0 12px 30px rgba(26, 43, 72, .12)", fontSize: 12 }}
            labelStyle={{ color: "#536176", fontWeight: 700, marginBottom: 4 }}
            formatter={(value) => [formatValue(value), title]}
          />
          {kind === "line" ? <Line type="monotone" dataKey={y} stroke="#4d7cff" strokeWidth={3} dot={false} activeDot={{ r: 5, fill: "#4d7cff", stroke: "#fff", strokeWidth: 3 }} /> : <Bar dataKey={y} fill="#4d7cff" radius={[5, 5, 0, 0]} maxBarSize={34} />}
          {overlays.map((o, i) => o.date_start && (
            <ReferenceArea
              key={`${o.date_start}-${i}`}
              x1={o.date_start}
              x2={o.date_end || o.date_start}
              fill={o.severity === "critical" ? "#ef6a78" : "#f5b94c"}
              fillOpacity={0.12}
              stroke={o.severity === "critical" ? "#ef6a78" : "#f5b94c"}
              strokeOpacity={0.42}
              label={<AnomalyLabel value={o.label} />}
            />
          ))}
        </Chart>
      </ResponsiveContainer>
      {overlays.length > 0 && <div className="chart__legend"><span className="legend-swatch" />Zone d’anomalie — survolez le point pour le détail</div>}
    </section>
  );
}
