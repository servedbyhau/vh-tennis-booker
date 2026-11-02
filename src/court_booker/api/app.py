"""Build the FastAPI application."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from court_booker import __version__
from court_booker.api import (
    accounts,
    history,
    live,
    notifications,
    runs,
    schedule,
    settings,
    setup,
    status,
)
from court_booker.api.context import AppContext
from court_booker.api.errors import Problem, add_error_handlers
from court_booker.api.ui import ui_router

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": Problem, "description": "Invalid request values, one line per value"},
    "default": {"model": Problem, "description": "An error with a stable code"},
}
"""Every route answers errors as a Problem; this tells the schema (and the UI types) so."""


class Health(BaseModel):
    """The backend answers and runs this version."""

    status: str
    version: str


def create_app(context: AppContext, ui_folder: Path | None = None) -> FastAPI:
    """Return the backend for ``context``; its OpenAPI schema is at ``/api/openapi.json``.

    With ``ui_folder``, a built UI, it serves that UI too; without it only ``/api``.
    """
    app = FastAPI(
        title="Court Booker",
        version=__version__,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.state.context = context
    add_error_handlers(app)

    @app.get("/api/health", response_model=Health, tags=["app"], responses=ERROR_RESPONSES)
    def health() -> Health:
        """Tell the UI the backend is up, and its version."""
        return Health(status="ok", version=__version__)

    for module in (history, settings, accounts, notifications, setup, schedule, runs, status):
        app.include_router(module.router, responses=ERROR_RESPONSES)
    app.include_router(live.router)
    if ui_folder is not None:
        app.include_router(ui_router(ui_folder))  # last: it answers every other address
    return app
