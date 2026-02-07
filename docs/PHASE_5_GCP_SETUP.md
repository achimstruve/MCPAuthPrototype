# Phase 5: GCP and GKE Cluster Setup

This guide walks you through setting up all the GCP infrastructure needed to run the MCP server in Kubernetes. **You will execute these commands manually** to build hands-on experience with each component.

**What we're building:**

```
┌─────────────────────────────────────────────────────────────────┐
│                        GCP Project                               │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Artifact        │  │ Secret Manager   │  │ GKE Cluster     │  │
│  │ Registry        │  │                  │  │ (3 nodes)       │  │
│  │                 │  │ mcp-jwt-signing  │  │                 │  │
│  │ Docker images   │  │ -key             │  │ External Secrets│  │
│  │ stored here     │  │                  │  │ Operator        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

Before starting, ensure you have:

1. **gcloud CLI installed and authenticated**
   ```bash
   gcloud version  # Should show version info
   gcloud auth list  # Should show your account
   ```

2. **kubectl installed**
   ```bash
   kubectl version --client  # Should show client version
   ```

3. **Helm installed**
   ```bash
   helm version  # Should show version 3.x
   ```

4. **A GCP project with billing enabled**
   - You'll need the Project ID (not Project Name)
   - Check your current project: `gcloud config get-value project`

---

## Phase 5a: GCP Project and APIs

### Step 1: Set Your Active Project

First, we need to tell gcloud which project to work with. Replace `<your-project-id>` with your actual project ID.

```bash
# Set the active project for all subsequent gcloud commands
gcloud config set project <your-project-id>
```

**What this does:**
- Configures gcloud to use this project by default
- All resources we create will belong to this project
- You can check the current project anytime with: `gcloud config get-value project`

**Expected output:**
```
Updated property [core/project].
```

### Step 2: Enable Required APIs

GCP requires you to explicitly enable APIs before using services. This is a security feature - you only enable what you need.

```bash
# Enable all required APIs in one command
gcloud services enable \
    container.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com
```

**What each API does:**
| API | Purpose |
|-----|---------|
| `container.googleapis.com` | Google Kubernetes Engine (GKE) - runs our containers |
| `artifactregistry.googleapis.com` | Artifact Registry - stores our Docker images |
| `secretmanager.googleapis.com` | Secret Manager - stores the JWT signing key securely |

**Expected output:**
```
Operation "operations/..." finished successfully.
```

**This may take 30-60 seconds.** If you see an error about billing not enabled, you need to enable billing on your project first.

### Verify APIs are enabled

```bash
gcloud services list --enabled --filter="name:(container OR artifactregistry OR secretmanager)"
```

**Expected output:** Should show all three services listed.

---

## Phase 5b: Artifact Registry

Artifact Registry is GCP's container registry - it stores Docker images that Kubernetes pulls when deploying pods.

### Why Artifact Registry instead of Docker Hub?

1. **Same network**: Images pull faster from GCP to GKE (same data center)
2. **IAM integration**: Use GCP permissions instead of Docker Hub credentials
3. **Regional storage**: Keep images close to your cluster
4. **Security scanning**: Built-in vulnerability scanning

### Step 1: Create the Docker Repository

```bash
# Create a Docker repository in Artifact Registry
gcloud artifacts repositories create mcp-server \
    --repository-format=docker \
    --location=europe-west1 \
    --description="MCP Auth Prototype container images"
```

**Flag explanations:**
| Flag | Value | Purpose |
|------|-------|---------|
| `--repository-format` | `docker` | We're storing Docker/OCI images (not Maven, npm, etc.) |
| `--location` | `europe-west1` | Region where images are stored (same region as our cluster) |
| `--description` | ... | Human-readable description |

**Expected output:**
```
Create request issued for: [mcp-server]
...
Created repository [mcp-server].
```

### Step 2: Configure Docker Authentication

Docker needs credentials to push images to Artifact Registry. This command sets up gcloud as a credential helper.

```bash
# Configure Docker to use gcloud for authentication
gcloud auth configure-docker europe-west1-docker.pkg.dev
```

**What this does:**
- Modifies `~/.docker/config.json` to use gcloud for `europe-west1-docker.pkg.dev`
- When Docker pushes to this registry, it asks gcloud for credentials
- No username/password needed - uses your gcloud login

**Expected output:**
```
Adding credentials for: europe-west1-docker.pkg.dev
Docker configuration file updated.
```

### Step 3: Tag and Push Your Image

Now we push the Docker image you built in Phase 4 to Artifact Registry.

```bash
# Get your project ID (we'll use this in the tag)
PROJECT_ID=$(gcloud config get-value project)
echo "Project ID: $PROJECT_ID"

