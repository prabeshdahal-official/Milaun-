"""Local HTTP API and single-page review UI.

The server binds to loopback by default and holds no state between requests.
Names are never logged: uvicorn's access log records the path only, and the
handlers do not emit request bodies.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from milaun import __version__
from milaun.matcher import Matcher, name_keys

WEB_DIR = Path(__file__).resolve().parent / "web"
MAX_RECORDS = 5000


class CompareRequest(BaseModel):
    left: str = Field(min_length=1, max_length=200)
    right: str = Field(min_length=1, max_length=200)


class RecordIn(BaseModel):
    id: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=200)


class DedupeRequest(BaseModel):
    records: list[RecordIn] = Field(min_length=1, max_length=MAX_RECORDS)


def create_app(matcher: Matcher | None = None) -> FastAPI:
    """Build the FastAPI application."""
    engine = matcher or Matcher()
    app = FastAPI(
        title="Milaun",
        version=__version__,
        description="Offline record linkage for Nepali names.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; form-action 'none'; frame-ancestors 'none'"
        )
        return response

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        page = WEB_DIR / "index.html"
        if not page.is_file():  # pragma: no cover - packaging error
            raise HTTPException(status_code=500, detail="web assets are missing")
        return HTMLResponse(page.read_text(encoding="utf-8"))

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/api/info")
    def info() -> dict:
        return engine.describe()

    @app.post("/api/compare")
    def compare(request: CompareRequest) -> JSONResponse:
        try:
            result = engine.compare(request.left, request.right)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return JSONResponse(result.as_dict())

    @app.post("/api/dedupe")
    def dedupe(request: DedupeRequest) -> JSONResponse:
        records = [
            {"id": record.id or f"row-{position}", "name": record.name}
            for position, record in enumerate(request.records)
        ]
        result = engine.dedupe(records)
        return JSONResponse(result)

    @app.get("/api/keys")
    def keys(name: str) -> dict:
        if not name.strip():
            raise HTTPException(status_code=422, detail="name must not be empty")
        return name_keys(name).as_dict()

    return app


app = None  # populated by ``milaun serve``; importing this module is side-effect free
