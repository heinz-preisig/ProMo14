# ProMo14 data directory

This directory is the default location for user-owned ontology / var/expr data during development.

- In production or Docker, mount the user's own data directory here with `PROMO_DATA_DIR`.
- Use subdirectories such as `ontology/` and `var_expr/` if you want, but the tool only requires a loadable set of `*.ttl` / `*.jsonld` named graphs.
- `*.trig` / `*.ttl` / `*.jsonld` graph files here ARE tracked by git — the user syncs work between two machines this way. Other file types remain ignored.
- Save layout: one `.trig` per artefact line — the draft graph plus its frozen versions ("the file is the history"), named by the line IRI's last segment. `ontology.trig` holds the core ontology line. A legacy single-file `ontology.trig` is split on first load.
This 