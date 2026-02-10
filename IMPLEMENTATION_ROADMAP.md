# Implementation Roadmap

This document tracks the step-by-step implementation of the Secure MCP Server Prototype. Check boxes as tasks are completed. See `PRD_Secure_MCP_Server_Prototype.md` for full requirements and `CLAUDE.md` for agent guidelines.

**Legend:**
- Tasks marked with **[AGENT]** are written by the coding agent
- Tasks marked with **[HUMAN]** are executed manually by the human (agent provides step-by-step guidance with explanations)
- Tasks marked with **[BOTH]** involve the agent writing files and the human verifying

---

## Phase 0: Project Scaffolding

**Goal:** Initialize the Python project with uv, create the directory structure, configure tooling.

- [x] **[AGENT]** Create `pyproject.toml` with dependencies (`fastmcp>=2,<3`, `pyjwt`, `pydantic-settings`, `uvicorn`) and dev dependencies (`pytest`, `pytest-asyncio`, `httpx`, `ruff`)
- [x] **[AGENT]** Create directory structure: `src/`, `documents/`, `tests/`, `scripts/` with `__init__.py` files
- [x] **[AGENT]** Extend `.gitignore` with Python patterns (`.venv/`, `__pycache__/`, `*.pyc`, `.env`, `dist/`, etc.)
- [x] **[BOTH]** Run `uv sync` to generate `uv.lock` and verify dependencies resolve
- [x] **[BOTH]** Run `uv run ruff check .` to verify linter works

**Verify before moving on:** `uv sync` succeeds, `uv run python -c "import fastmcp; print(fastmcp.__version__)"` prints a version number.

---

## Phase 1: MCP Server with Tools (No Auth)

**Goal:** A working MCP server with two tools, health endpoints, and Streamable HTTP transport. No authentication yet: just get MCP protocol working.

- [x] **[AGENT]** Create `src/config.py`: pydantic-settings configuration loaded from environment variables (host, port, log level, JWT secret, documents directory)
- [x] **[AGENT]** Create `src/tools.py`: tool definitions with scope mapping (`TOOL_SCOPE_MAP` dict mapping tool names to required scopes)
- [x] **[AGENT]** Create `src/server.py`: MCP server using `fastmcp.FastMCP` with two tools (`get_public_info`, `get_confidential_info`), health endpoint (`/health`), and readiness endpoint (`/ready`)
- [x] **[AGENT]** Create `documents/public.md`: sample public company information document
- [x] **[AGENT]** Create `documents/confidential.md`: sample confidential strategy document
- [x] **[BOTH]** Start server locally with `uv run python -m src.server`
- [x] **[BOTH]** Test health endpoint: `curl http://localhost:8080/health`
- [x] **[BOTH]** Test MCP connection: connect an MCP client and verify both tools are listed and callable

**Verify before moving on:** Server starts, health endpoint returns 200, both tools return document content.

---

## Phase 2: Authentication and Authorization

**Goal:** Add JWT validation and scope-based tool filtering. Requests without valid tokens are rejected. Tool list is filtered by token scopes.

- [x] **[AGENT]** Create `src/auth.py`: JWT token validation using PyJWT (extract Bearer token from header, validate signature and expiration, extract scopes from claims, return `TokenInfo` dataclass)
- [x] **[AGENT]** Update `src/server.py`: add `fastmcp` middleware (`on_list_tools` to filter tool list by scope, `on_call_tool` to reject unauthorized calls), add structured JSON logging for all auth decisions
- [x] **[AGENT]** Create `scripts/generate_token.py`: CLI utility to generate JWT tokens with configurable subject, scopes, secret, and expiration
- [x] **[BOTH]** Generate test tokens with different scopes and verify:
  - No token: request rejected
  - Token with `public:read`: only `get_public_info` visible
  - Token with both scopes: both tools visible
  - Expired token: request rejected
  - Calling unauthorized tool: permission denied error
- [x] **[BOTH]** Verify structured JSON logs show auth decisions (subject, scopes, tool, allowed/denied)

**Verify before moving on:** Auth works end-to-end. Different tokens produce different tool lists. Unauthorized calls are rejected. Logs capture all decisions.

---

## Phase 3: Tests

**Goal:** Unit tests for auth logic and integration tests for the MCP server.

- [x] **[AGENT]** Create `tests/conftest.py`: shared fixtures (token generation helpers, test client setup, known test secret key)
- [x] **[AGENT]** Create `tests/test_auth.py`: test cases for `validate_token()`:
  - Valid token decodes correctly
  - Expired token raises AuthError
  - Malformed token raises AuthError
  - Token with wrong signing key raises AuthError
  - Missing scope claim defaults to empty list
  - Non-list scope claim raises AuthError
