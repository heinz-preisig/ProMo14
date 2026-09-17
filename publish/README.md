# Publishing the ProMo namespace

How `https://w3id.org/promo#` becomes dereferenceable.  Three pieces:

1. **ProMo14** (this repo) — generates the RDF artefacts.
2. **ProMo-ontologies** (`github.com/heinz-preisig/ProMo-ontologies`) —
   public repo hosting the artefacts via GitHub Pages at
   `https://heinz-preisig.github.io/ProMo-ontologies/`.
3. **perma-id/w3id.org** — community redirect registry; a PR adds the
   `promo/` rewrite rules that forward `w3id.org/promo*` to GitHub Pages.

## One-time setup

- [x] Create public repo `heinz-preisig/ProMo-ontologies` (the legacy
      ProMo repo was renamed to free the name).
- [x] Push an initial commit (exported `ontology.ttl` + landing page).
- [x] Settings → Pages → Deploy from branch → `main` / root (done via
      `gh api repos/heinz-preisig/ProMo-ontologies/pages -X POST`).
- [x] Verify `https://heinz-preisig.github.io/ProMo-ontologies/ontology.ttl`
      loads (200, `text/turtle`).
- [x] Fork `perma-id/w3id.org`, copy `publish/w3id/` as `ids/promo/` in
      the fork, commit, open a PR — submitted as
      https://github.com/perma-id/w3id.org/pull/6700
- [ ] After merge, verify `curl -L https://w3id.org/promo` redirects to
      the GitHub Pages site.

## Publishing an ontology version

From the Ontology Editor: **Publish…** freezes the working graph under
the version IRI, saves `data/ontology.trig`, and downloads the frozen
Turtle.  Or from the CLI — freeze (if new) and write straight into a
ProMo-ontologies checkout:

```bash
uv run python scripts/export_ontology.py --version 1.1 --repo ~/1_Gits/ProMo-ontologies
# writes ontology/1.1 and refreshes ontology.ttl

cd ~/1_Gits/ProMo-ontologies && git add ontology.ttl ontology/1.1 \
  && git commit -m "Ontology 1.1" && git push
```

Export without publishing (working draft):

```bash
uv run python scripts/export_ontology.py --out ontology.ttl
```

## Versioning (per ADR-006)

Ontology versions are immutable.  Publish snapshots under versioned
paths so existing IRIs never change meaning:

```
ProMo-ontologies/
  ontology.ttl          # latest
  ontology/1.0          # frozen snapshot (extensionless; served via
  ontology/1.1          #   the w3id catch-all for promo/ontology/{v})
```

Tag releases in the ProMo-ontologies repo (`v1.0`, `v1.1`, ...) to match.

## IRI layout

| IRI                              | Resolves to                              |
|----------------------------------|------------------------------------------|
| `w3id.org/promo#<term>`          | `ProMo-ontologies/ontology.ttl` (hash)   |
| `w3id.org/promo` (browser)       | `ProMo-ontologies/` landing page         |
| `w3id.org/promo` (RDF client)    | `ProMo-ontologies/ontology.ttl`          |
| `w3id.org/promo/ontology`        | `ProMo-ontologies/ontology.ttl`          |
| `w3id.org/promo/language#<term>` | `ProMo-ontologies/language.ttl`          |

Content negotiation is handled by the `.htaccess` rules in `w3id/`.
