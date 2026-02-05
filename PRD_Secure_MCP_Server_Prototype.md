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
4. Gain hands-on experience with the Strike technology stack

## Non-Goals

- Production-grade high availability (single replica is acceptable)
- Complex RAG or vector database integration
- Fine-grained RBAC beyond two authorization tiers
- Custom domain or TLS termination (cluster-internal only)

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
┌─────────────────────────────────────────────────────────────────┐
│                        GKE Cluster                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Namespace: mcp-prototype                                 │  │
│  │                                                           │  │
│  │  ┌─────────────────┐      ┌─────────────────────────┐    │  │
│  │  │  MCP Server Pod │      │  ConfigMap              │    │  │
│  │  │  ┌───────────┐  │      │  - Document content     │    │  │
│  │  │  │ Container │  │      │  - Server config        │    │  │
│  │  │  │ Port 8080 │  │      └─────────────────────────┘    │  │
│  │  │  └───────────┘  │                                      │  │
│  │  └────────┬────────┘      ┌─────────────────────────┐    │  │
│  │           │               │  External Secret        │    │  │
│  │           │               │  (synced from GCP SM)   │    │  │
│  │  ┌────────▼────────┐      │  - JWT signing key      │    │  │
│  │  │  K8s Service    │      └─────────────────────────┘    │  │
│  │  │  ClusterIP      │                                      │  │
│  │  └─────────────────┘                                      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Namespace: argocd                                        │  │
│  │  ArgoCD (watches Git repo, syncs Helm chart)              │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

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
| MCP Server | Python + `mcp` library | MCP protocol implementation |
| Web Framework | FastAPI or Starlette | HTTP transport for MCP |
| Authentication | PyJWT | Token validation |
| Containerization | Docker | Package application |
| Container Registry | GCP Artifact Registry | Store container images |
| Orchestration | Google Kubernetes Engine | Run containers |
| Package Management | Helm | Kubernetes templating |
| GitOps / CD | ArgoCD | Continuous deployment |
| Secrets | GCP Secret Manager + External Secrets Operator | Secure secret injection |
| CI | GitHub Actions | Build and push images |

### Repository Structure

```
mcp-auth-prototype/
├── src/
│   ├── server.py           # MCP server implementation
│   ├── auth.py             # Token validation logic
│   ├── tools.py            # Tool definitions
│   └── config.py           # Configuration loading
├── documents/
│   ├── public.md           # Public document content
│   └── confidential.md     # Confidential document content
├── Dockerfile
├── requirements.txt
├── helm/
│   └── mcp-server/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-dev.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── configmap.yaml
│           ├── externalsecret.yaml
│           └── serviceaccount.yaml
├── .github/
│   └── workflows/
│       └── ci.yaml         # Build, test, push image
└── README.md
```

---

## Deployment Architecture

### CI Pipeline (GitHub Actions)

Trigger: Push to `main` branch

Steps:
1. Run unit tests
2. Build Docker image
3. Push to GCP Artifact Registry with tag `:<git-sha>`
4. Update `values.yaml` with new image tag
5. Commit and push Helm chart changes

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
replicaCount: 1

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

## Success Criteria

1. **Authentication works**: Requests without valid tokens are rejected with 401
2. **Authorization works**: Token scopes correctly limit available tools
3. **Deployment works**: `git push` triggers build and automatic deployment to GKE
4. **Secrets are secure**: JWT signing key is never in code or Git history
5. **Observable**: Logs show authentication and authorization decisions
6. **Demonstrable**: Can connect an MCP client and show differential access based on token

---

## Open Questions

1. **MCP Transport**: Use HTTP+SSE or stdio over WebSocket? HTTP+SSE is simpler for containerized deployment.
2. **Token Issuance**: For the prototype, generate tokens manually via a CLI script. Production would need a token service.
3. **External Secrets Operator**: Pre-install in cluster or include in Helm chart dependencies?

---

## References

- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io)
- [Helm Documentation](https://helm.sh/docs)
- [External Secrets Operator](https://external-secrets.io)
- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
