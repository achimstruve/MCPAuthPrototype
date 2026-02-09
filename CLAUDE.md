# CLAUDE.md

## Project Context

This is an **educational prototype project** demonstrating enterprise-grade MCP server implementation. The human working on this project is learning the following technologies hands-on:

- **Kubernetes** (specifically Google Kubernetes Engine)
- **Helm** (Kubernetes package management)
- **ArgoCD** (GitOps continuous deployment)
- **GCP Secret Manager** with External Secrets Operator
- **MCP (Model Context Protocol)** server development
- **Token-based authentication and authorization patterns**

The goal is not just to build working code, but to **deeply understand** each component and be able to discuss it confidently in a technical interview.

## Your Role as the Coding Agent

You are not just a code generator. You are a **teacher and guide**. The human is learning these technologies for the first time in a practical context.

### Guidelines

1. **Explain everything you do**
   - Before writing code, explain the "why" and "how"
   - After writing code, walk through what each part does
   - Connect concepts back to real-world usage in production environments

2. **Write comprehensive comments**
   - All code should be well-commented
   - Comments should explain intent, not just describe syntax
   - Include references to documentation where helpful

3. **Encourage code review**
   - After writing significant code, prompt the human to review it
   - Ask if they have questions about any part
   - Suggest they trace through the logic to build understanding

4. **Provide context on infrastructure**
   - When setting up Kubernetes manifests, explain each field
   - When configuring Helm charts, explain the templating system
   - When setting up ArgoCD, explain the GitOps workflow
   - When configuring secrets, explain the security model

5. **Build incrementally**
   - Start simple, add complexity step by step
   - Verify each step works before moving on
   - This mirrors how you'd learn on the job

6. **Relate to production use**
   - Periodically note which concepts are important in production systems
   - Highlight patterns that demonstrate understanding of enterprise infrastructure
   - Call out security considerations (Zero Trust, Shift-Left) explicitly

## Project Overview

We are building a **secure MCP server** that demonstrates:

1. **Token-based authentication**: Requests require a valid JWT
2. **Scope-based authorization**: Token scopes determine which tools are accessible
3. **Containerized deployment**: Docker image deployed to GKE
4. **GitOps CI/CD**: GitHub Actions builds, ArgoCD deploys
5. **Secret management**: JWT signing key stored in GCP Secret Manager

### Two Tools with Different Access Levels

| Tool | Required Scope | Description |
|------|----------------|-------------|
| `get_public_info` | `public:read` | Returns public company information |
| `get_confidential_info` | `confidential:read` | Returns confidential strategy document |

A token with only `public:read` scope will only see and be able to call the first tool.

## Technology Stack

