"""ProMo suite backend — single FastAPI app mounting per-tool routers.

Each tool lives in its own package (ontology, equation, behaviour, modeller)
and exposes an APIRouter under /api/<tool>/. Shared services (RDF store,
IRI registry, ontology client) live in backend.core.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.behaviour import router as behaviour_router
from backend.equation.service import router as equation_router
from backend.modeller import router as modeller_router
from backend.ontology.service import router as ontology_router

app = FastAPI(title="ProMo Suite Backend")

app.include_router(ontology_router, prefix="/api/ontology", tags=["ontology"])
app.include_router(equation_router, prefix="/api/equation", tags=["equation"])
app.include_router(behaviour_router, prefix="/api/behaviour", tags=["behaviour"])
app.include_router(modeller_router, prefix="/api/modeller", tags=["modeller"])


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Static frontend (built equation editor)
# ---------------------------------------------------------------------------

STATIC_DIR = Path(os.environ.get("STATIC_DIR", "apps/equation-editor/dist")).resolve()
ASSETS_DIR = STATIC_DIR / "assets"

if ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


ONTOLOGY_STATIC_DIR = Path(
    os.environ.get("ONTOLOGY_STATIC_DIR", "apps/ontology-editor/dist")
).resolve()
ONTOLOGY_ASSETS_DIR = ONTOLOGY_STATIC_DIR / "assets"

if ONTOLOGY_ASSETS_DIR.is_dir():
    app.mount(
        "/ontology/assets",
        StaticFiles(directory=str(ONTOLOGY_ASSETS_DIR)),
        name="ontology-assets",
    )


@app.get("/ontology", include_in_schema=False)
@app.get("/ontology/", include_in_schema=False)
@app.get("/ontology/{full_path:path}", include_in_schema=False)
def serve_ontology_spa(full_path: str = "") -> FileResponse:
    """Serve the ontology editor SPA for every /ontology/* route."""
    index = ONTOLOGY_STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(str(index))
    return FileResponse(str(ONTOLOGY_STATIC_DIR / "index.html"), status_code=404)


@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str) -> FileResponse:
    """Serve the built React SPA for every non-API, non-asset route."""
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(str(index))
    return FileResponse(str(STATIC_DIR / "index.html"), status_code=404)
