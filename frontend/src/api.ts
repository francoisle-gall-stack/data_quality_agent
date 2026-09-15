export type Filters = { min_date: string; max_date: string; countries: string[]; channels: string[] };
export type Query = { start: string; end: string; countries: string[]; channels: string[] };
const params = (q: Query) => {
  const result = new URLSearchParams({ start: q.start, end: q.end });
  q.countries.forEach((v) => result.append("countries", v));
  q.channels.forEach((v) => result.append("channels", v));
  return result;
};
export async function get<T>(path: string, q?: Query): Promise<T> { const response = await fetch(`${path}${q ? `?${params(q)}` : ""}`); if (!response.ok) throw new Error(await response.text()); return response.json(); }
