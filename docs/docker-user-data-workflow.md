# Docker + User-Data Workflow

ProMo14 ships as a Docker image. The image contains the tool suite (backend
and built frontend); the user's ontology / var/expr repository stays on the
host and is mounted into the container at runtime.

This keeps **tools** and **user data** separate:

- The image is versioned, replaceable, and the same across users.
- The data directory is owned and located by the user.
- Upgrades do not touch user files; user experiments do not depend on a
  particular host Python/Node installation.

## Layout

```
my-project/
├── ontology.json
├── variables_v8.json
├── variableExpression.trig
└── promo          # user-side launcher (copied from scripts/)
```

The container sees the same directory as `/data`:

```
PROMO_DATA_DIR=/data
```

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

    The container mounts the current directory on `/data`, starts the
    FastAPI backend, and serves the equation editor SPA on
    <http://localhost:8000>.

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

The backend writes the edited ontology to
`$PROMO_DATA_DIR/ontology.trig` when the user publishes.  The legacy
`variables_v8.json` / `ontology.json` files are still read on first boot if
`ontology.trig` is absent, so existing projects keep working.

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
