"""Shared test infrastructure.

``GraphClient`` is a ``TestClient`` that injects the session's
``?graph=`` param on mutating calls that don't already name a graph —
mirroring what the real frontends do (``apiFetch``/``withGraph``
appends it to every request).  Writes without ``?graph=`` are rejected
(400) since ``editable_param`` enforcement, so fixtures bind the client
to the artefact their tests edit; reads keep the legacy dataset-wide
default and are left untouched.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote

from fastapi.testclient import TestClient

_MUTATING = {"POST", "PUT", "DELETE", "PATCH"}


def _has_graph(url, params) -> bool:
    if "graph=" in str(url):
        return True
    if params is None:
        return False
    if isinstance(params, dict):
        return "graph" in params
    return any(k == "graph" for k, _ in params)


class GraphClient(TestClient):
    """TestClient bound to an artefact graph IRI for write calls."""

    def __init__(self, *args, graph_iri: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.graph_iri = graph_iri

    def request(self, method, url, **kwargs):
        if (self.graph_iri and method.upper() in _MUTATING
                and not _has_graph(url, kwargs.get("params"))):
            sep = "&" if "?" in str(url) else "?"
            url = f"{url}{sep}graph={quote(self.graph_iri, safe='')}"
        return super().request(method, url, **kwargs)
