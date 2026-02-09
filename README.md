# MCP Auth Prototype

A secure [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server demonstrating enterprise-grade access control patterns. Built with Python and [FastMCP v2](https://gofastmcp.com), this prototype implements JWT-based authentication and scope-based tool authorization, designed for deployment on Google Kubernetes Engine.

## What This Demonstrates

- **Token-based authentication**: Every MCP request requires a valid JWT Bearer token
- **Scope-based authorization**: Token scopes determine which tools a client can see and call
- **Defense in depth**: Tool list filtering AND tool call validation (two independent checks)
- **Structured audit logging**: Every auth decision logged as JSON for cloud logging systems
- **12-factor configuration**: All settings via environment variables
- **Kubernetes-ready**: Health and readiness probe endpoints

## Architecture

```
Client (Claude Code, MCP client)
  │
  │  Authorization: Bearer <jwt>
  ▼
┌─────────────────────────────────┐
│  FastMCP Server (port 8080)     │
│                                 │
│  ┌───────────────────────────┐  │
│  │  AuthMiddleware           │  │
│  │  1. Extract Bearer token  │  │
│  │  2. Validate JWT (sig+exp)│  │
│  │  3. Filter tools by scope │  │
│  │  4. Block unauthorized    │  │
│  └───────────────────────────┘  │
│                                 │
│  ┌───────────┐ ┌─────────────┐  │
│  │ get_public│ │get_confiden-│  │
│  │ _info     │ │tial_info    │  │
│  │           │ │             │  │
│  │ scope:    │ │ scope:      │  │
│  │ public:   │ │ confidenti- │  │
│  │ read      │ │ al:read     │  │
│  └───────────┘ └─────────────┘  │
│                                 │
│  /health  /ready  /mcp          │
└─────────────────────────────────┘
```

### Access Control Matrix

| Token Scopes | Visible Tools | Can Call |
|---|---|---|
| `["public:read"]` | `get_public_info` only | `get_public_info` only |
| `["public:read", "confidential:read"]` | Both tools | Both tools |
| `[]` | None | None |
| No token / expired / invalid | Rejected (AuthError) | Rejected (AuthError) |

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

### Install and Run

```bash
# Install dependencies
uv sync

# Start the server
uv run python -m src.server
```

The server starts on `http://localhost:8080` with:
- MCP endpoint: `POST /mcp` (Streamable HTTP transport)
- Health check: `GET /health`
- Readiness check: `GET /ready`

### Generate a Token

```bash
# Public access only
uv run python -m scripts.generate_token --sub alice --scope public:read

# Full access
uv run python -m scripts.generate_token --sub bob --scope public:read confidential:read

# Expired token (for testing rejection)
uv run python -m scripts.generate_token --sub charlie --scope public:read --exp-hours -1
```

> **Note:** The token must be signed with the same secret the server uses. By default, both
> use `dev-secret-change-me`. If you run the server with a custom secret (e.g.,
> `MCP_JWT_SECRET_KEY=my-secret`), you must generate tokens with the matching `--secret` flag:
> ```bash
> uv run python -m scripts.generate_token --sub alice --scope public:read --secret my-secret
> ```

### Connect with Claude Code

```bash
# Generate a token
TOKEN=$(uv run python -m scripts.generate_token --sub myuser --scope public:read confidential:read 2>&1 | grep "^Token:" | cut -d' ' -f2)

# Add the MCP server to Claude Code
claude mcp add --transport http mcp-auth-prototype http://localhost:8080/mcp \
  --header "Authorization: Bearer $TOKEN"
```

### Test with curl

```bash
# Generate a token
TOKEN=$(uv run python -m scripts.generate_token --sub alice --scope public:read 2>&1 | grep "^Token:" | cut -d' ' -f2)

# Initialize MCP session
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

## Development

```bash
# Run tests
uv run pytest -v

# Lint
uv run ruff check .
```

## Docker

Build and test the container image locally before deploying to Kubernetes.

### Build the Image

```bash
# Build the Docker image
docker build -t mcp-auth-prototype:local .
```

The multi-stage build creates a minimal ~150MB image containing only the runtime dependencies.

### Run the Container

```bash
# Run with a custom JWT secret (required for production)
docker run -p 8080:8080 -e MCP_JWT_SECRET_KEY=my-secret mcp-auth-prototype:local

# Run with debug logging
docker run -p 8080:8080 \
  -e MCP_JWT_SECRET_KEY=my-secret \
  -e MCP_LOG_LEVEL=debug \
  mcp-auth-prototype:local
```

### Test the Container

```bash
# Verify health endpoint
curl http://localhost:8080/health

# Verify readiness endpoint
curl http://localhost:8080/ready

# Generate a token (must use --secret matching the container's MCP_JWT_SECRET_KEY)
TOKEN=$(uv run python -m scripts.generate_token --sub alice --scope public:read --secret my-secret 2>&1 | grep "^Token:" | cut -d' ' -f2)

# Test MCP initialization against the container
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

### Project Structure

```
mcp-auth-prototype/
├── src/
│   ├── server.py          # MCP server, auth middleware, health endpoints
│   ├── auth.py            # JWT validation and scope extraction
│   ├── tools.py           # Tool-to-scope mapping registry
│   └── config.py          # Environment-based configuration (pydantic-settings)
├── documents/
│   ├── public.md          # Sample public company document
│   └── confidential.md    # Sample confidential strategy document
├── scripts/
│   └── generate_token.py  # CLI utility to mint JWT tokens
├── tests/
│   ├── conftest.py        # Shared test fixtures (token factories)
│   ├── test_auth.py       # Unit tests for JWT validation (16 tests)
│   └── test_tools.py      # Integration tests for tool authorization (6 tests)
├── helm/
│   └── mcp-server/            # Helm chart for Kubernetes deployment
│       ├── Chart.yaml         # Chart metadata (name, version)
│       ├── values.yaml        # Default configuration values
│       ├── values-dev.yaml    # Dev environment overrides
│       └── templates/
│           ├── _helpers.tpl       # Reusable Go template helpers
│           ├── deployment.yaml    # Deployment (2 replicas, probes, env vars)
│           ├── service.yaml       # ClusterIP Service on port 8080
│           ├── configmap.yaml     # Document content (public.md, confidential.md)
│           ├── serviceaccount.yaml # K8s ServiceAccounts with Workload Identity
│           ├── secretstore.yaml   # ESO connection to GCP Secret Manager
│           └── externalsecret.yaml # Syncs JWT key from GCP to K8s Secret
├── terraform/             # Infrastructure as Code
│   ├── main.tf            # Provider and backend configuration
│   ├── variables.tf       # Input variables
│   ├── outputs.tf         # Output values
│   ├── gke.tf             # GKE cluster definition
│   ├── artifact-registry.tf  # Container registry
│   ├── secret-manager.tf  # Secret Manager resources
│   └── iam.tf             # Service accounts and IAM bindings
├── pyproject.toml         # Dependencies and tool configuration
└── uv.lock                # Locked dependency versions
```

## Design Decisions

### Document Storage: ConfigMap (Prototype) vs Production Alternatives

In this prototype, document content (`public.md`, `confidential.md`) is inlined directly in a Kubernetes ConfigMap within the Helm chart. This is appropriate here because:

- We have only 2 small, static documents (~1KB total)
- It keeps the Helm chart self-contained and easy to understand
- Helm's `.Files.Get` function can't read files outside the chart directory

**This approach does NOT scale.** ConfigMaps are limited to 1MB, document changes require a full Helm upgrade (which triggers a pod rolling update), and there's no versioning or independent lifecycle management.

**Production alternatives for document-heavy systems:**

| Pattern | When to Use | How It Works |
|---------|-------------|--------------|
| **Object Storage (GCS/S3)** | Most common. Independent document lifecycle, many documents | App fetches from a cloud bucket at runtime via Workload Identity. Supports versioning, CDN, fine-grained IAM. |
| **Database (PostgreSQL/Firestore)** | Documents need metadata, search, relationships | App queries a database per request. Full CRUD, indexing, transactions. |
| **Git repo + sidecar** | GitOps-heavy orgs, docs-as-code | A sidecar/init container clones a separate docs repo. Version history from Git, PRs for review. |
| **Content API microservice** | Large-scale, many consumers | Dedicated service manages documents. MCP server becomes a thin orchestration layer. |

The key principle: **decouple document lifecycle from application lifecycle.** The MCP server should be deployable independently from content updates.

## Configuration

All settings are read from environment variables with the `MCP_` prefix:

| Variable | Default | Description |
|---|---|---|
| `MCP_HOST` | `0.0.0.0` | Network interface to bind to |
| `MCP_PORT` | `8080` | Server port |
| `MCP_LOG_LEVEL` | `info` | Logging verbosity (`debug`, `info`, `warning`, `error`) |
| `MCP_JWT_SECRET_KEY` | `dev-secret-change-me` | JWT signing key (override in production) |
| `MCP_JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `MCP_DOCUMENTS_DIR` | `documents` | Path to document files |

You can also set these in a `.env` file (gitignored).

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| MCP Server | [FastMCP v2](https://gofastmcp.com) | MCP protocol with middleware hooks |
| Authentication | [PyJWT](https://pyjwt.readthedocs.io) | JWT token validation |
| Configuration | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | Typed env var config |
| HTTP Server | [Uvicorn](https://www.uvicorn.org) | ASGI server |
| Testing | pytest + httpx | Unit and integration tests |
| Linting | [Ruff](https://docs.astral.sh/ruff/) | Fast Python linter |
| Package Manager | [uv](https://docs.astral.sh/uv/) | Fast Python package manager |
| Infrastructure | [Terraform](https://www.terraform.io/) | Infrastructure as Code for GCP resources |
| Container Registry | GCP Artifact Registry | Docker image storage |
| Orchestration | Google Kubernetes Engine | Container orchestration |
| Secrets | GCP Secret Manager + ESO | Secure secret management |

## Roadmap

See [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) for the full build plan. Current status:

- [x] Phase 0: Project scaffolding
- [x] Phase 1: MCP server with tools
- [x] Phase 2: Authentication and authorization
- [x] Phase 3: Tests
- [x] Phase 4: Dockerize
- [x] Phase 5: GCP Infrastructure + Terraform + GKE
- [x] Phase 6: Helm chart
- [ ] Phase 7: GitHub Actions CI pipeline
- [ ] Phase 8: ArgoCD
- [ ] Phase 9: End-to-end verification
- [ ] Phase 10: TLS Ingress (HTTPS) — Ingress controller, cert-manager, Let's Encrypt, encrypted external access
- [ ] Phase 11: OAuth2 Token Service — Production token issuance via Google OAuth2, developer CLI, Claude Code integration
- [ ] Phase 12: Autoscaling & Resilience — HPA, Cluster Autoscaler, PDB, load balancing, load testing with Locust