# Tag the local image with the Artifact Registry path
docker tag mcp-auth-prototype:local \
    europe-west1-docker.pkg.dev/${PROJECT_ID}/mcp-server/mcp-auth-prototype:v1

# Push the image to Artifact Registry
docker push europe-west1-docker.pkg.dev/${PROJECT_ID}/mcp-server/mcp-auth-prototype:v1
```

**Understanding the image path:**
```
europe-west1-docker.pkg.dev / ${PROJECT_ID} / mcp-server / mcp-auth-prototype:v1
      │                            │               │                 │
      │                            │               │                 └── Image name:tag
      │                            │               └── Repository name (we created this)
      │                            └── GCP Project ID
      └── Artifact Registry hostname for this region
```

**Expected output:**
```
The push refers to repository [europe-west1-docker.pkg.dev/.../mcp-auth-prototype]
...
v1: digest: sha256:... size: ...
```

### Step 4: Verify the Image

```bash
# List images in the repository
gcloud artifacts docker images list \
    europe-west1-docker.pkg.dev/${PROJECT_ID}/mcp-server
```

**Expected output:** Should show your `mcp-auth-prototype` image with tag `v1`.

---

## Phase 5c: Secret Manager

GCP Secret Manager is a secure vault for sensitive data like API keys, passwords, and cryptographic keys. We'll store the JWT signing key here.

### Why Secret Manager instead of Kubernetes Secrets directly?

1. **Centralized**: Secrets in one place, accessible by multiple clusters
2. **Versioning**: Secret Manager keeps history of all versions
3. **Audit logging**: Every access is logged in Cloud Audit Logs
4. **IAM**: Fine-grained access control with GCP IAM
5. **Encryption**: Encrypted at rest with Google-managed or customer-managed keys

### Step 1: Generate a Strong JWT Signing Key

A JWT signing key should be a long, random string. We'll generate one using OpenSSL.

```bash
# Generate a 64-character random hex string
JWT_SECRET=$(openssl rand -hex 32)
echo "Generated JWT secret (keep this safe!):"
echo $JWT_SECRET
```

**What this does:**
- `openssl rand -hex 32` generates 32 random bytes, output as 64 hex characters
- This produces a 256-bit key, suitable for HS256 (HMAC-SHA256)
- **IMPORTANT:** Save this value somewhere secure - you'll need it to generate tokens

### Step 2: Store the Secret in Secret Manager

```bash
# Create the secret in Secret Manager
echo -n "$JWT_SECRET" | gcloud secrets create mcp-jwt-signing-key \
    --data-file=- \
    --replication-policy="user-managed" \
    --locations="europe-west1"
```

**Flag explanations:**
| Flag | Value | Purpose |
|------|-------|---------|
| `--data-file=-` | `-` | Read secret value from stdin (piped from echo) |
| `--replication-policy` | `user-managed` | We choose where replicas are stored |
| `--locations` | `europe-west1` | Store in same region as our cluster (lower latency) |

**Why `echo -n`?** The `-n` flag prevents adding a newline character at the end, which would become part of the secret and cause JWT validation to fail.

**Expected output:**
```
Created secret [mcp-jwt-signing-key].
```

### Step 3: Verify the Secret

```bash
# Read back the secret to verify it was stored correctly
gcloud secrets versions access latest --secret=mcp-jwt-signing-key
```

**Expected output:** Should print the same hex string you generated.

**Security note:** In production, you'd avoid printing secrets to the terminal. This is just for learning/verification.

---

## Phase 5d: GKE Cluster

Now we create the Kubernetes cluster that will run our MCP server.

### Cluster Architecture Recap

From the PRD:
- **3 nodes** (e2-small): Provides realistic multi-node scheduling
- **2 MCP server replicas**: Demonstrates multi-replica orchestration
- **Single zone**: Keeps costs low for a prototype
- **Workload Identity**: Secure access to GCP services without key files

### Step 1: Create the GKE Cluster

This command creates the cluster with all our specifications:

```bash
PROJECT_ID=$(gcloud config get-value project)

gcloud container clusters create mcp-prototype \
    --zone=europe-west1-b \
    --num-nodes=3 \
    --machine-type=e2-small \
    --disk-size=30 \
    --release-channel=regular \
    --workload-pool=${PROJECT_ID}.svc.id.goog
