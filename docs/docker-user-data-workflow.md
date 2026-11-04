# Docker + User-Data Workflow

ProMo14 ships as a Docker image. The image contains the tool suite (backend
and built frontends); the user's artefact repository stays on the
host and is mounted into the container at runtime.

This keeps **tools** and **user data** separate:

- The image is versioned, replaceable, and the same across users.
- The data directory is owned and located by the user.
- Upgrades do not touch user files; user experiments do not depend on a
  particular host Python/Node installation.

The mount is also the delivery channel for **generated code**: the container
never executes user models — emitted source (matlab/julia) must reach the
host filesystem, and writing it into the mounted dir avoids the
browser-download + unzip dance.

## Layout

```
my-project/
├── ontology.trig        # authored artefacts (inputs, version-worthy)
├── library.trig
├── model.trig
├── assignments.trig
├── generated/           # derived products — emitted code, re-emittable
│   ├── _GENERATED.txt   #   "do not edit" marker
│   ├── <model>/         #   <model>.m, model_data.json, run.m
│   └── @MultiDimVar/    #   shared runtime library
└── promo                # user-side launcher (copied from scripts/)
```

The container sees the same directory as `/data`:

```
PROMO_DATA_DIR=/data
```

Two subtrees, two roles: `*.trig` at the root are authored artefacts;
`generated/` is a pure re-emission target that may be deleted wholesale
(it re-emits from the model artefact on every export).

## Quick start

1.  Build (or pull) the image:

    ```bash
    docker build -t promo14:latest /path/to/ProMo14
    ```

2.  Copy the launcher into your data directory:

    ```bash
    cp /path/to/ProMo14/scripts/promo my-project/
    cd my-project
    ```

3.  Run the suite:

    ```bash
    ./promo
    ```

    The container mounts the current directory on `/data` (as the calling
    user via `--user`, so everything the backend writes — artefact saves,
    `generated/` exports — comes out user-owned), starts the FastAPI
    backend, and serves the suite on <http://localhost:8000>.

4.  Update the image later:

    ```bash
    ./promo update
    ```

    If the image is in a registry, `docker pull` fetches the new version.
    Otherwise the script prints a build command.

## Environment variables

| Variable          | Default              | Meaning                                  |
|-------------------|----------------------|------------------------------------------|
| `PROMO_DATA_DIR`  | current directory    | Directory mounted as `/data`             |
| `PROMO_IMAGE`     | `promo14:latest`     | Docker image to run                      |
| `PROMO_PORT`      | `8000`               | Host port exposed for the web interface  |

## Saving data

The backend writes artefact graphs as one `.trig` per artefact line under
`$PROMO_DATA_DIR` on save/publish.

## Generated code — two delivery channels

Same file set (`<model>.m`, `model_data.json`, `run.m`, `@MultiDimVar/`),
two sinks:

- **Project-dir export** — `POST /api/instantiate/code/export` writes
  `$PROMO_DATA_DIR/generated/<model>/…`. The Docker path: files land on the
  user's filesystem directly. Needs a writable mount.
- **Zip download** — `GET /api/instantiate/code/bundle` serves the same set
  as `<model>.zip` over HTTP. The universal fallback: works with read-only
  or remote mounts, and handy for grabbing a copy anywhere.

Generated code is a derived product, never an artefact — nothing is lost
if `generated/` is wiped; it re-renders from the model artefact.

## Building the image

The `Dockerfile` is a multi-stage build:

1.  Node stage: installs and builds `apps/equation-editor`.
2.  Python stage: installs dependencies via `uv sync` and copies the built
    `dist` directory.

Build with:

```bash
docker build -t promo14:latest .
```

If you want to use a registry, push the image and set `PROMO_IMAGE` in the
launcher:

```bash
docker tag promo14:latest ghcr.io/your-org/promo14:latest
docker push ghcr.io/your-org/promo14:latest
```
