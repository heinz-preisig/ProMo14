# Legacy templates (unported sources)

Copied verbatim from old-ProMo
(`CAM13/ProMo/packages/OntologyBuilder/EquationEditor_v01` and
`Common/RepositoryInfrastructure/LaTeX/resources`) on 2026-09-18 for
reference — they are **not** wired into the renderer.

- `template_equation_list*.latex` — per-variable equation-assignment-
  sequence documents; port when the assignment machinery exists.
- `template_variable.{latex,matlab,python}` — trivial `{{var}}` stubs.
- `template_main.python` — old whole-simulation script skeleton
  (imports the never-ported `python_simulation` runtime); reference
  for the post-instantiation codegen pipeline.
- `latex_compile.sh`, `make_documentation.sh` — old doc compile
  pipeline scripts.

The working template is `../document.latex`; shared LaTeX macros live
in `../resources/` and are inlined by `document.py` at render time.
