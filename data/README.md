# ProMo14 data directory

This directory is the default location for user-owned ontology / var/expr data during development.

- In production or Docker, mount the user's own data directory here with `PROMO_DATA_DIR`.
- Use subdirectories such as `ontology/` and `var_expr/` if you want, but the tool only requires a loadable set of `*.ttl` / `*.jsonld` named graphs.
- Files placed here are ignored by git so they are not committed to the ProMo14 repository.
This 