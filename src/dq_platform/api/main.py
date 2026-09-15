"""FastAPI application for dashboard data and conversational Q&A."""

from datetime import date
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import asyncio

from dq_platform.services import chart_queries
from dq_platform.orchestration.chat_pipeline import answer_question

app = FastAPI(title="DQ Platform API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str
    dashboard_context: dict[str, Any] = Field(default_factory=dict)


def _dates(start: date | None, end: date | None) -> tuple[date, date]:
    filters = chart_queries.get_filters()
    return start or filters["min_date"], end or filters["max_date"]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/filters")
def filters() -> dict[str, Any]:
    return chart_queries.get_filters()


@app.get("/api/kpis")
def kpis(
    start: date | None = None,
    end: date | None = None,
    countries: list[str] = Query(default=[]),
    channels: list[str] = Query(default=[]),
) -> list[dict[str, Any]]:
    start, end = _dates(start, end)
    return chart_queries.get_kpis(start, end, countries, channels)


@app.get("/api/charts/daily-trends")
def daily_trends(
    start: date | None = None,
    end: date | None = None,
    countries: list[str] = Query(default=[]),
    channels: list[str] = Query(default=[]),
) -> list[dict[str, Any]]:
    start, end = _dates(start, end)
    return chart_queries.get_daily_trends(start, end, countries, channels)


@app.get("/api/charts/by-country")
def by_country(start: date | None = None, end: date | None = None, countries: list[str] = Query(default=[]), channels: list[str] = Query(default=[])):
    start, end = _dates(start, end)
    return chart_queries.get_breakdown("country_code", start, end, countries, channels)


@app.get("/api/charts/by-channel")
def by_channel(start: date | None = None, end: date | None = None, countries: list[str] = Query(default=[]), channels: list[str] = Query(default=[])):
    start, end = _dates(start, end)
    return chart_queries.get_breakdown("channel", start, end, countries, channels)


@app.get("/api/charts/top-products")
def top_products(start: date | None = None, end: date | None = None, countries: list[str] = Query(default=[]), channels: list[str] = Query(default=[])):
    start, end = _dates(start, end)
    return chart_queries.get_top_products(start, end, countries, channels)


@app.get("/api/charts/top-stores")
def top_stores(start: date | None = None, end: date | None = None, countries: list[str] = Query(default=[]), channels: list[str] = Query(default=[])):
    start, end = _dates(start, end)
    return chart_queries.get_top_stores(start, end, countries, channels)


@app.post("/api/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    answer = await answer_question(request.question, request.dashboard_context)

    async def events():
        for line in answer.splitlines(keepends=True) or [answer]:
            yield f"data: {line}\n\n"
            await asyncio.sleep(0)

    return StreamingResponse(events(), media_type="text/event-stream")


def main() -> None:
    import uvicorn

    uvicorn.run("dq_platform.api.main:app", host="0.0.0.0", port=8000, reload=False)
