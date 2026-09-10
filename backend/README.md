# ProMo Suite Backend

Single FastAPI application serving all browser tools. Each tool has its own
package exposing an `APIRouter`; shared services live in `core/`.

## Layout

- `core/` — shared services: RDF store access, IRI registry, ontology/QUDT client
- `ontology/` — ontology editor API (domains, node/arc types, variable types)
- `equation/` — equation editor + compiler API (parse, structural check, RDF output)
- `behaviour/` — behaviour linker API (equation selection → entity behaviour)
- `modeller/` — modeller API (model graph persistence, composition, validation)

## Run

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```