- [x] **[AGENT]** Create `tests/test_tools.py`: test cases for tool authorization:
  - Token with `public:read` sees only `get_public_info`
  - Token with both scopes sees both tools
  - Token with no scopes sees no tools
  - Unauthorized tool call returns permission denied
  - Authorized tool call returns document content
- [x] **[BOTH]** Run `uv run pytest -v` and verify all tests pass
- [x] **[BOTH]** Run `uv run ruff check .` and verify no lint errors

**Verify before moving on:** All tests pass. Linter is clean.

---

## Phase 4: Dockerize

**Goal:** Multi-stage Docker image using uv for fast, reproducible builds.

- [x] **[AGENT]** Create `Dockerfile`: multi-stage build (Stage 1: `ghcr.io/astral-sh/uv:python3.11-bookworm` for dependency install, Stage 2: `python:3.11-slim` for runtime with only `.venv`, `src/`, `documents/`)
- [x] **[AGENT]** Create `.dockerignore`: exclude `.git`, `.venv`, `__pycache__`, `tests/`, `helm/`, `.github/`, markdown files except documents
- [x] **[HUMAN]** Build Docker image: `docker build -t mcp-auth-prototype:local .`
- [x] **[HUMAN]** Run container: `docker run -p 8080:8080 -e MCP_JWT_SECRET_KEY=test-secret mcp-auth-prototype:local`
- [x] **[HUMAN]** Test health endpoint: `curl http://localhost:8080/health`
- [x] **[HUMAN]** Generate a token with matching secret and verify auth works against the container

**Verify before moving on:** Docker image builds, container starts and responds to health checks, auth works with environment-injected secret.

**Key learning:** Multi-stage builds, 12-factor app config (env vars), Docker layer caching with uv, `.dockerignore` purpose.

---

## Phase 5: GCP Infrastructure Setup (with Terraform)

**Goal:** Set up all GCP infrastructure using Terraform for Infrastructure as Code (IaC): APIs, Artifact Registry, Secret Manager, GKE cluster, and IAM for Workload Identity. Then install External Secrets Operator via Helm.

> **This is a key learning phase.** We use a hybrid approach: some resources were created manually first (to learn the concepts), then we adopt Terraform to manage infrastructure declaratively. Terraform imports existing resources into its state.

### 5a: GCP Project and APIs (Manual - Completed)
- [x] **[HUMAN]** Set active GCP project: `gcloud config set project mcpauthprototype`
- [x] **[HUMAN]** Enable required APIs: Container, Artifact Registry, Secret Manager

### 5b: Artifact Registry (Manual - Completed)
- [x] **[HUMAN]** Create Docker repository in Artifact Registry (region: `europe-west1`)
- [x] **[HUMAN]** Configure Docker authentication for the registry
- [x] **[HUMAN]** Tag and push the local Docker image to Artifact Registry
- [x] **[HUMAN]** Verify image appears: `gcloud artifacts docker images list ...`

### 5c: Secret Manager (Manual - Completed)
- [x] **[HUMAN]** Generate a strong JWT signing key
- [x] **[HUMAN]** Store it in GCP Secret Manager as `mcp-jwt-signing-key`
- [x] **[HUMAN]** Verify it can be read back: `gcloud secrets versions access latest --secret=mcp-jwt-signing-key`

### 5d: Terraform Setup (Completed)
- [x] **[AGENT]** Create `terraform/main.tf`: provider configuration and terraform settings
- [x] **[AGENT]** Create `terraform/variables.tf`: input variables (project_id, region, zone)
- [x] **[AGENT]** Create `terraform/outputs.tf`: output values (cluster endpoint, registry URL)
- [x] **[AGENT]** Create `terraform/artifact-registry.tf`: Artifact Registry repository resource
- [x] **[AGENT]** Create `terraform/secret-manager.tf`: Secret Manager secret resource (structure only)
- [x] **[AGENT]** Create `terraform/gke.tf`: GKE cluster resource with Workload Identity
- [x] **[AGENT]** Create `terraform/iam.tf`: Service accounts and Workload Identity bindings
- [x] **[AGENT]** Update `.gitignore`: add Terraform patterns (`.terraform/`, `*.tfstate`, `*.tfvars`)
- [x] **[HUMAN]** Install Terraform CLI
- [x] **[HUMAN]** Run `terraform init` to initialize providers
- [x] **[HUMAN]** Import existing resources into Terraform state:
  - `terraform import google_artifact_registry_repository.mcp_server ...`
  - `terraform import google_secret_manager_secret.jwt_signing_key ...`
- [x] **[HUMAN]** Run `terraform plan` to verify no changes needed for imported resources
- [x] **[HUMAN]** Run `terraform apply` to create GKE cluster and IAM resources
- [x] **[HUMAN]** Get cluster credentials: `gcloud container clusters get-credentials mcp-prototype --zone europe-west1-b`
- [x] **[HUMAN]** Verify: `kubectl get nodes` shows 3 nodes in Ready state

