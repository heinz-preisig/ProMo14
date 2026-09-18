from fastapi import APIRouter

router = APIRouter()

# Registers the /model endpoints onto ``router`` (ADR-007).
from . import service  # noqa: F401,E402
