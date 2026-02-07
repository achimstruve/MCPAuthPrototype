# =============================================================================
# Multi-Stage Dockerfile for the MCP Auth Prototype
# =============================================================================
#
# This Dockerfile builds a minimal, production-ready container image using
# two stages:
#
#   Stage 1 (builder): Uses the official uv image to install all Python
#   dependencies into a virtual environment. This stage has all the build
#   tools but is thrown away after the build.
#
#   Stage 2 (runtime): Copies only the virtual environment, source code,
#   and document files into a slim Python image. The result is a small,
#   secure image with no build tools, no package manager, no dev deps.
#
# Why multi-stage?
#   - Final image is ~150MB instead of ~800MB+ with build tools
#   - Smaller images = faster container pulls = faster deployments on GKE
#   - Fewer packages = smaller attack surface for security scanners
#   - Build dependencies (gcc, headers, uv itself) aren't in production
#
# Build:  docker build -t mcp-auth-prototype:local .
# Run:    docker run -p 8080:8080 -e MCP_JWT_SECRET_KEY=my-secret mcp-auth-prototype:local
#
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder — install dependencies with uv
# ---------------------------------------------------------------------------
# This image comes from Astral (the uv team). It includes Python 3.11 and
# uv pre-installed. We use it to resolve and install all dependencies into
# a virtual environment.
FROM ghcr.io/astral-sh/uv:python3.11-bookworm AS builder

WORKDIR /app

# Copy only the dependency files first. Docker caches each layer, so if
# pyproject.toml and uv.lock haven't changed, Docker skips reinstalling
# dependencies entirely. This makes rebuilds after code changes very fast.
COPY pyproject.toml uv.lock ./

# Install runtime dependencies (no dev deps like pytest, ruff).
# --frozen: use exact versions from uv.lock (fail if lock is stale)
# --no-dev: skip [project.optional-dependencies] dev group
# This creates a .venv directory with all the installed packages.
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal image with just the app
# ---------------------------------------------------------------------------
# python:3.11-slim is based on Debian bookworm with only essential packages.
# It's ~120MB vs ~900MB for the full Python image. The "slim" variant strips
# out compilers, headers, documentation, and other build-time dependencies.
FROM python:3.11-slim

WORKDIR /app

# Copy the virtual environment from the builder stage. This contains all
# our runtime dependencies (fastmcp, pyjwt, pydantic-settings, uvicorn)
# already compiled and ready to use.
COPY --from=builder /app/.venv /app/.venv

# Copy application source code
COPY src/ ./src/

# Copy document files (these are the content our tools serve)
COPY documents/ ./documents/

# Add the virtual environment's bin directory to PATH so that Python
# and all installed packages are found without needing to activate the venv.
# This is the standard pattern for containerized Python apps.
ENV PATH="/app/.venv/bin:$PATH"

# Document which port the server listens on. This doesn't actually publish
# the port — that's done with `docker run -p 8080:8080` or in the Kubernetes
# Service definition. EXPOSE is documentation for humans and tools.
EXPOSE 8080

# Health check: Docker (and Docker Compose) can use this to monitor the
# container's health. Kubernetes uses its own probe system (configured in
# the Helm chart), but this is useful for local development.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run the server. We use "python -m src.server" which:
# 1. Adds the current directory to sys.path (so `from src.xxx import` works)
# 2. Executes src/server.py as the __main__ module
# 3. Starts uvicorn on 0.0.0.0:8080 (configured via MCP_HOST and MCP_PORT env vars)
#
# We don't use CMD ["uvicorn", ...] directly because our server.py has
# startup logic (logging setup, middleware registration) that runs before
# calling mcp.run().
CMD ["python", "-m", "src.server"]
