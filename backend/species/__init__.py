from fastapi import APIRouter

router = APIRouter()

# Registers the /species endpoints onto ``router`` (§20).
from . import service  # noqa: F401,E402
