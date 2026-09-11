"""Generate an interactive, local HTML MCD for the dbt mart layer."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"
OUTPUT = ROOT / "dbt" / "target" / "marts_mcd.html"


def _columns_from_sql(sql_path: Path) -> list[dict[str, str]]:
    """Extract the selected column names from a simple mart SELECT statement."""
    sql = sql_path.read_text(encoding="utf-8")
    match = re.search(r"\bselect\b(.*?)\bfrom\b", sql, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return []

    columns = []
    for expression in match.group(1).split(","):
        expression = expression.strip()
        if not expression:
            continue
        alias = re.search(r"\bas\s+([a-zA-Z_][\w]*)\s*$", expression, re.IGNORECASE)
        name = alias.group(1) if alias else expression.split(".")[-1].strip()
        name = re.sub(r"\W+$", "", name)
        kind = "measure" if re.search(
            r"\b(count|sum|avg|min|max)\s*\(", expression, re.IGNORECASE
        ) else "attribute"
        columns.append({"name": name, "kind": kind})
    return columns


def _load_models() -> list[dict]:
    if not MANIFEST.exists():
        raise FileNotFoundError(
            f"Manifest absent: {MANIFEST}. Lance d'abord `dbt build --project-dir dbt --profiles-dir dbt`."
        )

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    models = []
    for node in manifest.get("nodes", {}).values():
        path = node.get("original_file_path", "").replace("\\", "/")
        if node.get("resource_type") != "model" or "models/2_marts/" not in path:
            continue
        sql_path = ROOT / "dbt" / path
        columns = _columns_from_sql(sql_path) if sql_path.exists() else [
            {"name": name, "kind": "attribute"} for name in node.get("columns", {})
        ]
        name = node["name"]
        expected_keys = {
            "dim_customers": "customer_id",
            "dim_products": "product_id",
            "dim_stores": "store_id",
            "fct_orders": "order_id",
            "fct_daily_sales": "order_date",
        }
        key = next((c["name"] for c in columns if c["name"] == expected_keys.get(name)), None)
        if not key:
            key = next((c["name"] for c in columns if c["name"].endswith("_id")), None)
        models.append(
            {
                "id": name,
                "name": name,
                "layer": "mart",
                "description": node.get("description") or "Description non documentée",
                "path": path,
                "columns": [
                    {
                        **column,
                        "role": (
                            "PK"
                            if column["name"] == key
                            else "measure"
                            if column["kind"] == "measure"
                            else "attribute"
                        ),
                    }
                    for column in columns
                ],
                "grain": "1 ligne par date" if name == "fct_daily_sales" else (
                    "1 ligne par commande" if name == "fct_orders" else "1 ligne par entité"
                ),
            }
        )
    return sorted(models, key=lambda model: model["name"])


def _make_graph(models: list[dict]) -> dict:
    names = {model["name"] for model in models}
    edges = []
    for source, target, source_column, target_column, cardinality in [
        ("dim_customers", "fct_orders", "customer_id", "customer_id", "1 — N"),
        ("dim_stores", "fct_orders", "store_id", "store_id", "1 — N"),
        ("fct_orders", "fct_daily_sales", "order_date", "order_date", "N — 1"),
    ]:
        if source in names and target in names:
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "sourceColumn": source_column,
                    "targetColumn": target_column,
                    "cardinality": cardinality,
                }
            )
    return {"models": models, "edges": edges}


HTML = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MCD — marts dbt</title>
<style>
:root{color-scheme:dark;--bg:#0f172a;--panel:#172033;--panel2:#202d44;--text:#e5edf9;--muted:#91a4bf;--line:#49617e;--accent:#64d8cb;--measure:#f4b860;--pk:#ff7b9c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px system-ui,-apple-system,Segoe UI,sans-serif;height:100vh;overflow:hidden}
header{height:72px;padding:14px 20px;background:#111c30;border-bottom:1px solid #263750;display:flex;align-items:center;gap:20px}
h1{font-size:19px;margin:0;white-space:nowrap}header p{color:var(--muted);margin:3px 0 0;font-size:12px}
.tools{margin-left:auto;display:flex;gap:8px;align-items:center}input,button{border:1px solid #3b506e;border-radius:7px;background:var(--panel);color:var(--text);padding:8px 10px}input{width:220px}button{cursor:pointer}button:hover{border-color:var(--accent)}
main{height:calc(100vh - 72px);display:flex}.canvas{position:relative;flex:1;overflow:hidden;background-image:linear-gradient(#1a2940 1px,transparent 1px),linear-gradient(90deg,#1a2940 1px,transparent 1px);background-size:32px 32px}
svg{width:100%;height:100%;cursor:grab}svg:active{cursor:grabbing}.edge{stroke:var(--line);stroke-width:2;fill:none}.edge.active{stroke:var(--accent);stroke-width:3}.edge-label{fill:var(--muted);font-size:12px;text-anchor:middle}.edge-label.active{fill:var(--accent)}
.table{fill:var(--panel);stroke:var(--line);stroke-width:1.5;rx:10}.table.active{stroke:var(--accent);stroke-width:2.5}.table.dimmed{opacity:.22}.table-title{fill:var(--text);font-size:15px;font-weight:700}.table-meta{fill:var(--muted);font-size:11px}.column{fill:var(--text);font-size:12px}.column.pk{fill:var(--pk);font-weight:700}.column.measure{fill:var(--measure)}.column.fk{fill:var(--accent)}
.side{width:320px;background:#111c30;border-left:1px solid #263750;padding:18px;overflow:auto}.side h2{font-size:16px;margin:0 0 8px}.side h3{font-size:12px;text-transform:uppercase;color:var(--muted);margin:20px 0 7px}.hint{color:var(--muted);line-height:1.5}.badge{display:inline-block;border-radius:10px;padding:3px 7px;margin:2px 3px 2px 0;background:var(--panel2);font-size:11px}.badge.pk{color:var(--pk)}.badge.measure{color:var(--measure)}.badge.fk{color:var(--accent)}.relation{border-left:2px solid var(--accent);padding:7px 9px;margin:7px 0;background:var(--panel);font-size:12px}.legend{position:absolute;bottom:15px;left:15px;background:#111c30dd;padding:8px 10px;border:1px solid #263750;border-radius:7px;color:var(--muted);font-size:11px}
@media(max-width:850px){.side{width:260px}header p{display:none}input{width:150px}}
</style>
</head>
<body>
<header><div><h1>MCD — marts dbt</h1><p>Généré depuis dbt/target/manifest.json · clés et relations inférées</p></div><div class="tools"><input id="search" placeholder="Rechercher un modèle…"><button id="reset">Réinitialiser</button></div></header>
<main><section class="canvas" id="canvas"><svg id="diagram" viewBox="0 0 1120 720" role="img" aria-label="Modèle conceptuel des données mart"></svg><div class="legend"><span style="color:var(--pk)">● PK</span> &nbsp; <span style="color:var(--accent)">● FK / relation</span> &nbsp; <span style="color:var(--measure)">● mesure</span></div></section><aside class="side" id="details"><h2>Sélectionne une table</h2><p class="hint">Clique sur une table pour afficher son grain, ses colonnes et ses relations. Utilise la recherche pour isoler un modèle.</p></aside></main>
<script>
const graph=__GRAPH__;
const svg=document.querySelector("#diagram"), details=document.querySelector("#details"), search=document.querySelector("#search");
const positions={dim_customers:[55,75],dim_products:[55,365],dim_stores:[55,560],fct_orders:[430,210],fct_daily_sales:[790,300]};
const nodeSize={w:285,row:24,head:58};
let selected=null, query="";
const NS="http://www.w3.org/2000/svg";
function el(tag,attrs={},text=""){const n=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));if(text)n.textContent=text;return n}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]))}
function model(name){return graph.models.find(m=>m.name===name)}
function render(){
 svg.replaceChildren(); const g=el("g",{id:"world"}); svg.append(g);
 graph.edges.forEach(edge=>{const [sx,sy]=positions[edge.source], [tx,ty]=positions[edge.target];const x1=sx+nodeSize.w,y1=sy+nodeSize.head+nodeSize.row*2,x2=tx,y2=ty+nodeSize.head+nodeSize.row*2;const path=el("path",{d:`M ${x1} ${y1} C ${(x1+x2)/2} ${y1}, ${(x1+x2)/2} ${y2}, ${x2} ${y2}`,class:"edge "+(selected&&(selected===edge.source||selected===edge.target)?"active":"")});g.append(path);g.append(el("text",{x:(x1+x2)/2,y:(y1+y2)/2-7,class:"edge-label "+(selected&&(selected===edge.source||selected===edge.target)?"active":"")},`${edge.cardinality} · ${edge.sourceColumn}`))});
 graph.models.forEach(m=>{const [x,y]=positions[m.name];const visible=!query||m.name.toLowerCase().includes(query.toLowerCase());const active=selected===m.name;const group=el("g",{class:"model "+(active?"active ":"")+(visible?"":"dimmed"),transform:`translate(${x},${y})`,tabindex:"0"});group.addEventListener("click",()=>select(m.name));group.append(el("rect",{width:nodeSize.w,height:nodeSize.head+nodeSize.row*m.columns.length+14,class:"table "+(active?"active ":"")+(visible?"":"dimmed")}),el("text",{x:15,y:24,class:"table-title"},m.name),el("text",{x:15,y:43,class:"table-meta"},`${m.grain} · ${m.columns.length} colonnes`));m.columns.forEach((c,i)=>group.append(el("text",{x:17,y:nodeSize.head+17+i*nodeSize.row,class:"column "+c.role.toLowerCase()},`${c.role==="PK"?"🔑 ":c.role==="measure"?"Σ ":""}${c.name}`)));g.append(group)});
}
function select(name){selected=name;const m=model(name);const rel=graph.edges.filter(e=>e.source===name||e.target===name);details.innerHTML=`<h2>${esc(m.name)}</h2><p class="hint">${esc(m.description)}</p><h3>Grain</h3><p>${esc(m.grain)}</p><h3>Colonnes</h3><div>${m.columns.map(c=>`<span class="badge ${c.role.toLowerCase()}">${c.role!=="attribute"?c.role+" · ":""}${esc(c.name)}</span>`).join("")}</div><h3>Relations</h3>${rel.length?rel.map(e=>`<div class="relation"><b>${e.source===name?"→":"←"} ${esc(e.source===name?e.target:e.source)}</b><br>${esc(e.cardinality)} · ${esc(e.sourceColumn)} ↔ ${esc(e.targetColumn)}</div>`).join(""):"<p class=\"hint\">Aucune relation directe dans la couche mart.</p>"}<h3>Fichier</h3><p class="hint">${esc(m.path)}</p>`;render()}
search.addEventListener("input",e=>{query=e.target.value;render()});document.querySelector("#reset").addEventListener("click",()=>{selected=null;query="";search.value="";details.innerHTML="<h2>Sélectionne une table</h2><p class=\"hint\">Clique sur une table pour afficher son grain, ses colonnes et ses relations.</p>";render()});
let pan={x:0,y:0,startX:0,startY:0,drag:false};svg.addEventListener("pointerdown",e=>{pan={...pan,startX:e.clientX-pan.x,startY:e.clientY-pan.y,drag:true};svg.setPointerCapture(e.pointerId)});svg.addEventListener("pointermove",e=>{if(!pan.drag)return;pan.x=e.clientX-pan.startX;pan.y=e.clientY-pan.startY;document.querySelector("#world").setAttribute("transform",`translate(${pan.x} ${pan.y})`)});svg.addEventListener("pointerup",()=>pan.drag=false);svg.addEventListener("wheel",e=>{e.preventDefault();const scale=Math.max(.55,Math.min(1.7,1-(e.deltaY/1000)));document.querySelector("#world").setAttribute("transform",`translate(${pan.x} ${pan.y}) scale(${scale})`)},{passive:false});
render();
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    graph = _make_graph(_load_models())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    html = HTML.replace("__GRAPH__", json.dumps(graph, ensure_ascii=False))
    args.output.write_text(html, encoding="utf-8")
    print(f"MCD généré : {args.output}")
    print("Ouvre ce fichier dans Cursor/VS Code avec « Simple Browser: Show ».")


if __name__ == "__main__":
    main()
