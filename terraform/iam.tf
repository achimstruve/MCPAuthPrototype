# =============================================================================
# iam.tf - Service Accounts and IAM Bindings
# =============================================================================
#
# This file sets up the identity and permissions infrastructure for
# Workload Identity - the secure way to give Kubernetes pods access to
# GCP services.
#
# THE WORKLOAD IDENTITY FLOW:
#
#   Kubernetes Pod
#        │
#        │ uses K8s ServiceAccount
#        ▼
#   K8s ServiceAccount (in cluster)
#        │
#        │ annotated with GCP SA email
#        ▼
#   IAM Policy Binding (connects K8s SA → GCP SA)
#        │
#        │ grants workloadIdentityUser role
#        ▼
#   GCP Service Account
#        │
#        │ has secretmanager.secretAccessor role
#        ▼
#   GCP Secret Manager
#
# Result: Pod can read secrets without any key files or stored credentials!
# =============================================================================

# -----------------------------------------------------------------------------
# GCP Service Account for External Secrets Operator
# -----------------------------------------------------------------------------
# This service account will be "impersonated" by ESO pods via Workload Identity

resource "google_service_account" "eso_secret_accessor" {
  # Account ID must be 6-30 characters, lowercase letters, numbers, hyphens
  account_id   = "eso-secret-accessor"
  display_name = "External Secrets Operator Secret Accessor"
  description  = "Service account for ESO to read secrets from Secret Manager"
}

# -----------------------------------------------------------------------------
# Grant Secret Manager Access to the Service Account
# -----------------------------------------------------------------------------
# This allows the service account to read secret values

resource "google_project_iam_member" "eso_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.eso_secret_accessor.email}"
}

# Explanation of roles:
# - roles/secretmanager.secretAccessor: Read secret values (what we need)
# - roles/secretmanager.viewer: List and view metadata (no values)
# - roles/secretmanager.admin: Full control (too permissive for ESO)
#
# Always use least privilege: only grant what's needed

# -----------------------------------------------------------------------------
# Workload Identity Binding
# -----------------------------------------------------------------------------
# This is the magic that connects Kubernetes to GCP IAM.
#
# Format of the member:
#   serviceAccount:PROJECT_ID.svc.id.goog[NAMESPACE/KSA_NAME]
#
# Where:
# - PROJECT_ID.svc.id.goog: The Workload Identity pool (auto-created with cluster)
# - NAMESPACE: Kubernetes namespace where the ServiceAccount lives
# - KSA_NAME: Name of the Kubernetes ServiceAccount

resource "google_service_account_iam_binding" "eso_workload_identity" {
  service_account_id = google_service_account.eso_secret_accessor.name
  role               = "roles/iam.workloadIdentityUser"

  members = [
    # ESO's service account in the mcp-prototype namespace
    "serviceAccount:${var.project_id}.svc.id.goog[mcp-prototype/eso-service-account]",
  ]

  # Must wait for GKE cluster to create the Workload Identity pool
  depends_on = [google_container_cluster.mcp_prototype]
}

# =============================================================================
# Understanding Workload Identity vs Service Account Keys
# =============================================================================
#
# TRADITIONAL APPROACH (not recommended):
#
#   1. Create GCP service account
#   2. Generate JSON key file: gcloud iam service-accounts keys create key.json
#   3. Create K8s secret from the key file
#   4. Mount secret in pods
#   5. Set GOOGLE_APPLICATION_CREDENTIALS env var
#
#   Problems:
#   - Key file is a long-lived credential (never expires by default)
#   - Must be rotated manually
#   - Can be leaked if secret is exposed
#   - Hard to audit who is using which key
#
# WORKLOAD IDENTITY APPROACH (what we use):
#
#   1. Create GCP service account (this file)
#   2. Create K8s ServiceAccount with annotation (Helm chart)
#   3. Create IAM binding (this file)
#   4. Pod automatically gets temporary GCP credentials
#
#   Benefits:
#   - No key files to manage or rotate
#   - Credentials are temporary (expire automatically)
#   - Auditable: Cloud Audit Logs show which pod accessed what
#   - Defense in depth: compromised pod can't exfiltrate persistent credentials
#
# =============================================================================

# -----------------------------------------------------------------------------
# MCP Server Service Account (for future use)
# -----------------------------------------------------------------------------
# The MCP server itself might need GCP access in the future
# (e.g., for Cloud Logging, Cloud Trace, etc.)

resource "google_service_account" "mcp_server" {
  account_id   = "mcp-server"
  display_name = "MCP Server"
  description  = "Service account for MCP server pods"
}

# Workload Identity binding for MCP server
resource "google_service_account_iam_binding" "mcp_server_workload_identity" {
  service_account_id = google_service_account.mcp_server.name
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[mcp-prototype/mcp-server]",
  ]

  # Must wait for GKE cluster to create the Workload Identity pool
  depends_on = [google_container_cluster.mcp_prototype]
}

# Note: We don't grant any GCP permissions to mcp-server yet because
# the MCP server doesn't need direct GCP access. It gets secrets via ESO,
# which handles the Secret Manager access.
