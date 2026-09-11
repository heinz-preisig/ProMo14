# syntax=docker/dockerfile:1

# Multi-stage build for the ProMo14 suite.
# Stage 1 builds the React frontends; stage 2 builds the Python backend
# and serves both SPAs plus the FastAPI API from a single process.

FROM node:20-slim AS equation-frontend

# tsconfig.json extends the repo-level base, so keep the same nesting.
WORKDIR /build/apps/equation-editor

# Copy only the package manifest first for a cache-friendly install.
COPY apps/equation-editor/package.json ./
RUN npm install

# Then copy the rest of the source, the shared tsconfig base, and build.
COPY apps/equation-editor/ ./
COPY tsconfig.base.json /build/tsconfig.base.json
RUN npm run build


FROM node:20-slim AS ontology-frontend

WORKDIR /build/apps/ontology-editor

COPY apps/ontology-editor/package.json ./
RUN npm install

COPY apps/ontology-editor/ ./
COPY tsconfig.base.json /build/tsconfig.base.json
RUN npm run build


FROM python:3.12-slim AS backend

WORKDIR /app

# Install Python deps first for Docker layer caching.
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the backend source and the built frontend dists.
COPY backend ./backend
COPY --from=equation-frontend /build/apps/equation-editor/dist ./apps/equation-editor/dist
COPY --from=ontology-frontend /build/apps/ontology-editor/dist ./apps/ontology-editor/dist

# Data volume: the user mounts their ontology / var/expr repository here.
ENV PROMO_DATA_DIR=/data
ENV STATIC_DIR=/app/apps/equation-editor/dist
ENV ONTOLOGY_STATIC_DIR=/app/apps/ontology-editor/dist

VOLUME ["/data"]
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
