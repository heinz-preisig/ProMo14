"""ProMo suite backend — single FastAPI app mounting per-tool routers.

Each tool lives in its own package (ontology, equation, behaviour, modeller)
and exposes an APIRouter under /api/<tool>/. Shared services (RDF store,
IRI registry, ontology client) live in backend.core.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.behaviour import router as behaviour_router
from backend.core.catalogue import router as catalogue_router
from backend.core.graph_store import get_store
from backend.equation.service import router as equation_router
from backend.instantiate import router as instantiate_router
from backend.modeller import router as modeller_router
from backend.ontology.service import router as ontology_router

app = FastAPI(title="ProMo Suite Backend")

# POSTs that do not mutate the dataset (read-only checks) or that persist it
# themselves (save/publish clear the dirty flag via RdfStore.save).
_NON_MUTATING_POSTS = {
    "/api/equation/parse",
    "/api/equation/check",
    "/api/behaviour/evaluate",
    "/api/ontology/save",
    "/api/ontology/publish",
}


@app.middleware("http")
async def track_store_dirty(request, call_next):
    """Flag the shared RdfStore dirty after any successful mutating call.

    Covers every present and future CRUD endpoint across the ontology,
    equation, and catalogue routers — the frontends poll
    ``GET /api/ontology/status`` to show an unsaved-changes badge.
    """
    response = await call_next(request)
    if (
        request.method in {"POST", "PUT", "DELETE"}
        and response.status_code < 400
        and request.url.path not in _NON_MUTATING_POSTS
    ):
        get_store().mark_dirty()
    return response

app.include_router(ontology_router, prefix="/api/ontology", tags=["ontology"])
app.include_router(equation_router, prefix="/api/equation", tags=["equation"])
app.include_router(behaviour_router, prefix="/api/behaviour", tags=["behaviour"])
app.include_router(modeller_router, prefix="/api/modeller", tags=["modeller"])
app.include_router(instantiate_router, prefix="/api/instantiate", tags=["instantiate"])
app.include_router(catalogue_router, prefix="/api/catalogue", tags=["catalogue"])


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


def _spa_index(static_dir: Path, name: str) -> Response:
    """Serve a built SPA's index.html, or a plain 404 if not built yet."""
    index = static_dir / "index.html"
    if index.is_file():
        return FileResponse(str(index))
    return PlainTextResponse(
        f"{name} frontend not built (missing {index})", status_code=404
    )


@app.get("/ontology", include_in_schema=False)
@app.get("/ontology/", include_in_schema=False)
@app.get("/ontology/{full_path:path}", include_in_schema=False)
def serve_ontology_spa(full_path: str = "") -> Response:
    """Serve the ontology editor SPA for every /ontology/* route."""
    return _spa_index(ONTOLOGY_STATIC_DIR, "Ontology editor")


@app.get("/equation", include_in_schema=False)
@app.get("/equation/", include_in_schema=False)
@app.get("/equation/{full_path:path}", include_in_schema=False)
def serve_equation_spa(full_path: str = "") -> Response:
    """Serve the equation editor SPA for every /equation/* route."""
    return _spa_index(STATIC_DIR, "Equation editor")


MODELLER_STATIC_DIR = Path(
    os.environ.get("MODELLER_STATIC_DIR", "apps/modeller/dist")
).resolve()
MODELLER_ASSETS_DIR = MODELLER_STATIC_DIR / "assets"

if MODELLER_ASSETS_DIR.is_dir():
    app.mount(
        "/modeller/assets",
        StaticFiles(directory=str(MODELLER_ASSETS_DIR)),
        name="modeller-assets",
    )


@app.get("/modeller", include_in_schema=False)
@app.get("/modeller/", include_in_schema=False)
@app.get("/modeller/{full_path:path}", include_in_schema=False)
def serve_modeller_spa(full_path: str = "") -> Response:
    """Serve the modeller SPA for every /modeller/* route."""
    return _spa_index(MODELLER_STATIC_DIR, "Modeller")


BEHAVIOUR_STATIC_DIR = Path(
    os.environ.get("BEHAVIOUR_STATIC_DIR", "apps/behaviour-linker/dist")
).resolve()
BEHAVIOUR_ASSETS_DIR = BEHAVIOUR_STATIC_DIR / "assets"

if BEHAVIOUR_ASSETS_DIR.is_dir():
    app.mount(
        "/behaviour/assets",
        StaticFiles(directory=str(BEHAVIOUR_ASSETS_DIR)),
        name="behaviour-assets",
    )


@app.get("/behaviour", include_in_schema=False)
@app.get("/behaviour/", include_in_schema=False)
@app.get("/behaviour/{full_path:path}", include_in_schema=False)
def serve_behaviour_spa(full_path: str = "") -> Response:
    """Serve the behaviour linker SPA for every /behaviour/* route."""
    return _spa_index(BEHAVIOUR_STATIC_DIR, "Behaviour linker")


HUB_PAGE = Path(__file__).resolve().parent / "static" / "hub.html"


@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
def serve_hub(full_path: str = "") -> FileResponse:
    """Serve the suite hub (artefact catalogue) as the entry point."""
    return FileResponse(str(HUB_PAGE))
