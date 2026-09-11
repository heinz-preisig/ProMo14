import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    """Return the user-owned ProMo data directory.

    Defaults to a `data/` directory next to the ProMo14 repository root.
    Override with the PROMO_DATA_DIR environment variable.
    """
    override = os.environ.get("PROMO_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return PROJECT_ROOT / "data"


def ensure_data_dir() -> Path:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
