"""ProMo suite backend — single FastAPI app mounting per-tool routers.

Each tool lives in its own package (ontology, equation, behaviour, modeller)
and exposes an APIRouter under /api/<tool>/. Shared services (RDF store,
IRI registry, ontology client) live in backend.core.
"""

from fastapi import FastAPI

from backend.behaviour import router as behaviour_router
from backend.equation import router as equation_router
from backend.modeller import router as modeller_router
from backend.ontology import router as ontology_router

app = FastAPI(title="ProMo Suite Backend")

app.include_router(ontology_router, prefix="/api/ontology", tags=["ontology"])
app.include_router(equation_router, prefix="/api/equation", tags=["equation"])
app.include_router(behaviour_router, prefix="/api/behaviour", tags=["behaviour"])
app.include_router(modeller_router, prefix="/api/modeller", tags=["modeller"])


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
