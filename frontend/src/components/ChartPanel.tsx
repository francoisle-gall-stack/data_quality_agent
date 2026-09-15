import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const formatValue = (value: unknown) => typeof value === "number" ? value.toLocaleString("fr-FR") : String(value ?? "—");

export function ChartPanel({ title, data, x, y, kind = "line" }: { title: string; data: Record<string, unknown>[]; x: string; y: string; kind?: "line" | "bar" }) {
  const Chart = kind === "bar" ? BarChart : LineChart;
  return (
    <section className="chart">
      <div className="chart__header">
        <div>
          <span className="eyebrow">Tendance</span>
          <h2>{title}</h2>
        </div>
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
        </Chart>
      </ResponsiveContainer>
    </section>
  );
}