```

**Flag explanations:**

| Flag | Value | Purpose |
|------|-------|---------|
| `--zone` | `europe-west1-b` | Single zone deployment (cheaper than regional) |
| `--num-nodes` | `3` | Three nodes for realistic scheduling |
| `--machine-type` | `e2-small` | 2 vCPU, 2GB RAM per node (smallest viable) |
| `--disk-size` | `30` | 30GB per node for images and system data |
| `--release-channel` | `regular` | Stable Kubernetes version, auto-updated |
| `--workload-pool` | `${PROJECT_ID}.svc.id.goog` | Enables Workload Identity |

**What is Workload Identity?**
Workload Identity lets Kubernetes pods authenticate to GCP services using a Kubernetes ServiceAccount, without storing JSON key files. The pods get temporary credentials automatically, managed by GCP.

**This takes 5-10 minutes.** You'll see progress updates as it creates:
1. The control plane (managed by Google)
2. The three worker nodes
3. Networking components

**Expected output:**
```
Creating cluster mcp-prototype...
...
Created [https://container.googleapis.com/...].
...
kubeconfig entry generated for mcp-prototype.
```

### Step 2: Get Cluster Credentials

This configures `kubectl` to talk to your new cluster:

```bash
gcloud container clusters get-credentials mcp-prototype --zone=europe-west1-b
```

**What this does:**
- Adds an entry to `~/.kube/config` with cluster connection info
- Sets this cluster as the current context for kubectl
- Uses gcloud to provide authentication tokens automatically

**Expected output:**
```
Fetching cluster endpoint and auth data.
kubeconfig entry generated for mcp-prototype.
```

### Step 3: Verify the Cluster

```bash
# Check that we're connected to the right cluster
kubectl config current-context

# List all nodes - should show 3 in Ready state
kubectl get nodes

# See more details about each node
kubectl get nodes -o wide
```

**Expected output:**
```
NAME                                          STATUS   ROLES    AGE   VERSION
gke-mcp-prototype-default-pool-xxxxx-xxxx     Ready    <none>   2m    v1.xx.x-gke.xxx
gke-mcp-prototype-default-pool-xxxxx-xxxx     Ready    <none>   2m    v1.xx.x-gke.xxx
gke-mcp-prototype-default-pool-xxxxx-xxxx     Ready    <none>   2m    v1.xx.x-gke.xxx
```

**What to look for:**
- All 3 nodes should show `STATUS: Ready`
- `ROLES: <none>` is normal for GKE worker nodes (control plane is managed)
- `VERSION` should be a recent Kubernetes version

---

## Phase 5e: External Secrets Operator

External Secrets Operator (ESO) syncs secrets from external vaults (like GCP Secret Manager) into Kubernetes Secrets. This keeps secrets out of your Git repository and Helm values files.

### How ESO Works

```
GCP Secret Manager                    Kubernetes Cluster
┌────────────────────┐               ┌─────────────────────────────┐
│ mcp-jwt-signing-key│               │                             │
│ (secret value)     │◄──────────────│  ExternalSecret Resource    │
└────────────────────┘   ESO polls   │  "Sync secret X from GCP"   │
                         every 1h    │                             │
                                     │          ▼                  │
                                     │  Kubernetes Secret          │
                                     │  (created by ESO)           │
                                     │                             │
                                     │          ▼                  │
                                     │  Pod (mounts secret as env) │
                                     └─────────────────────────────┘
```

### Step 1: Install External Secrets Operator via Helm

```bash
# Add the External Secrets Helm repository
helm repo add external-secrets https://charts.external-secrets.io

# Update repo cache
helm repo update

# Install ESO into its own namespace
helm install external-secrets external-secrets/external-secrets \
    --namespace external-secrets \
    --create-namespace \
    --set installCRDs=true
```

**Flag explanations:**
| Flag | Purpose |
|------|---------|
| `--namespace external-secrets` | Install into dedicated namespace |
| `--create-namespace` | Create the namespace if it doesn't exist |
| `--set installCRDs=true` | Install Custom Resource Definitions (ExternalSecret, SecretStore, etc.) |

**Expected output:**
```
NAME: external-secrets
...
STATUS: deployed
```

### Step 2: Verify ESO Installation

```bash
# Check pods are running
kubectl get pods -n external-secrets

# Check CRDs were installed
kubectl get crds | grep external-secrets
```

**Expected output for pods:**
```
NAME                                               READY   STATUS    RESTARTS   AGE
external-secrets-xxxxxxxxx-xxxxx                   1/1     Running   0          30s
external-secrets-cert-controller-xxxxxxxxx-xxxxx   1/1     Running   0          30s
external-secrets-webhook-xxxxxxxxx-xxxxx           1/1     Running   0          30s
```

**Expected CRDs:**
- `externalsecrets.external-secrets.io`
- `secretstores.external-secrets.io`
- `clustersecretstores.external-secrets.io`

### Step 3: Create GCP Service Account for ESO

ESO needs a GCP service account with permission to read secrets. We'll create this and bind it to a Kubernetes ServiceAccount using Workload Identity.

```bash
PROJECT_ID=$(gcloud config get-value project)

# Create a GCP service account for ESO
gcloud iam service-accounts create eso-secret-accessor \
    --display-name="External Secrets Operator"

# Grant it permission to access secrets
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:eso-secret-accessor@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

**What this does:**
1. Creates a GCP service account named `eso-secret-accessor`
2. Grants it the `secretmanager.secretAccessor` role (read-only access to secrets)

### Step 4: Create Kubernetes ServiceAccount for ESO

Now we create a Kubernetes ServiceAccount that ESO will use, and bind it to the GCP service account:

```bash
PROJECT_ID=$(gcloud config get-value project)

# Create a Kubernetes ServiceAccount in the namespace where we'll deploy
kubectl create namespace mcp-prototype

kubectl create serviceaccount eso-service-account \
    --namespace mcp-prototype

# Annotate it to link with the GCP service account
kubectl annotate serviceaccount eso-service-account \
    --namespace mcp-prototype \
    iam.gke.io/gcp-service-account=eso-secret-accessor@${PROJECT_ID}.iam.gserviceaccount.com
```

### Step 5: Configure Workload Identity Binding

The final step links the Kubernetes ServiceAccount to the GCP ServiceAccount:

```bash
PROJECT_ID=$(gcloud config get-value project)

# Allow the K8s ServiceAccount to impersonate the GCP ServiceAccount
gcloud iam service-accounts add-iam-policy-binding \
    eso-secret-accessor@${PROJECT_ID}.iam.gserviceaccount.com \
    --role="roles/iam.workloadIdentityUser" \
    --member="serviceAccount:${PROJECT_ID}.svc.id.goog[mcp-prototype/eso-service-account]"
```

**Understanding the member format:**
```
serviceAccount:${PROJECT_ID}.svc.id.goog[mcp-prototype/eso-service-account]
               │                        │            │
               │                        │            └── K8s ServiceAccount name
               │                        └── K8s Namespace
               └── Workload Identity pool (project.svc.id.goog)
```

**What Workload Identity does:**
1. Pod starts with K8s ServiceAccount `eso-service-account`
2. When it needs GCP credentials, it contacts the GKE metadata server
3. GKE sees the binding and issues a temporary GCP token for `eso-secret-accessor`
4. Pod uses this token to access Secret Manager
5. Token expires automatically - no long-lived keys stored anywhere

### Verify Workload Identity Setup

```bash
# Verify the annotation exists
kubectl get serviceaccount eso-service-account \
    -n mcp-prototype \
    -o jsonpath='{.metadata.annotations}'
```

**Expected output:** Should show the `iam.gke.io/gcp-service-account` annotation.

---

## Phase 5 Verification Checklist

Before moving to Phase 6, verify all of the following:

```bash
# 1. Check cluster nodes (3 nodes in Ready state)
kubectl get nodes

# 2. Check ESO is running
kubectl get pods -n external-secrets

# 3. Verify image is in Artifact Registry
PROJECT_ID=$(gcloud config get-value project)
gcloud artifacts docker images list \
    europe-west1-docker.pkg.dev/${PROJECT_ID}/mcp-server

# 4. Verify secret exists
gcloud secrets describe mcp-jwt-signing-key

# 5. Verify namespace exists
kubectl get namespace mcp-prototype

# 6. Verify ServiceAccount exists with annotation
kubectl get serviceaccount eso-service-account -n mcp-prototype -o yaml
```

**All checks passed?** You're ready for Phase 6: Helm Chart!

---

## Cost Reminder

**Your cluster is now running and incurring costs!**

The 3x e2-small nodes cost approximately $35-45/month. When you're done working for the day, you can:

1. **Delete the cluster** (removes everything, you'll recreate for next session):
   ```bash
   gcloud container clusters delete mcp-prototype --zone=europe-west1-b
   ```

2. **Resize to 0 nodes** (keeps cluster config, stops compute costs):
   ```bash
   gcloud container clusters resize mcp-prototype --num-nodes=0 --zone=europe-west1-b
   # To restore later:
   gcloud container clusters resize mcp-prototype --num-nodes=3 --zone=europe-west1-b
   ```

---

## Key Concepts Learned

| Concept | What You Learned |
|---------|------------------|
| **GCP APIs** | Services must be explicitly enabled; security feature |
| **Artifact Registry** | Container registry integrated with GCP IAM |
| **Secret Manager** | Secure vault for sensitive data with versioning and audit logging |
| **GKE Standard** | Full control over nodes (vs Autopilot which abstracts nodes away) |
| **Workload Identity** | Keyless authentication from K8s pods to GCP services |
| **External Secrets Operator** | Syncs secrets from external vaults to K8s Secrets |
| **ServiceAccount binding** | Links K8s and GCP identities for secure access |

These patterns are used in production environments to:
- Keep secrets out of code and Git
- Provide audit trails for secret access
- Enable Zero Trust security (pods only get credentials they need)
- Simplify credential rotation (update in Secret Manager, ESO syncs automatically)