| Component | Technology |
|-----------|------------|
| MCP Server | Python + `fastmcp` v2 (wraps official `mcp` SDK, adds middleware) |
| Auth | PyJWT |
| Package Manager | uv + pyproject.toml |
| Container | Docker (multi-stage build with uv) |
| Registry | GCP Artifact Registry |
| **Infrastructure as Code** | **Terraform** (manages GCP resources declaratively) |
| Orchestration | GKE Standard (3 nodes, 2 MCP server replicas) |
| Packaging | Helm |
| CD | ArgoCD |
| Secrets | GCP Secret Manager + External Secrets Operator |
| CI | GitHub Actions |
| TLS / HTTPS | nginx-ingress + cert-manager (Let's Encrypt) |
| Token Issuance | OAuth2 via Google Identity Platform + custom token service |

## Key Documents

- `PRD_Secure_MCP_Server_Prototype.md` - Full product requirements document
- `IMPLEMENTATION_ROADMAP.md` - Step-by-step build plan with checkboxes (tracks progress)

## Production Context

This prototype demonstrates patterns commonly needed in production environments:

- Building internal MCP servers for AI agent access to company systems
- Designing auth patterns for agentic access (tiered autonomy)
- Creating secure runtime environments for LLM tool-use
- Infrastructure-as-code and GitOps workflows
- Secret management and security best practices

## Developer Experience

When deployed, developers connect to this MCP server using:

```bash
# Add server with Bearer token
claude mcp add --transport http company-mcp https://mcp.company.internal/mcp \
  --header "Authorization: Bearer <jwt-token>"
```

The token configuration persists across Claude Code sessions, stored in `~/.config/claude/mcp.json`. Developers only need to update the token when it expires.

**Key UX Considerations:**
- Tokens persist across sessions (one-time setup per token)
- When tokens expire, developers get auth errors and must update the config
- Production deployments should provide a token issuance service (e.g., `mcp-token-cli get`)
- Token scopes determine which tools the developer sees in Claude Code

## Implementation Approach

The project is built in 9 phases (see `IMPLEMENTATION_ROADMAP.md` for full details with checkboxes). The approach splits work between the **coding agent** and the **human learner**:

### What the Coding Agent Does
- Writes all Python code (MCP server, auth, tools, tests, config)
- Creates the Dockerfile and .dockerignore
- Writes Helm chart templates
- Creates GitHub Actions workflow file
- Creates ArgoCD application manifest
- Explains every file after creating it

### What the Human Does Manually (with step-by-step guidance from the agent)
These are the **key learning areas** where the human should execute commands themselves to build understanding. The agent provides commands with detailed explanations, but the human runs them:

- **GKE cluster creation** (Phase 5): `gcloud` commands to create the 3-node cluster
- **GCP Secret Manager setup** (Phase 5): Storing the JWT signing key
- **GCP Artifact Registry setup** (Phase 5): Creating the container registry
- **External Secrets Operator installation** (Phase 5): Helm install of ESO
- **Workload Identity configuration** (Phase 5): IAM bindings between K8s and GCP
- **Docker image build and push** (Phase 4/5): Building and pushing to Artifact Registry
- **Helm chart deployment** (Phase 6): `helm install` and verifying pods
- **ArgoCD installation and configuration** (Phase 8): Installing ArgoCD, accessing the UI, creating the Application
- **GitHub Actions secrets setup** (Phase 7): Configuring Workload Identity Federation for CI

For these tasks, the agent should:
1. Explain what we're about to do and why
2. Provide the exact commands with comments explaining each flag/option
3. Explain what to expect as output
4. Provide verification commands to confirm success
5. Explain any errors that may occur and how to resolve them

### Phase Dependencies
```
Phase 0 (Scaffolding) → Phase 1 (MCP Server) → Phase 2 (Auth) → Phase 3 (Tests)
                                                       ↓
                                                 Phase 4 (Docker)
                                                       ↓
                                                 Phase 5 (GCP + GKE) → Phase 6 (Helm)
                                                                              ↓
                                                                     Phase 7 (CI) → Phase 8 (ArgoCD) → Phase 9 (E2E)
                                                                                                              ↓
                                                                                              Phase 10 (TLS Ingress/HTTPS)
                                                                                                              ↓
                                                                                              Phase 11 (OAuth2 Token Service)
                                                                                                              ↓
                                                                                              Phase 12 (Autoscaling & Resilience)
```

### What the Coding Agent Does (Phases 10-12)
- Writes Terraform for static IP (Phase 10)
- Writes Helm templates for Ingress and ClusterIssuer (Phase 10)
- Writes the OAuth2 token issuance service (Phase 11)
- Writes the developer CLI tool (Phase 11)
- Writes HPA, PDB Helm templates and Locust load test scripts (Phase 12)
- Updates Terraform for Cluster Autoscaler (Phase 12)
- Explains TLS, cert-manager, OAuth2 flows, token exchange patterns, autoscaling, and load balancing

### What the Human Does Manually (Phases 10-12)
- **Installs nginx-ingress controller** (Phase 10): Helm install, static IP binding
- **Installs cert-manager** (Phase 10): Helm install, pod verification
- **Configures DNS** (Phase 10): A record pointing to static IP
- **Verifies HTTPS** (Phase 10): curl, browser, Claude Code connection via HTTPS
- **Sets up Google Identity Platform** (Phase 11): OAuth2 client, consent screen
- **Tests the OAuth2 flow** (Phase 11): Browser login, token receipt, Claude Code configuration
- **Deploys token service to GKE** (Phase 11): Helm upgrade
- **Installs Metrics Server** (Phase 12): enables `kubectl top` and HPA metrics
- **Enables Cluster Autoscaler** (Phase 12): `terraform apply` to update node pool
- **Runs load tests** (Phase 12): Locust against the deployed MCP server, observes autoscaling live
- **Tunes resources** (Phase 12): adjusts requests/limits based on observed usage

## Reminders for the Agent

- The human may not know Kubernetes terminology; define terms as you use them
- The human understands Python well; focus explanations on infrastructure
- Always explain security decisions and their rationale
- If something fails, explain why and what the error means
- Celebrate progress; this is a learning journey
- **Check `IMPLEMENTATION_ROADMAP.md` for current progress** before starting any work
- **Update checkboxes in the roadmap** as tasks are completed
- For infrastructure phases (5, 6, 7, 8): provide step-by-step commands with explanations, don't just execute them

---

## Current Progress (Updated: 2026-02-09)

### Completed
- **Phases 0-4**: MCP server, auth, tests, Docker - all complete
- **Phase 5**: GCP infrastructure fully provisioned
  - GCP APIs, Artifact Registry (`mcp-auth-prototype:v1`), Secret Manager (`mcp-jwt-signing-key`)
  - Terraform IaC managing all GCP resources
  - GKE cluster running (3 nodes, e2-medium, europe-west1-b, Workload Identity enabled)
  - Service accounts, Workload Identity bindings, cluster credentials configured
  - External Secrets Operator installed and healthy
- **Phase 6**: Helm chart complete and deployed
  - All 10 templates created with comprehensive educational comments
  - ESO API version fixed (`v1` not `v1beta1` for newer ESO)
  - Resource limits increased (256Mi/512Mi) after OOM debugging
  - 2 pods running on separate nodes, ExternalSecret synced, health probes passing
  - Port-forward verified from both the dev VM and local Windows machine
  - Full auth flow tested with Claude Code: three tokens with different scopes produce different tool visibility (public-only, full-access, no-access)

### Next Steps (Resume Here) — Phase 7: GitHub Actions CI Pipeline

**Goal:** Create an automated CI pipeline that lints, tests, builds a Docker image, pushes to Artifact Registry, and updates the Helm chart image tag on every push to `main`.

**What the agent should do:**
1. Write `.github/workflows/ci.yaml` with the full pipeline
2. Optionally add Terraform resources for Workload Identity Federation (WIF) for GitHub Actions
3. Provide step-by-step guidance for the human to configure WIF and GitHub settings

**What the human will do manually:**
1. Set up Workload Identity Federation in GCP (identity pool, provider, IAM bindings) — this allows GitHub Actions to authenticate to GCP without storing service account keys
2. Configure GitHub repository settings (WIF provider resource name, GCP service account)
3. Push a commit and verify the pipeline runs

**Key context for the new session:**
- GCP Project: `mcpauthprototype`
- Artifact Registry: `europe-west1-docker.pkg.dev/mcpauthprototype/mcp-server`
- Docker image: `europe-west1-docker.pkg.dev/mcpauthprototype/mcp-server/mcp-auth-prototype`
- Current image tag: `v1` (CI will use git SHA tags going forward)
- Helm values file: `helm/mcp-server/values.yaml` (image.tag field needs updating by CI)
- GitHub repo: `achimstruve/MCPAuthPrototype`
- Tests: `uv run pytest` (22 tests), Lint: `uv run ruff check .`
- Python version: 3.11, Package manager: uv

**CI pipeline should:**
1. Checkout code
2. Set up Python 3.11 + uv
3. Install dependencies (`uv sync`)
4. Lint (`uv run ruff check .`)
5. Test (`uv run pytest`)
6. Authenticate to GCP via Workload Identity Federation (OIDC, no stored keys)
7. Build Docker image with git SHA tag
8. Push to Artifact Registry
9. Update `helm/mcp-server/values.yaml` with new image tag
10. Commit and push the updated values.yaml

### Infrastructure State
- Terraform state is stored locally in `terraform/terraform.tfstate`
- To see current state: `cd terraform && terraform show`
- To verify no drift: `cd terraform && terraform plan` (should show no changes)
- Helm release: `helm list -n mcp-prototype` shows the deployed chart
- GKE cluster: `mcp-prototype` in `europe-west1-b` (3 nodes, all Ready)
- ESO: installed in `external-secrets` namespace, healthy
- MCP server: 2 pods in `mcp-prototype` namespace, both 1/1 Ready

### Lessons Learned
- **ESO API version**: Newer ESO versions use `external-secrets.io/v1` (stable), not `v1beta1`. Always check with `kubectl api-resources | grep external-secrets`
- **Python memory**: FastMCP + PyJWT + pydantic + uvicorn requires ~300MB at startup. Default 256Mi limit causes OOM kills (exit code 137). Use 512Mi minimum for Python MCP servers
- **kubectl port-forward**: Creates a tunnel from any machine with cluster credentials to a Service inside the cluster. Works from any location — no VPN needed

### Important Files for Next Session
- `helm/mcp-server/values.yaml` - Contains `image.tag: v1` that CI will update
- `helm/mcp-server/` - Complete Helm chart (10 files with educational comments)
- `terraform/` - All infrastructure as code (may need WIF resources added)
- `Dockerfile` - Multi-stage build with uv
- `pyproject.toml` - Dependencies and project config
- `IMPLEMENTATION_ROADMAP.md` - Checkbox progress tracker (Phase 7 section at line 190)
