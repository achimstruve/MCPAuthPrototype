# Product Requirements Document: Secure MCP Server Prototype

## Overview

A prototype MCP (Model Context Protocol) server demonstrating enterprise-grade access control patterns deployed on Google Kubernetes Engine. This project serves as a practical demonstration of building secure AI infrastructure with tiered authorization, containerized deployment, and GitOps-based CI/CD.

## Problem Statement

AI agents require access to internal data sources, but granting unrestricted access creates security risks. Organizations need a pattern for:
- Authenticating agent requests
- Scoping access based on authorization level
- Deploying MCP servers in a scalable, reproducible manner
- Managing secrets securely

This prototype demonstrates a minimal but complete implementation of these patterns.

## Goals

1. Build an MCP server with token-based authentication and scoped tool access
2. Deploy to GKE using production-ready practices (Helm, ArgoCD, Secrets Manager)
3. Document the architecture for reference and demonstration purposes
4. Gain hands-on experience with enterprise-grade cloud-native technology stacks

## Non-Goals

- Production-grade high availability (we run 2 replicas for learning, but don't need automated failover, PodDisruptionBudgets, etc.)
- Complex RAG or vector database integration
- Fine-grained RBAC beyond two authorization tiers
- Custom domain or TLS termination (cluster-internal only)
- Auto-scaling node pools (fixed node count is fine for a prototype)

---

## Functional Requirements

### FR1: MCP Server with Two Tools

The MCP server exposes two tools via the MCP protocol:

| Tool | Description | Required Scope |
|------|-------------|----------------|
| `get_public_info` | Returns contents of a public company document | `public:read` |
| `get_confidential_info` | Returns contents of a confidential strategy document | `confidential:read` |

Both tools return document content as structured text. The documents themselves are static files bundled with the server or fetched from a configurable source.

### FR2: Token-Based Authentication

Every MCP request must include a Bearer token in the authorization header. The server validates tokens and extracts scopes.

**Token Structure (JWT):**
```
{
  "sub": "user-or-agent-id",
  "scope": ["public:read", "confidential:read"],
  "exp": <expiration timestamp>
}
```

**Validation Rules:**
- Reject requests without a valid token
- Reject expired tokens
- Extract scopes from token claims

### FR3: Scope-Based Tool Access

The server enforces access control at the tool level:

| Token Scopes | Available Tools |
|--------------|-----------------|
| `["public:read"]` | `get_public_info` only |
| `["public:read", "confidential:read"]` | Both tools |
| `[]` or missing | No tools (empty tool list) |

When a client connects, the MCP server returns only the tools the token authorizes. Attempts to call unauthorized tools return a permission denied error.

### FR4: Health and Readiness Endpoints

The server exposes HTTP endpoints for Kubernetes probes:

- `GET /health` - Liveness probe (server is running)
- `GET /ready` - Readiness probe (server can accept requests)

### FR5: Structured Logging

All requests are logged with:
- Timestamp
- Request ID
- Subject (from token)
- Tool called
- Authorization decision (allowed/denied)
- Response status

Logs output as JSON for compatibility with cloud logging systems.

---

## Technical Architecture

### System Components

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         GKE Cluster (3 nodes)                                │
│                                                                              │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐      │
│  │ Node 1 (e2-small)  │  │ Node 2 (e2-small)  │  │ Node 3 (e2-small)  │      │
│  │                    │  │                    │  │                    │      │
│  │ System DaemonSets  │  │ System DaemonSets  │  │ System DaemonSets  │      │
│  │ ArgoCD pods        │  │ MCP Server Pod #1  │  │ MCP Server Pod #2  │      │
│  │ ESO pods           │  │                    │  │                    │      │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘      │
│                                                                              │
│  * Pod placement is illustrative; the K8s scheduler decides actual placement │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Namespace: mcp-prototype                                     │  │
│  │                                                               │  │
│  │  ┌─────────────────┐      ┌─────────────────────────┐        │  │
│  │  │  MCP Server Pod │      │  ConfigMap              │        │  │
│  │  │  ┌───────────┐  │      │  - Document content     │        │  │
│  │  │  │ Container │  │      │  - Server config        │        │  │
│  │  │  │ Port 8080 │  │      └─────────────────────────┘        │  │
│  │  │  └───────────┘  │                                          │  │
│  │  └────────┬────────┘      ┌─────────────────────────┐        │  │
│  │           │               │  External Secret        │        │  │
│  │           │               │  (synced from GCP SM)   │        │  │
│  │  ┌────────▼────────┐      │  - JWT signing key      │        │  │
│  │  │  K8s Service    │      └─────────────────────────┘        │  │
│  │  │  ClusterIP      │                                          │  │
│  │  └─────────────────┘                                          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Namespace: argocd                                            │  │
│  │  ArgoCD (watches Git repo, syncs Helm chart)                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     External Services                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ GitHub          │  │ GCP Artifact    │  │ GCP Secret     │  │
│  │ - Source code   │  │ Registry        │  │ Manager        │  │
│  │ - Helm charts   │  │ - Container     │  │ - JWT key      │  │
│  │                 │  │   images        │  │                │  │
│  └─────────────────┘  └─────────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| MCP Server | Python + `fastmcp` v2 | MCP protocol implementation with middleware support |
| Authentication | PyJWT | Token validation |
| Containerization | Docker | Package application |
| Container Registry | GCP Artifact Registry | Store container images |
| Orchestration | Google Kubernetes Engine | Run containers |
| Package Management | Helm | Kubernetes templating |
| GitOps / CD | ArgoCD | Continuous deployment |
| Secrets | GCP Secret Manager + External Secrets Operator | Secure secret injection |
| CI | GitHub Actions | Build and push images |

**Why `fastmcp` v2 instead of the official `mcp` SDK directly:**
The official `mcp` SDK includes a basic FastMCP class but lacks middleware hooks (`on_list_tools`, `on_call_tool`). The standalone `fastmcp` v2 package wraps the official SDK and adds these middleware capabilities, which are essential for our scope-based tool filtering. It also handles Streamable HTTP transport and Starlette integration internally, so we don't need a separate FastAPI/Starlette dependency. The `fastmcp` package depends on the official `mcp` SDK underneath, so it is not a competing implementation.

### GKE Cluster Infrastructure

The GKE cluster is provisioned with **3 nodes** to create a realistic Kubernetes environment. We run **2 replicas** of the MCP server to learn about multi-replica orchestration, and the 3rd node provides headroom for system components (ArgoCD, External Secrets Operator, CoreDNS, kube-proxy, etc.).

**Why 3 Nodes with 2 Replicas:**
- A single-node cluster is essentially just a VM with extra steps: Kubernetes provides no scheduling, failover, or distribution benefits
- 2 MCP server replicas let us observe how K8s distributes copies of the same application across nodes
- `e2-small` instances have only 2 GB RAM each: ArgoCD alone has multiple components (server, repo-server, application-controller) that need room alongside system DaemonSets
- 3 nodes give the scheduler enough resources to comfortably place everything without memory pressure
- Allows observing pod placement decisions (`kubectl get pods -o wide` shows which node each pod lands on)
- Demonstrates what happens when a node becomes unavailable (K8s reschedules pods to healthy nodes)

**Note:** Kubernetes does not dedicate whole nodes to specific workloads by default. Every node runs system DaemonSets (kube-proxy, etc.), and the scheduler places pods wherever resources are available. The 3-node setup simply ensures enough total capacity for all pods.

**Cluster Specification:**

| Setting | Value | Rationale |
|---------|-------|-----------|
| Cluster type | GKE Standard | Full control over node configuration (Autopilot abstracts away node management, which defeats the learning purpose) |
| Node count | 3 | 2 for MCP server replicas + headroom for system/platform pods |
| Machine type | `e2-small` (2 vCPU, 2 GB RAM) | Smallest viable size that can run system pods + our workloads |
| Node disk size | 30 GB | Enough for container images and system components |
| Region/Zone | Single zone (e.g., `europe-west1-b`) | Multi-zone is unnecessary for a prototype and doubles cost |
| Kubernetes version | Latest stable (default release channel) | Keeps things current without chasing bleeding edge |

**Cluster Provisioning:**

The cluster is created via `gcloud` CLI commands (not Terraform), keeping infrastructure setup simple and transparent:

```bash
# Create the GKE cluster with 3 nodes
gcloud container clusters create mcp-prototype \
  --zone europe-west1-b \
  --num-nodes 3 \
  --machine-type e2-small \
  --disk-size 30 \
  --release-channel regular \
  --workload-pool=<project-id>.svc.id.goog  # Enables Workload Identity for GCP Secret Manager access

# Get credentials for kubectl
gcloud container clusters get-credentials mcp-prototype --zone europe-west1-b
```

**Cost Considerations:**
- 3x `e2-small` instances run approximately $35-45/month
- Remember to delete the cluster when not actively working on the project: `gcloud container clusters delete mcp-prototype --zone europe-west1-b`
- Alternatively, resize to 0 nodes to stop compute costs while keeping the cluster config: `gcloud container clusters resize mcp-prototype --num-nodes 0 --zone europe-west1-b`

### Development Setup

**Package Management:** Uses `uv` (fast Python package manager) with `pyproject.toml`

```toml
# pyproject.toml
[project]
name = "mcp-auth-prototype"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2,<3",              # MCP server framework with middleware support (wraps official mcp SDK)
    "pyjwt>=2.8.0",               # JWT token validation
    "pydantic>=2.5.0",            # Data validation
    "pydantic-settings>=2.1.0",   # Configuration from environment variables
    "uvicorn>=0.24.0",            # ASGI server
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.25.0",  # For testing HTTP endpoints
    "ruff>=0.1.0",
]
```

**Local Development:**
```bash
# Install dependencies
uv sync

# Run server locally
uv run python src/server.py

# Run tests
uv run pytest

# Lint
uv run ruff check .
```

**Docker Integration:**
The Dockerfile uses uv for faster, reproducible builds with dependency caching.

### Repository Structure

```
mcp-auth-prototype/
├── src/
│   ├── __init__.py         # Package marker
│   ├── server.py           # MCP server implementation (fastmcp v2 with auth middleware)
│   ├── auth.py             # JWT token validation and scope extraction
│   ├── tools.py            # Tool definitions and scope mapping
│   └── config.py           # Configuration loading (pydantic-settings)
├── documents/
│   ├── public.md           # Public document content
│   └── confidential.md     # Confidential document content
├── scripts/
│   └── generate_token.py   # CLI utility to mint test JWT tokens
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # Shared test fixtures
│   ├── test_auth.py        # Token validation tests
│   └── test_tools.py       # Tool authorization tests
├── Dockerfile              # Multi-stage build with uv
├── .dockerignore
├── pyproject.toml          # Dependencies and project metadata
├── uv.lock                 # Locked dependencies (generated by uv)
├── helm/
│   └── mcp-server/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-dev.yaml
│       └── templates/
│           ├── _helpers.tpl
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── configmap.yaml
│           ├── externalsecret.yaml
│           ├── secretstore.yaml
│           └── serviceaccount.yaml
├── argocd/
│   └── application.yaml    # ArgoCD Application resource
├── .github/
│   └── workflows/
│       └── ci.yaml         # Build, test, push image, update Helm tag
├── IMPLEMENTATION_ROADMAP.md  # Step-by-step build plan with checkboxes
└── README.md
```

---

## Deployment Architecture

### CI Pipeline (GitHub Actions)

Trigger: Push to `main` branch

Steps:
1. Set up uv
2. Install dependencies (`uv sync`)
3. Run linter (`uv run ruff check`)
4. Run unit tests (`uv run pytest`)
5. Build Docker image (multi-stage build with uv)
6. Push to GCP Artifact Registry with tag `:<git-sha>`
7. Update `values.yaml` with new image tag
8. Commit and push Helm chart changes

**Docker Multi-Stage Build with uv:**
```dockerfile
# Stage 1: Build dependencies
FROM ghcr.io/astral-sh/uv:python3.11-bookworm AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src/ ./src/
COPY documents/ ./documents/
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "src/server.py"]
```

Benefits:
- **Faster builds**: uv is 10-100x faster than pip
- **Reproducible**: `uv.lock` ensures exact versions across environments
- **Better caching**: Docker layers cache effectively with uv

### CD Pipeline (ArgoCD)

ArgoCD monitors the GitHub repository and automatically syncs when Helm chart changes are detected.

Sync behavior:
- Auto-sync enabled for dev environment
- Rolling update strategy (zero downtime)
- Health checks must pass before marking deployment successful

### Secret Management Flow

```
GCP Secret Manager
       │
       │ External Secrets Operator polls
       ▼
K8s ExternalSecret resource
       │
       │ Creates/updates
       ▼
K8s Secret (native)
       │
       │ Mounted as env var
       ▼
MCP Server Pod
```

The JWT signing key is stored in GCP Secret Manager and synced to the cluster via External Secrets Operator. The application never sees the raw secret in code or config files.

---

## Security Requirements

### SR1: No Hardcoded Secrets

All secrets (JWT signing key) must be stored in GCP Secret Manager and injected at runtime.

### SR2: Least Privilege Service Account

The MCP server runs with a dedicated Kubernetes ServiceAccount that has minimal permissions:
- No cluster-admin
- No access to other namespaces
- Read-only access to its own secrets and configmaps

### SR3: Token Expiration

All tokens must have an expiration time. The server rejects expired tokens regardless of valid signatures.

### SR4: Audit Trail

All authorization decisions are logged with sufficient context to reconstruct access patterns.

---

## Testing Strategy

### Unit Tests

- Token validation logic (valid, expired, malformed, missing scopes)
- Tool authorization checks
- MCP protocol message handling

### Integration Tests

- End-to-end MCP connection with valid token
- Tool listing reflects authorized scopes
- Tool invocation returns expected content
- Unauthorized tool calls are rejected

### Manual Verification

- Deploy to GKE and verify pods are healthy
- Connect Claude Code (or MCP client) to the server
- Verify tool access matches token scopes
- Verify ArgoCD syncs on Helm chart changes

---

## Helm Chart Configuration

### values.yaml (defaults)

```yaml
replicaCount: 2

image:
  repository: <region>-docker.pkg.dev/<project>/mcp-server/mcp-auth-prototype
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8080

resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "256Mi"
    cpu: "200m"

env:
  LOG_LEVEL: "info"

externalSecret:
  enabled: true
  secretStore: gcp-secret-store
  remoteRef: mcp-jwt-signing-key

probes:
  liveness:
    path: /health
    initialDelaySeconds: 5
  readiness:
    path: /ready
    initialDelaySeconds: 5
```

---

## Developer Experience: Connecting Claude Code

### Initial Setup

A developer connects their Claude Code instance to the MCP server using the CLI:

```bash
# Add the MCP server with authentication
claude mcp add --transport http company-mcp https://mcp.company.internal/mcp \
  --header "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

Alternative JSON configuration for easier token updates:

```bash
claude mcp add-json company-mcp '{
  "type": "http",
  "url": "https://mcp.company.internal/mcp",
  "headers": {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}'
```

### Token Lifecycle Management

**Persistence:**
- MCP server configurations (including Bearer tokens) are stored in Claude Code's config file
- Tokens persist across Claude Code sessions - developers don't need to re-enter them each time
- Configuration location: `~/.config/claude/mcp.json` (Linux/Mac) or `%APPDATA%\claude\mcp.json` (Windows)

**Token Expiration:**
- When a token expires, the MCP server returns authentication errors
- The developer must update the token manually:

```bash
# Update existing server with new token
claude mcp remove company-mcp
claude mcp add --transport http company-mcp https://mcp.company.internal/mcp \
  --header "Authorization: Bearer <new-token>"
```

**Production Token Management Options:**

1. **Short-lived tokens with manual refresh** (prototype approach):
   - Developers request tokens from internal token service (e.g., `mcp-token-cli get --scope public:read,confidential:read`)
   - Tokens expire after 8 hours
   - Update MCP config when expired

2. **Long-lived tokens** (simpler but less secure):
   - Tokens expire after 30 days
   - Stored securely in developer's password manager
   - Rotated monthly

3. **OAuth2 with refresh tokens** (future enhancement):
   - Initial OAuth flow to get access + refresh token
   - Claude Code automatically refreshes expired tokens
   - Note: Currently has [known issues](https://github.com/anthropics/claude-code/issues/3515) in Claude Code

### Security Best Practices

**For Developers:**
- Never commit tokens to Git repositories
- Store tokens in environment variables or secure password managers
- Request minimal scopes needed for your work
- Rotate tokens when changing projects or teams

**For Platform Teams:**
- Implement token issuance service with audit logging
- Set reasonable token expiration (4-8 hours for development)
- Provide CLI tool for easy token management: `mcp-token-cli get`, `mcp-token-cli refresh`, `mcp-token-cli revoke`
- Monitor token usage and alert on suspicious patterns

### Example Developer Workflow

```bash
# Day 1: Initial setup
$ mcp-token-cli get --scope public:read,confidential:read
Token: eyJhbGc...
Expires: 2026-02-05 18:00:00 UTC (8 hours)

$ claude mcp add --transport http company-mcp https://mcp.company.internal/mcp \
  --header "Authorization: Bearer eyJhbGc..."
✓ Added MCP server 'company-mcp'
✓ Discovered 2 tools: get_public_info, get_confidential_info

# Day 1-N: Use Claude Code normally
$ claude
# Tools are automatically available in all sessions

# When token expires:
$ claude
⚠ MCP server 'company-mcp' authentication failed

$ mcp-token-cli refresh
Token: eyJhbGc...<new-token>
Expires: 2026-02-06 18:00:00 UTC (8 hours)

$ claude mcp add-json company-mcp '{
  "type": "http",
  "url": "https://mcp.company.internal/mcp",
  "headers": {"Authorization": "Bearer eyJhbGc...<new-token>"}
}'
✓ Updated MCP server 'company-mcp'
```

---

## Success Criteria

1. **Authentication works**: Requests without valid tokens are rejected with 401
2. **Authorization works**: Token scopes correctly limit available tools
3. **Deployment works**: `git push` triggers build and automatic deployment to GKE
4. **Secrets are secure**: JWT signing key is never in code or Git history
5. **Observable**: Logs show authentication and authorization decisions
6. **Demonstrable**: Can connect an MCP client and show differential access based on token
7. **Multi-replica orchestration**: 2 MCP server replicas are scheduled across the 3-node cluster, visible via `kubectl get pods -o wide`

---

## Decisions Log

Decisions made during planning, kept here for reference:

1. **MCP Transport**: Streamable HTTP (replaces deprecated HTTP+SSE). Handled by `fastmcp` v2 internally.
2. **MCP Library**: `fastmcp` v2 (standalone package) instead of the official `mcp` SDK directly. Reason: `fastmcp` v2 provides middleware hooks (`on_list_tools`, `on_call_tool`) essential for scope-based tool filtering. It wraps the official `mcp` SDK underneath.
3. **Token Issuance**: Generate tokens manually via `scripts/generate_token.py` CLI script. Production would need a token service.
4. **GKE Standard vs Autopilot**: GKE Standard. Autopilot abstracts away node management, which defeats the educational purpose.

## Open Questions

1. **External Secrets Operator**: Pre-install in cluster (via `helm install`) or include in Helm chart dependencies? Current plan: pre-install separately in Phase 5.
2. **Client Token Management**: For the prototype, manual token generation and configuration. Production would need OAuth2 with refresh tokens or a CLI token tool.

---

## References

- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io)
- [Helm Documentation](https://helm.sh/docs)
- [External Secrets Operator](https://external-secrets.io)
- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
