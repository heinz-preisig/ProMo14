# Ontology Editor Design

A web-based ontology editor for ProMo14. It lets users define the
**core physics ontology**: the domain tree, variables, indices, tokens,
and equations. Large empirical relations (equations of state,
correlations) are not hand-edited here — they are imported as
**user functions**.

## Scope

Managed in the ontology editor:

- **Domain tree** (networks) — hierarchy of physical domains.
- **Tokens** — token types and their hierarchy.
- **Indices** — index definitions, aliases, and token bindings.
- **Variables** — three-name identity, units, tokens, index structures,
  aliases, doc.
- **Core equations** — equations with token-stream RHS, classified as
  `generic`, `instantiate`, `balance`, etc.

**Not** authored in the ontology editor:

- **Empirical / user-function equations** — registered by signature and
  linked to an external implementation.

## Layout

A single-page application with three persistent panes:

```
+-----------------+-------------------------------+------------------+
| Domain Tree     | Variable Table                | Detail / Editor  |
|                 |                               |                  |
| - physical      | type | symbol | network | ... | [selected row]   |
|   - macroscopic | ...  | ...    | ...     |     |                  |
|   - microscopic |                               | Identity         |
| - thermo        | [+ New] [+ Port] [LaTeX]      | Domain           |
|   - liquid      |                               | Semantics        |
|   - gas         |                               | Indices          |
|                 |                               | Equations        |
+-----------------+-------------------------------+------------------+
```

The active domain in the left tree filters the variable table in the
centre and pre-fills the `network` field for new variables.

## Domain tree pane

- Tree view of networks, editable via drag-drop or a context menu.
- Selecting a network sets `accessible_networks` context for the equation
  editor (it and its ancestors).
- Double-click a network to edit label, IRI, and parent.

## Variable table

Columns (extending the old PyQt table):

| Column | Purpose |
|--------|---------|
| `variable_class` | state / input / ... |
| `label` | surface symbol; click to rename |
| `doc` | short description |
| `tokens` | comma-separated token labels |
| `units` | rendered unit expression |
| `index_structures` | index code list, e.g. `[N, t]` |
| `eqs` | number of equations for this variable |
| `network` | definition network |
| `internal_id` | code name, e.g. `V_1` |
| `IRI` | full IRI |

Toolbar:
- **New** — add a variable.
- **Port** — mark/unmark selected row as a port variable.
- **LaTeX** — preview selected variables as LaTeX.
- **Delete** — remove selected variable (with incidence warning).
- **Export** — generate a publication-ready report.

## Detail / editor pane

A tabbed form for the selected variable:

### 1. Identity
- `IRI` (read-only after creation)
- `label`
- `internal_id` (auto-generated, editable)
- `aliases` — language map: `internal_code`, `latex`, and user-defined
  template languages.

### 2. Domain
- `network` — dropdown populated from the domain tree.
- `variable_class` — dropdown: `state`, `input`, `auxiliary`, ...
- `port_variable` — checkbox.

### 3. Semantics
- `doc` — free text.
- `units` — array editor (8 QUDT exponents) or a unit picker.
- `tokens` — multi-select of token IRIs from the token ontology.

### 4. Index structures
- Ordered list of index IRIs. Reorder via drag and drop.
- Indices are filtered by the variable's network (its `network` and
  ancestors) and by token compatibility.

### 5. Equations
- List of equation cards for this variable.
- Each card shows `equation_class`, `network`, and a rendered LaTeX
  preview.
- **Edit** opens the equation editor.
- **New equation** opens the equation editor pre-filled with `lhs =`.

## Equation editor (modal / inline)

```
+-------------------------------------------------+
| Equation Editor — network: [macroscopic ▼]      |
+-------------------------------------------------+
| [lhs variable label] := [ expression input    ] |
+-------------------------------------------------+
|                                                 |
|  LaTeX preview / rendered equation              |
|                                                 |
+-------------------------------------------------+
| Documentation: [_____________________]          |
| equation_class: [generic ▼]                     |
+-------------------------------------------------+
| [Variables] [Indices] [Operations] [Check]      |
+-------------------------------------------------+
```

- `lhs` is the selected variable (read-only in this context).
- `expression` is a text input accepting the ProMo14 surface syntax.
- **Check** calls `/api/equation/check` and shows errors inline.
- Pickers insert qualified names into the expression:
  - **Variables** — list of variables visible in the active network.
  - **Indices** — list of valid indices.
  - **Operations** — operators and ufuncs.
- `equation_class` dropdown filters available classes; for
  `empirical` / `user_function` the expression input becomes a function
  selector rather than a token editor.

## User function registration

A separate dialog / screen for empirical relations:

- `IRI` — stable function IRI.
- `label` — human name, e.g. "Peng–Robinson EOS".
- `network` — domain where it is valid.
- `signature` — ordered list of input variables and the output variable
  with their units and indices.
- `implementation` — link to the Python module / external library.
- `doc` — source reference or paper citation.

The equation editor can reference a user function by label; the checker
validates the call against the stored signature.

## Tokens and indices

Two auxiliary views:

- **Tokens** — a small hierarchy (`promo:Token` with `promo:parent`).
  Used for variable `tokens` and index `token`.
- **Indices** — table of indices with `IRI`, `label`, `internal_code`,
  `network`, `index_class`, and `token`.

## Arcs (model-level, not ontology-level)

Arcs are **not** defined in the ontology editor.  In the new design:

- **Physical domain arcs** — continuity conditions (the same flow
  variable on both sides of a connection).
- **Information flow arcs** — output of one function equals input of
  another.

Both are expressed as **equations** in the equation editor
(`output = input`, or a `Root` solve-for).  The actual graph connections
are drawn in the model/flowsheet editor, which generates the linking
equations.  The ontology editor only needs to know which variable
classes / tokens can carry a flow.

## Publication exports

From the ontology editor, the user can export:

- **LaTeX equation set** — all equations for the selected network and its
  descendants.
- **Variable table** — markdown or PDF table of variables, units,
  indices, and docs.
- **Domain tree diagram** — SVG / PDF of the network hierarchy.
- **Ontology report** — single markdown/PDF document combining the above,
  suitable for a paper or book appendix.

## State and data flow

1. Editor loads the current ontology from the graph store via
   `EquationContext` (see `equation-context-contract.md`).
2. All edits produce patches to the in-memory graph model.
3. `Check` buttons call the FastAPI equation endpoints using the current
   `DictContext` / graph context.
4. Save commits the graph to the backend store (RDF/JSON/OWL).

## Future decisions

- Web framework: React with Tailwind or shadcn/ui.
- Table library: TanStack Table for sort/filter/selection; virtualisation
  if empirical libraries are later browsed here.
- Equation input: a controlled text input with autocomplete for
  variables, indices, and operators (similar to the old PyQt
  `lineExpression`).
