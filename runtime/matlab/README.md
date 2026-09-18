# Matlab runtime — `@MultiDimVar`

Vendored from old-ProMo (`CAM13/ProMo/static_assets/@MultiDimVar`) on
2026-09-18.  Einstein-notation tensor library by the ProMo research
group: `MultiDimVar(indexLabels, indexSizes, indexOrder, value)` with
label-keyed operators — `einsum`, `reducesum`, `reducemult`, `plus`,
`minus`, `power`, `rdivide`, unitary functions.

`backend/equation/codegen.py` emits calls against this API for the
`matlab` target.  Generated code needs this directory (or the original)
on the Matlab/Octave path.

Do not edit here — upstream is the CAM13 repository; re-copy to update.
