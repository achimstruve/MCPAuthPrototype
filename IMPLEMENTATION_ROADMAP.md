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
- [ ] **[HUMAN]** Get cluster credentials: `gcloud container clusters get-credentials mcp-prototype --zone europe-west1-b`
- [ ] **[HUMAN]** Verify: `kubectl get nodes` shows 3 nodes in Ready state

### 5e: External Secrets Operator (Helm)
- [ ] **[HUMAN]** Add ESO Helm repo and install ESO into the cluster
- [ ] **[HUMAN]** Verify ESO pods are running: `kubectl get pods -n external-secrets`

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

- [ ] **[AGENT]** Create `helm/mcp-server/Chart.yaml`: chart metadata (apiVersion v2, name, version, appVersion)
- [ ] **[AGENT]** Create `helm/mcp-server/values.yaml`: default values (replicaCount: 2, image, service port 8080, resource requests/limits, probe config, externalSecret config)
- [ ] **[AGENT]** Create `helm/mcp-server/values-dev.yaml`: dev environment overrides
- [ ] **[AGENT]** Create `helm/mcp-server/templates/_helpers.tpl`: common template helpers (labels, names)
- [ ] **[AGENT]** Create `helm/mcp-server/templates/deployment.yaml`: Deployment with 2 replicas, container config, probes, env vars from Secret, resource limits
- [ ] **[AGENT]** Create `helm/mcp-server/templates/service.yaml`: ClusterIP Service on port 8080
- [ ] **[AGENT]** Create `helm/mcp-server/templates/configmap.yaml`: document content mounted into pods
- [ ] **[AGENT]** Create `helm/mcp-server/templates/serviceaccount.yaml`: dedicated ServiceAccount with Workload Identity annotation
- [ ] **[AGENT]** Create `helm/mcp-server/templates/externalsecret.yaml`: ExternalSecret resource to sync JWT key from GCP Secret Manager
- [ ] **[AGENT]** Create `helm/mcp-server/templates/secretstore.yaml`: SecretStore connecting ESO to GCP Secret Manager
- [ ] **[BOTH]** Lint chart: `helm lint helm/mcp-server/`
- [ ] **[BOTH]** Render templates locally: `helm template mcp-server helm/mcp-server/` and review output
- [ ] **[HUMAN]** Create namespace: `kubectl create namespace mcp-prototype`
- [ ] **[HUMAN]** Install chart: `helm install mcp-server helm/mcp-server/ -n mcp-prototype`
- [ ] **[HUMAN]** Verify pods are running across nodes: `kubectl get pods -n mcp-prototype -o wide`
- [ ] **[HUMAN]** Verify service exists: `kubectl get svc -n mcp-prototype`
- [ ] **[HUMAN]** Check logs: `kubectl logs -n mcp-prototype -l app.kubernetes.io/name=mcp-server`
- [ ] **[HUMAN]** Port-forward and test: `kubectl port-forward svc/mcp-server -n mcp-prototype 8080:8080`

**Verify before moving on:** 2 pods running on different nodes, service routing traffic, health probes passing, JWT secret injected from Secret Manager.

**Key learning:** Helm templating (Go templates, values, helpers), Deployment vs Pod, ClusterIP Service, ConfigMap vs Secret, resource requests vs limits, liveness vs readiness probes, ExternalSecret/SecretStore pattern, `helm template` for debugging.

---

## Phase 7: GitHub Actions CI Pipeline

**Goal:** Automated pipeline that lints, tests, builds the Docker image, pushes to Artifact Registry, and updates the Helm chart image tag.

> **This is a key learning phase.** The agent writes the workflow file. The human configures GitHub secrets and Workload Identity Federation manually.

- [ ] **[AGENT]** Create `.github/workflows/ci.yaml`: complete CI pipeline (checkout, setup uv, lint, test, authenticate to GCP via Workload Identity Federation, build Docker image with git SHA tag, push to Artifact Registry, update values.yaml image tag, commit and push)
- [ ] **[HUMAN]** Set up Workload Identity Federation in GCP for GitHub Actions (create workload identity pool, provider, and IAM bindings)
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