### 5e: External Secrets Operator (Helm)
- [x] **[HUMAN]** Add ESO Helm repo and install ESO into the cluster
- [x] **[HUMAN]** Verify ESO pods are running: `kubectl get pods -n external-secrets`

**Verify before moving on:** 3 nodes running, image in Artifact Registry, secret in Secret Manager, ESO installed and healthy, all resources tracked in Terraform state.

**Key learning:**
- **Terraform**: Declarative IaC, state management, resource imports, plan/apply workflow
- **GKE**: Standard vs Autopilot, node pools, Workload Identity
- **Workload Identity**: Why it's better than service account keys
- **Secret Manager**: Why not K8s secrets directly (audit, versioning, central management)
- **ESO**: Bridges external secrets to Kubernetes

---

## Phase 6: Helm Chart

**Goal:** Package all Kubernetes resources into a Helm chart. Deploy the MCP server to GKE with 2 replicas.

> **This is a key learning phase.** The agent writes the Helm templates with detailed comments. The human reviews each template to understand the Kubernetes resources, then runs `helm install` manually.

- [x] **[AGENT]** Create `helm/mcp-server/Chart.yaml`: chart metadata (apiVersion v2, name, version, appVersion)
- [x] **[AGENT]** Create `helm/mcp-server/values.yaml`: default values (replicaCount: 2, image, service port 8080, resource requests/limits, probe config, externalSecret config)
- [x] **[AGENT]** Create `helm/mcp-server/values-dev.yaml`: dev environment overrides
- [x] **[AGENT]** Create `helm/mcp-server/templates/_helpers.tpl`: common template helpers (labels, names)
- [x] **[AGENT]** Create `helm/mcp-server/templates/deployment.yaml`: Deployment with 2 replicas, container config, probes, env vars from Secret, resource limits
- [x] **[AGENT]** Create `helm/mcp-server/templates/service.yaml`: ClusterIP Service on port 8080
- [x] **[AGENT]** Create `helm/mcp-server/templates/configmap.yaml`: document content mounted into pods
- [x] **[AGENT]** Create `helm/mcp-server/templates/serviceaccount.yaml`: dedicated ServiceAccount with Workload Identity annotation
- [x] **[AGENT]** Create `helm/mcp-server/templates/externalsecret.yaml`: ExternalSecret resource to sync JWT key from GCP Secret Manager
- [x] **[AGENT]** Create `helm/mcp-server/templates/secretstore.yaml`: SecretStore connecting ESO to GCP Secret Manager
- [x] **[BOTH]** Lint chart: `helm lint helm/mcp-server/`
- [x] **[BOTH]** Render templates locally: `helm template mcp-server helm/mcp-server/` and review output
- [x] **[HUMAN]** Create namespace: `kubectl create namespace mcp-prototype`
- [x] **[HUMAN]** Install chart: `helm install mcp-server helm/mcp-server/ -n mcp-prototype`
- [x] **[HUMAN]** Verify pods are running across nodes: `kubectl get pods -n mcp-prototype -o wide`
- [x] **[HUMAN]** Verify service exists: `kubectl get svc -n mcp-prototype`
- [x] **[HUMAN]** Check logs: `kubectl logs -n mcp-prototype -l app.kubernetes.io/name=mcp-server`
- [x] **[HUMAN]** Port-forward and test: `kubectl port-forward svc/mcp-server -n mcp-prototype 8080:8080`

**Verify before moving on:** 2 pods running on different nodes, service routing traffic, health probes passing, JWT secret injected from Secret Manager.

**Key learning:** Helm templating (Go templates, values, helpers), Deployment vs Pod, ClusterIP Service, ConfigMap vs Secret, resource requests vs limits, liveness vs readiness probes, ExternalSecret/SecretStore pattern, `helm template` for debugging.

---

## Phase 7: GitHub Actions CI Pipeline

**Goal:** Automated pipeline that lints, tests, builds the Docker image, pushes to Artifact Registry, and updates the Helm chart image tag.

> **This is a key learning phase.** The agent writes the workflow file. The human configures GitHub secrets and Workload Identity Federation manually.

- [x] **[AGENT]** Create `.github/workflows/ci.yaml`: complete CI pipeline (checkout, setup uv, lint, test, authenticate to GCP via Workload Identity Federation, build Docker image with git SHA tag, push to Artifact Registry, update values.yaml image tag, commit and push)
- [x] **[AGENT]** Create `terraform/github-wif.tf`: Workload Identity Federation resources (pool, OIDC provider, CI service account, IAM bindings) — managed as IaC
- [ ] **[HUMAN]** Apply Terraform to create WIF resources, then configure GitHub repository variable
- [ ] **[HUMAN]** Configure required GitHub repository settings (Workload Identity Provider resource name, GCP service account)
- [ ] **[HUMAN]** Push a commit to `main` and verify the pipeline runs successfully
- [ ] **[HUMAN]** Verify image appears in Artifact Registry with the git SHA tag
- [ ] **[HUMAN]** Verify `values.yaml` was updated with the new image tag

