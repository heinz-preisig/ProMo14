# @promo/equation-editor

Browser-based equation editor for ProMo14. Built with React + TypeScript + Vite.

## Features

- **Variable wizard** for defining port and dependent variables.
  - Choose a domain from the network tree.
  - Select a variable class (`state`, `effort`, `transport`, ...).
  - For port variables: set name, SI units and index structures.
  - For dependent variables: enter an RHS expression, check it, then save.
- **Index short names** (`short_name`) displayed and used in LaTeX subscripts, the check result panel, the variable wizard and the variable detail popup.
- **Variable palette** with click-to-view details and delete-with-cascade support.
  - Deleting a variable shows the dependent variables and equations that will also be removed.
- **Expression input** with operator/function buttons and a single **Check** button that parses and checks.
- **LaTeX preview** of parsed expressions, including index subscripts.
- **Inline parser / checker error display**.
- **Debug equation context (JSON)** popup for editing variables, indices and the network tree.
- **Save and reload checked equations**.

## User workflow

1. Click **New variable…** in the sidebar.
2. Choose **port variable** or **dependent variable**.
3. Pick a domain and a class.
4. For a port variable, enter the name, units and index structures, then **Add variable**.
5. For a dependent variable, enter the LHS name and an expression, then press **Check**.
   - `Check` parses first; if parsing succeeds it runs the semantic checker.
6. Save the dependent variable once the check passes.
7. Click any variable in the sidebar to view its details.
8. Click the `×` next to a variable to delete it and review the cascade impact.

## Run

Start the backend first:

```bash
cd /home/heinz/1_Gits/CAM14/ProMo14/backend
uvicorn main:app --reload --port 8000
```

Then start the frontend:

```bash
cd /home/heinz/1_Gits/CAM14/ProMo14
npm install
npm run dev:equation
```

The dev server runs on `http://localhost:3001` and proxies `/api` to the backend at `http://localhost:8000`.
