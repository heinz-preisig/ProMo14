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
from backend.species import router as species_router

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
app.include_router(species_router, prefix="/api/species", tags=["species"])


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Static frontends (built SPAs)
# ---------------------------------------------------------------------------

def _mount_assets(prefix: str, assets_dir: Path, name: str) -> None:
    """Mount a SPA's assets unconditionally.

    check_dir=False: dist/ may not exist at startup — building an app
    later must not require a backend restart (missing files 404).
    """
    app.mount(prefix,
              StaticFiles(directory=str(assets_dir), check_dir=False),
              name=name)


def _spa_index(static_dir: Path, name: str) -> Response:
    """Serve a built SPA's index.html, or a plain 404 if not built yet.

    ``no-cache`` forces revalidation every load: a rebuild changes the
    hashed bundle name, and a stale cached index.html would 404 the JS
    and render a blank page.  The hashed assets themselves stay
    cacheable."""
    index = static_dir / "index.html"
    if index.is_file():
        return FileResponse(
            str(index), headers={"Cache-Control": "no-cache"})
    return PlainTextResponse(
        f"{name} frontend not built (missing {index})", status_code=404
    )


#: (route prefix, STATIC_DIR env var, dist dir, display name) per SPA.
#: The equation editor sits at the root assets path for historical
#: reasons; every other app is namespaced under ``/<route>/assets``.
_SPAS = [
    ("equation",      "STATIC_DIR",             "apps/equation-editor/dist",   "Equation editor"),
    ("ontology",      "ONTOLOGY_STATIC_DIR",    "apps/ontology-editor/dist",   "Ontology editor"),
    ("modeller",      "MODELLER_STATIC_DIR",    "apps/modeller/dist",          "Modeller"),
    ("behaviour",     "BEHAVIOUR_STATIC_DIR",   "apps/behaviour-linker/dist",  "Behaviour linker"),
    ("instantiation", "INSTANTIATION_STATIC_DIR", "apps/instantiation/dist",   "Instantiation"),
    ("species",       "SPECIES_STATIC_DIR",     "apps/species/dist",           "Species"),
]


def _register_spa(route: str, env_var: str, dist: str, label: str) -> None:
    """Mount one SPA's assets and register its catch-all index route."""
    static_dir = Path(os.environ.get(env_var, dist)).resolve()
    assets_prefix = "/assets" if route == "equation" else f"/{route}/assets"
    _mount_assets(assets_prefix, static_dir / "assets", f"{route}-assets")

    def serve(full_path: str = "") -> Response:
        return _spa_index(static_dir, label)

    for path in (f"/{route}", f"/{route}/", f"/{route}/{{full_path:path}}"):
        app.get(path, include_in_schema=False)(serve)


for _route, _env, _dist, _label in _SPAS:
    _register_spa(_route, _env, _dist, _label)


HUB_PAGE = Path(__file__).resolve().parent / "static" / "hub.html"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

_DOC_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ max-width: 56em; margin: 2em auto; padding: 0 1em;
       font: 15px/1.55 -apple-system, "Segoe UI", sans-serif;
       color: #1f2937; }}
code, pre {{ font: 0.9em ui-monospace, monospace; background: #f3f4f6;
            border-radius: 4px; }}
code {{ padding: 0.1em 0.3em; }}
pre {{ padding: 0.8em; overflow-x: auto; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid #d1d5db; padding: 0.3em 0.7em;
         text-align: left; }}
h1, h2, h3, h4 {{ color: #111827; }}
a {{ color: #2563eb; }}
blockquote {{ border-left: 3px solid #d1d5db; margin-left: 0;
             padding-left: 1em; color: #4b5563; }}
</style></head><body>{body}</body></html>"""


@app.get("/docs/{filename}", include_in_schema=False)
def serve_doc(filename: str, raw: bool = False) -> Response:
    """Serve a documentation markdown file rendered as HTML.

    Read-only, basename only, ``.md`` only.  Heading anchors come from
    the ``toc`` extension — GitHub-style slugs, so ``#unbound-port``
    scrolls to ``### unbound-port``.  ``?raw=1`` returns the markdown
    source.  Problem reports link here via ``doc`` anchors
    (``/docs/problem-catalogue.md#<kind>``)."""
    safe = Path(filename).name
    if not safe.endswith(".md"):
        return PlainTextResponse("not a markdown document", status_code=404)
    path = DOCS_DIR / safe
    if not path.is_file():
        return PlainTextResponse(f"no such document: {safe}", status_code=404)
    headers = {"Cache-Control": "no-cache"}
    if raw:
        return FileResponse(str(path),
                            media_type="text/markdown; charset=utf-8",
                            headers=headers)
    import markdown
    body = markdown.markdown(
        path.read_text(encoding="utf-8"),
        extensions=["toc", "tables", "fenced_code", "sane_lists"])
    from fastapi.responses import HTMLResponse
    return HTMLResponse(
        _DOC_PAGE.format(title=safe, body=body), headers=headers)


@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
def serve_hub(full_path: str = "") -> FileResponse:
    """Serve the suite hub (artefact catalogue) as the entry point."""
    return FileResponse(
        str(HUB_PAGE), headers={"Cache-Control": "no-cache"}
    )