**Verify before moving on:** Push to main triggers green pipeline, image pushed to registry, Helm values updated in Git.

**Key learning:** GitHub Actions workflow syntax, Workload Identity Federation (OIDC-based auth, no stored keys), why git SHA tags over `latest`, the GitOps image tag update pattern.

---

## Phase 8: ArgoCD

**Goal:** Install ArgoCD, create an Application that watches the Helm chart, and verify auto-sync on changes.

> **This is a key learning phase.** The agent writes the ArgoCD Application manifest. The human installs ArgoCD and configures it manually.

- [ ] **[HUMAN]** Install ArgoCD in the cluster (namespace: `argocd`)
- [ ] **[HUMAN]** Access ArgoCD UI via port-forward, retrieve initial admin password
- [ ] **[AGENT]** Create `argocd/application.yaml`: ArgoCD Application resource (source: GitHub repo + helm/mcp-server path, destination: mcp-prototype namespace, auto-sync enabled)
- [ ] **[HUMAN]** Apply the Application: `kubectl apply -f argocd/application.yaml`
- [ ] **[HUMAN]** Verify in ArgoCD UI: Application shows as Synced and Healthy
- [ ] **[HUMAN]** Test auto-sync: push a code change, wait for CI to update the image tag, watch ArgoCD deploy the new version
- [ ] **[HUMAN]** Verify rolling update: observe old pods being replaced by new ones with `kubectl get pods -n mcp-prototype -w`

**Verify before moving on:** ArgoCD UI shows healthy application, auto-sync works on git push, rolling updates happen with zero downtime.

**Key learning:** GitOps principle (Git as single source of truth), ArgoCD sync loop (desired vs actual state), auto-sync vs manual sync, self-healing (ArgoCD reverts manual changes), rolling update strategy with 2 replicas.

---

## Phase 9: End-to-End Verification

**Goal:** Full pipeline test and documentation.

- [ ] **[BOTH]** End-to-end test: push code change → CI pipeline → ArgoCD sync → rolling update → verify new version is running
- [ ] **[HUMAN]** Connect Claude Code (or MCP client) via port-forward with different tokens:
  - Public-only token: verify only `get_public_info` is visible and callable
  - Full-access token: verify both tools are visible and callable
  - No token: verify rejection
  - Expired token: verify rejection
- [ ] **[HUMAN]** Verify pod distribution: `kubectl get pods -n mcp-prototype -o wide` shows pods on different nodes
- [ ] **[HUMAN]** Verify structured JSON logs: `kubectl logs -n mcp-prototype -l app.kubernetes.io/name=mcp-server`
- [ ] **[HUMAN]** Test resilience: `kubectl delete pod <pod-name> -n mcp-prototype` and observe K8s recreating it
- [ ] **[AGENT]** Update `README.md` with project overview, architecture summary, setup instructions, and usage examples

**Verify:** All success criteria from the PRD are met (auth works, authorization works, deployment works, secrets are secure, observable, demonstrable, multi-replica orchestration visible).

---

## Phase 10: TLS Ingress (HTTPS)

**Goal:** Expose the MCP server externally via HTTPS with automatic TLS certificate management. This is what makes the application production-ready — all traffic between clients and the cluster is encrypted, protecting JWT tokens and confidential document content in transit.

> **This is a key learning phase.** Without TLS, anyone on the network path can read the JWT tokens in the Authorization header and the confidential data returned by tools. TLS termination at the Ingress is the standard production pattern: the Ingress handles HTTPS, and traffic within the cluster stays plain HTTP (which is acceptable because the internal network is trusted).

### Architecture

```
Client (Claude Code)
  │
  │  HTTPS (encrypted)
  ▼
┌─────────────────────────────┐
│  Ingress Controller         │
│  (nginx-ingress)            │
│  TLS termination here       │
│  cert from cert-manager     │
└─────────────┬───────────────┘
              │ HTTP (internal, trusted)
              ▼
┌─────────────────────────────┐
│  ClusterIP Service          │
│  → MCP Server Pods          │
└─────────────────────────────┘
```

### 10a: Reserve a Static IP
- [ ] **[AGENT]** Add `terraform/ingress.tf`: reserve a GCP global static IP address
- [ ] **[HUMAN]** Run `terraform apply` to create the static IP
- [ ] **[HUMAN]** Note the IP address from `terraform output` (needed for DNS)

### 10b: DNS Setup
- [ ] **[HUMAN]** Configure a DNS A record pointing to the static IP (e.g., `mcp.yourdomain.com → <static-ip>`)
- [ ] **[HUMAN]** Verify DNS resolution: `dig mcp.yourdomain.com` returns the static IP

