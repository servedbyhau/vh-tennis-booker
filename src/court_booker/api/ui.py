"""Serve the built UI from the backend, so the packaged app has one origin and needs no CORS."""

# No `from __future__ import annotations`: FastAPI reads the annotations at run time.
import mimetypes
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from court_booker.api.errors import NotFoundError

# The Windows registry can map .js to text/plain, and a browser then refuses the module.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


def ui_router(folder: Path) -> APIRouter:
    """Return the route that answers every address the API does not, from ``folder``.

    Include it after the API. Any address that is not a file gets ``index.html``, whose router
    shows the screen, so an address kept from an earlier visit still opens. ``index.html`` is
    never cached: it names the hashed files of the build, which change with an update.
    """
    router = APIRouter()
    root = folder.resolve()

    @router.get("/{address:path}", include_in_schema=False)
    def page(address: str) -> FileResponse:
        """Answer with the file at ``address``, or with the UI."""
        if address == "api" or address.startswith("api/"):
            raise NotFoundError(f"No such API address: /{address}")
        target = (root / address).resolve()
        if address and target.is_relative_to(root) and target.is_file():
            return FileResponse(target)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})

    return router
