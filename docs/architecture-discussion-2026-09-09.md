# ProMo Suite Architecture Discussion — 2026-09-09

> **Superseded** by `docs/suite-overview.md`.  Kept as a historical record
> of the initial architecture discussion.  Several open questions listed
> below have since been resolved — see ADR-005, `ontology-data-model.md`,
> and `equation-context-contract.md`.

## Context

ProMo14 Modeller (browser-based, React+Konva) has Phases 1–3 complete (35 tests passing). Now looking at the upstream modules before continuing with persistence (Phase 4).

## Suite pipeline

```
Ontology Editor → Equation Editor → Behaviour Linker → Modeller (ProMo14) → Model Reuse → Instantiation → Code Generation
```

## Browser vs PyQt

- Current Equation Editor has PyQt frontend + Python special-purpose compiler (solid, don't redo)
- User leans toward making ALL tools browser-based (ontology editor, equation editor, behaviour linker, modeller)
- Python stays as backend (FastAPI/Flask + WebSocket)
- Only frontends would be rewritten; compiler and math backend stay in Python
- Main motivation: unified tech stack, one spawnable Graphic Object Editor (ADR-004), unified IRI/catalogue space
- Other tools (ontology editor, behaviour linker) are relatively simple editors but don't work with RDF yet — need to be touched regardless

## Ontology Editor

- Builds hierarchical domain structure
- Defines specific objects within domains
- Output: node type definitions, arc type definitions, variable types
- Not complicated, but needs rethinking given new approach

## Equation Editor / Compiler

- User writes string with operators and variables
- Compiler checks syntax + structural consistency
- If accepted → produces internal representation with unique IDs for variables, operators, delimiters
- Currently outputs JSON file → consumed by "assignment tool"
- Needs to change: JSON → RDF, internal IDs → IRIs
- Variables link to public IRIs when they exist (e.g., QUDT for quantities/units), otherwise ProMo-namespace IRIs
- Operators and delimiters also need IRIs

## External ontology references

- QUDT for quantities, units, dimensions (e.g., temperature is just one example)
- Mix of external ontology references and ProMo-specific definitions
- Compiler and equation editor need access to both

## Open questions (to continue)

1. Is the "assignment tool" the Behaviour Linker, or a separate step between compiler and Behaviour Linker?
2. Structural consistency check — type-level (dimension compatibility via QUDT), structural (arity/parentheses), or both?
3. How deeply does the compiler need to query the ontology during compilation?
4. RDF vocabulary design for equations, operators, variables
5. Should we look at the old ProMo codebase for reference?

## Next steps

- Continue discussion tomorrow, possibly on another computer
- Look at old ProMo codebase for reference
- Then decide on architecture and start implementing