> **Note:** If you don't have a domain, you can use a free service like [nip.io](https://nip.io) for prototyping (e.g., `mcp.<static-ip>.nip.io` resolves to `<static-ip>` automatically). For a production demo, a real domain is recommended.

### 10c: Install Ingress Controller
- [ ] **[HUMAN]** Install the nginx-ingress controller via Helm into the cluster
- [ ] **[HUMAN]** Configure it to use the reserved static IP via the `loadBalancerIP` setting
- [ ] **[HUMAN]** Verify the ingress controller pod is running and has the external IP assigned

### 10d: Install cert-manager
- [ ] **[HUMAN]** Install cert-manager via Helm (manages TLS certificates automatically)
- [ ] **[HUMAN]** Verify cert-manager pods are running: `kubectl get pods -n cert-manager`
- [ ] **[AGENT]** Create `helm/mcp-server/templates/cluster-issuer.yaml`: ClusterIssuer resource for Let's Encrypt (configures how certificates are obtained via ACME/HTTP-01 challenge)

### 10e: Add Ingress Resource to Helm Chart
- [ ] **[AGENT]** Create `helm/mcp-server/templates/ingress.yaml`: Ingress resource with TLS configuration, cert-manager annotations, and routing rules to the MCP Service
- [ ] **[AGENT]** Update `helm/mcp-server/values.yaml`: add ingress configuration (host, tls, annotations)
- [ ] **[BOTH]** Lint and template-render the updated chart: `helm template mcp-server helm/mcp-server/`
- [ ] **[HUMAN]** Upgrade the Helm release: `helm upgrade mcp-server helm/mcp-server/ -n mcp-prototype`

### 10f: Verify HTTPS End-to-End
- [ ] **[HUMAN]** Verify cert-manager issued a certificate: `kubectl get certificate -n mcp-prototype`
- [ ] **[HUMAN]** Test HTTPS health endpoint: `curl https://mcp.yourdomain.com/health`
- [ ] **[HUMAN]** Test HTTPS MCP endpoint with a token:
  ```bash
  curl -X POST https://mcp.yourdomain.com/mcp \
    -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize",...}'
  ```
- [ ] **[HUMAN]** Connect Claude Code via HTTPS:
  ```bash
  claude mcp add --transport http mcp-auth-prototype https://mcp.yourdomain.com/mcp \
    --header "Authorization: Bearer <token>"
  ```
- [ ] **[HUMAN]** Verify HTTP-to-HTTPS redirect works (optional: configure in Ingress annotations)

**Verify before moving on:** HTTPS endpoint is reachable from the internet, TLS certificate is valid (browser shows padlock / curl doesn't complain), Claude Code can connect via HTTPS and use tools, HTTP requests are redirected to HTTPS.

**Key learning:**
- **TLS termination**: Why terminate at the Ingress (not in the app): simplifies app code, centralizes cert management, standard enterprise pattern
- **cert-manager**: Automates certificate lifecycle (issuance, renewal, revocation) via Let's Encrypt ACME protocol
- **Ingress resource**: Layer 7 (HTTP-aware) routing in Kubernetes — host-based and path-based routing, TLS config
- **nginx-ingress controller**: The most widely used Ingress implementation, translates Ingress resources into nginx config
- **Static IP**: Why reserve one (DNS records need a stable IP; ephemeral LoadBalancer IPs change on recreation)
- **Defense in depth**: TLS protects tokens in transit, JWT auth protects at the application layer — both are needed

---

## Phase 11: OAuth2 Token Issuance Service

**Goal:** Replace manual JWT generation with a proper OAuth2-based token issuance flow. Developers authenticate with their identity (e.g., Google account), and the system issues scoped JWT tokens for MCP access. This is how production MCP servers manage developer access at scale.

> **This is a key learning phase.** In our prototype so far, we generate JWTs manually with `scripts/generate_token.py` and hardcode them into the Claude Code config. This doesn't scale: there's no identity verification, no central revocation, no audit trail of who requested what scopes. OAuth2 solves all of this by separating **identity** (who you are) from **authorization** (what you can access).

### Architecture

```
Developer                    Token Service                 MCP Server
    │                             │                             │
    │  1. OAuth2 login            │                             │
    │  (browser → Google IdP)     │                             │
    │────────────────────────────>│                             │
    │                             │                             │
    │  2. ID token returned       │                             │
    │<────────────────────────────│                             │
    │                             │                             │
    │  3. Exchange ID token       │                             │
    │     for scoped MCP JWT      │                             │
    │────────────────────────────>│                             │
    │                             │  (verify identity,          │
    │                             │   look up scopes,           │
    │                             │   mint JWT)                 │
    │  4. Scoped MCP JWT          │                             │
    │<────────────────────────────│                             │
    │                             │                             │
    │  5. Use JWT with Claude Code                              │
    │  Authorization: Bearer <jwt>                              │
    │──────────────────────────────────────────────────────────>│
    │                             │                             │
    │  6. Authorized tool response                              │
    │<──────────────────────────────────────────────────────────│
```

### 11a: Identity Provider Setup
- [ ] **[HUMAN]** Set up Google Identity Platform (or Cloud Identity) as the OAuth2 identity provider in GCP
- [ ] **[HUMAN]** Create an OAuth2 client ID (type: Web application) with appropriate redirect URIs
- [ ] **[HUMAN]** Configure the OAuth2 consent screen (app name, authorized domains, scopes)

### 11b: Token Issuance Service
- [ ] **[AGENT]** Create `token-service/` directory with its own `pyproject.toml`
- [ ] **[AGENT]** Create `token-service/src/main.py`: FastAPI service with two endpoints:
  - `GET /auth/login` — redirects to Google OAuth2 consent screen
  - `GET /auth/callback` — handles OAuth2 callback, verifies ID token, looks up user's allowed MCP scopes (from a config file or database), mints a scoped JWT signed with the same key as the MCP server, returns it to the developer
- [ ] **[AGENT]** Create `token-service/src/config.py`: configuration (OAuth2 client ID/secret, JWT signing key, allowed scopes per user/group)
- [ ] **[AGENT]** Create `token-service/src/scope_mapping.py`: maps Google identity (email/group) to MCP scopes (e.g., `@company.com` engineers get `public:read`, security team gets both scopes)
- [ ] **[AGENT]** Create `token-service/Dockerfile`: containerize the token service
- [ ] **[BOTH]** Test locally: start the token service, complete the OAuth2 flow in a browser, receive a JWT

### 11c: Developer CLI Tool
- [ ] **[AGENT]** Create `scripts/mcp_token_cli.py`: CLI tool that automates the token flow for developers:
  - `mcp-token-cli login` — opens browser for OAuth2 flow, receives JWT, prints it
  - `mcp-token-cli configure` — gets a token and automatically configures Claude Code's MCP settings (updates `~/.config/claude/mcp.json`)
  - `mcp-token-cli status` — shows current token expiry and scopes
- [ ] **[BOTH]** Test the CLI end-to-end: login, get token, verify it works against the MCP server

### 11d: Deploy Token Service to GKE
- [ ] **[AGENT]** Create Helm chart for the token service (or add to existing chart as a sub-chart)
- [ ] **[AGENT]** Add Ingress rule for the token service (e.g., `https://auth.yourdomain.com`)
- [ ] **[HUMAN]** Deploy: `helm upgrade` to add the token service alongside the MCP server
- [ ] **[HUMAN]** Verify the OAuth2 flow works via the deployed HTTPS endpoint

### 11e: Claude Code Integration and E2E Test
- [ ] **[HUMAN]** Full developer workflow test:
  1. Run `mcp-token-cli login` → authenticate with Google → receive JWT
  2. Run `mcp-token-cli configure` → auto-configure Claude Code
  3. Open Claude Code → verify MCP tools are available and work
  4. Wait for token expiry → verify Claude Code gets auth errors
  5. Run `mcp-token-cli login` again → re-configure → verify tools work again
- [ ] **[AGENT]** Update `README.md` with the production token management workflow
- [ ] **[AGENT]** Document the security model: identity verification, scope assignment, token lifecycle, audit trail

**Verify before moving on:** Developer can authenticate with their Google identity, receive a scoped JWT, and use it seamlessly with Claude Code. Token expiry and re-issuance flow works smoothly. Audit logs show who requested tokens and with what scopes.

**Key learning:**
- **OAuth2 authorization code flow**: The standard for web-based authentication — redirect, consent, callback, token exchange
- **ID tokens vs access tokens**: ID tokens prove identity (who you are), access tokens grant access (what you can do) — our token service bridges the two
- **Token exchange pattern**: Converting an external identity (Google ID token) into an internal authorization token (scoped MCP JWT)
- **Scope mapping**: How organizations map identities (users, groups, roles) to fine-grained permissions
- **Developer experience**: Why CLI tooling matters — reducing friction means developers actually use the secure path instead of sharing long-lived tokens
- **MCP + OAuth2**: How the MCP ecosystem is evolving toward native OAuth2 support (RFC 9728), and how our pattern aligns with that future

---

## Phase 12: Load Balancing, Autoscaling, and Production Resilience

**Goal:** Make the MCP server handle real-world traffic patterns by adding Horizontal Pod Autoscaling (HPA), GKE Cluster Autoscaler, Pod Disruption Budgets (PDB), and load testing. This is the difference between a "works in a demo" deployment and one that survives production traffic spikes.

> **This is a key learning phase.** So far our cluster has a fixed number of nodes (3) and a fixed number of MCP server replicas (2). In production, traffic is unpredictable — a team of 50 developers might all start Claude Code sessions in the morning, or an AI agent orchestrator might fan out hundreds of concurrent MCP calls. Autoscaling lets Kubernetes react automatically: spinning up more pods when load increases, and more nodes when the cluster runs out of capacity to schedule those pods.

### How Autoscaling Works (Two Layers)

```
                          Traffic increases
                                │
                                ▼
                ┌───────────────────────────────┐
                │  Horizontal Pod Autoscaler    │
                │  (HPA)                        │
                │                               │
                │  Watches: CPU/memory/custom   │
                │  Action: adds more Pod        │
                │  replicas (e.g., 2 → 8)       │
                └───────────────┬───────────────┘
                                │
                    Pods need nodes to run on
                                │
                                ▼
                ┌───────────────────────────────┐
                │  Cluster Autoscaler           │
                │  (GKE node auto-provisioning) │
                │                               │
                │  Watches: unschedulable pods  │
                │  Action: adds more nodes      │
                │  (e.g., 3 → 6 nodes)          │
                └───────────────────────────────┘
                                │
                                ▼
                ┌───────────────────────────────┐
                │  Load Balancer (Ingress)      │
                │                               │
                │  Distributes traffic across   │
                │  all healthy pods equally     │
                └───────────────────────────────┘
```

**Key insight:** HPA scales *pods* (your application), Cluster Autoscaler scales *nodes* (the infrastructure). They work together: HPA says "I need 8 replicas", Cluster Autoscaler says "I need more nodes to fit 8 replicas".

### 12a: Horizontal Pod Autoscaler (HPA)
- [ ] **[HUMAN]** Install the Metrics Server in the cluster (provides CPU/memory metrics that HPA reads):
  ```bash
  kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
  ```
- [ ] **[HUMAN]** Verify metrics are available: `kubectl top nodes` and `kubectl top pods -n mcp-prototype`
- [ ] **[AGENT]** Create `helm/mcp-server/templates/hpa.yaml`: HorizontalPodAutoscaler resource that:
  - Scales between 2 (min) and 10 (max) replicas
  - Targets 70% average CPU utilization
  - Targets 80% average memory utilization
  - Uses sensible scale-up/scale-down behavior (scale up fast, scale down slowly to avoid flapping)
- [ ] **[AGENT]** Update `helm/mcp-server/values.yaml`: add autoscaling configuration block (enabled, min/max replicas, target CPU/memory percentages)
- [ ] **[BOTH]** Deploy and verify: `kubectl get hpa -n mcp-prototype` shows the HPA with current metrics

### 12b: Pod Disruption Budget (PDB)
- [ ] **[AGENT]** Create `helm/mcp-server/templates/pdb.yaml`: PodDisruptionBudget that guarantees at least 1 pod is always available during voluntary disruptions (node upgrades, cluster scaling down, `kubectl drain`)
- [ ] **[AGENT]** Update `helm/mcp-server/values.yaml`: add PDB configuration (minAvailable or maxUnavailable)
- [ ] **[BOTH]** Deploy and verify: `kubectl get pdb -n mcp-prototype`

### 12c: GKE Cluster Autoscaler
- [ ] **[AGENT]** Update `terraform/gke.tf`: enable Cluster Autoscaler on the node pool with:
  - Minimum nodes: 2 (always keep at least 2 for availability)
  - Maximum nodes: 6 (cost ceiling for the prototype)
  - Auto-provisioning profile (resource limits, machine types)
- [ ] **[HUMAN]** Run `terraform apply` to update the cluster configuration
- [ ] **[HUMAN]** Verify autoscaler is active: `gcloud container clusters describe mcp-prototype --zone europe-west1-b | grep -A5 autoscaling`

### 12d: Load Balancer Deep Dive
- [ ] **[HUMAN]** Understand the load balancing layers by inspecting the current setup:
  - **L4 (TCP)**: The GCP Network Load Balancer in front of the nginx-ingress controller — distributes TCP connections across ingress controller pods
  - **L7 (HTTP)**: nginx-ingress internally — routes HTTP requests to MCP server pods, respects readiness probes (unhealthy pods get no traffic)
  - **kube-proxy**: The Kubernetes networking layer — implements Service load balancing via iptables/IPVS rules
- [ ] **[HUMAN]** Inspect the load balancer: `kubectl get svc -n ingress-nginx` (note the EXTERNAL-IP and port mappings)
- [ ] **[HUMAN]** Verify traffic distribution: make multiple requests and check which pod handles each (visible in structured JSON logs via `kubectl logs`)
- [ ] **[AGENT]** Add session affinity configuration to `helm/mcp-server/values.yaml` (optional: explain when sticky sessions matter vs stateless round-robin)

### 12e: Load Testing
- [ ] **[AGENT]** Create `load-test/locustfile.py`: load test script using [Locust](https://locust.io) that:
  - Simulates multiple concurrent MCP clients
  - Sends `initialize`, `tools/list`, and `tools/call` requests with valid JWTs
  - Ramps up from 10 to 100 concurrent users over 5 minutes
  - Reports response times, error rates, and throughput
- [ ] **[AGENT]** Create `load-test/README.md`: instructions for running the load test
- [ ] **[HUMAN]** Run the load test against the deployed MCP server:
  ```bash
  pip install locust
  locust -f load-test/locustfile.py --host https://mcp.yourdomain.com
  ```
- [ ] **[HUMAN]** Observe autoscaling in real-time during the load test:
  - Watch pod count increase: `kubectl get pods -n mcp-prototype -w`
  - Watch HPA react: `kubectl get hpa -n mcp-prototype -w`
  - Watch node count increase (if load is high enough): `kubectl get nodes -w`
- [ ] **[HUMAN]** After the load test ends, observe scale-down:
  - HPA gradually reduces pod count (cooldown period)
  - Cluster Autoscaler removes underutilized nodes (10-minute default delay)

### 12f: Resource Tuning
- [ ] **[HUMAN]** Analyze load test results to tune resource requests/limits:
  - Check actual CPU/memory usage: `kubectl top pods -n mcp-prototype`
  - Compare against current requests/limits in `values.yaml`
  - Adjust if pods are being OOM-killed (limits too low) or wasting resources (requests too high)
- [ ] **[AGENT]** Update `helm/mcp-server/values.yaml` with tuned resource values based on load test observations
- [ ] **[BOTH]** Re-run load test to verify improved behavior

**Verify before moving on:** HPA scales pods up under load and back down when load drops. Cluster Autoscaler adds nodes when pods can't be scheduled and removes them when underutilized. PDB prevents total outage during node drains. Load test shows stable response times under expected traffic levels. All of this is observable in real-time.

**Key learning:**
- **HPA (Horizontal Pod Autoscaler)**: Scales pods based on metrics — the primary mechanism for handling traffic spikes. Understand the difference between scaling on CPU vs memory vs custom metrics, and why scale-down is intentionally slow (to prevent flapping)
- **Cluster Autoscaler**: Scales the underlying infrastructure (nodes). Triggered when pods are "Pending" because no node has enough resources. Understand the delay (pods wait while nodes boot) and why min/max limits matter (cost control)
- **Pod Disruption Budget**: Guarantees availability during voluntary disruptions. Without a PDB, a `kubectl drain` or cluster upgrade could terminate all pods simultaneously. This is a production must-have
- **Load balancing layers**: L4 (TCP — GCP LB), L7 (HTTP — nginx-ingress), kube-proxy (Service). Understanding which layer does what helps debug connectivity and distribution issues
- **Resource requests vs limits**: Requests = "what I need to be scheduled" (affects which node the pod lands on). Limits = "the maximum I'm allowed to use" (pod gets killed if it exceeds memory limit). Getting these right is critical for autoscaling to work properly
- **Load testing**: The only way to validate autoscaling config. Without simulating real traffic, you're guessing. Locust is a popular Python-based load testing tool
- **Cost awareness**: Autoscaling creates resources that cost money. Max limits on HPA and Cluster Autoscaler are your cost ceiling. In production, pair with budget alerts

---

## Summary

| Phase | Description | Primary Actor | Key Learning Areas |
|-------|-------------|---------------|-------------------|
| 0 | Project scaffolding | Agent | uv, pyproject.toml, lockfiles |
| 1 | MCP server (no auth) | Agent | MCP protocol, Streamable HTTP, tools |
| 2 | Auth + authorization | Agent | JWT, middleware, scopes, defense in depth |
| 3 | Tests | Agent | Testing auth, shift-left security |
| 4 | Docker | Agent writes, Human builds | Multi-stage builds, 12-factor config |
| 5 | GCP + Terraform + GKE | Agent writes, **Human applies** | **Terraform IaC, GKE, Workload Identity, ESO** |
| 6 | Helm chart | Agent writes, **Human deploys** | **Helm templating, K8s resources, probes** |
| 7 | GitHub Actions CI | Agent writes, **Human configures** | **CI/CD, Workload Identity Federation** |
| 8 | ArgoCD | Agent writes, **Human installs** | **GitOps, auto-sync, rolling updates** |
| 9 | E2E verification | Both | Full pipeline validation |
| 10 | TLS Ingress (HTTPS) | Agent writes, **Human deploys** | **Ingress, cert-manager, TLS termination, static IP** |
| 11 | OAuth2 Token Service | Agent writes, **Human configures** | **OAuth2, token exchange, CLI tooling, DX** |
| 12 | Autoscaling & Resilience | Agent writes, **Human applies** | **HPA, Cluster Autoscaler, PDB, load testing, LB** |
