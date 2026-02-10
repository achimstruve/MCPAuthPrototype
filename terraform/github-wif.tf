# =============================================================================
# github-wif.tf - Workload Identity Federation for GitHub Actions
# =============================================================================
#
# WHAT IS WORKLOAD IDENTITY FEDERATION (WIF)?
#
# WIF allows external identities (like GitHub Actions) to impersonate GCP
# service accounts WITHOUT storing long-lived credentials (JSON key files).
#
# THE PROBLEM WIF SOLVES:
#   Traditional CI/CD → GCP authentication:
#     1. Create a GCP service account
#     2. Generate a JSON key file (long-lived, never expires by default)
#     3. Store the key as a GitHub secret
#     4. CI uses the key to authenticate
#
#   Problems:
#     - The key is a permanent credential — if leaked, attacker has access forever
#     - Key rotation is manual and error-prone
#     - The key exists in two places (GCP + GitHub) — doubles the attack surface
#     - No way to restrict WHICH workflow/branch/repo can use the key
#
# HOW WIF WORKS (the secure alternative):
#
#   ┌──────────────┐     1. "I am repo X,       ┌──────────────────┐
#   │   GitHub      │        branch main,        │  Google Cloud     │
#   │   Actions     │        workflow ci.yaml"    │  Security Token   │
#   │   Runner      │ ─────────────────────────▶  │  Service (STS)    │
#   │               │     (OIDC JWT token)        │                   │
#   │               │                             │  2. Verifies token│
#   │               │     3. Short-lived          │     against GitHub│
#   │               │  ◀───────────────────────── │     OIDC issuer   │
#   │               │     GCP access token        │                   │
#   └──────────────┘     (expires in ~1 hour)     └──────────────────┘
#
#   Step 1: GitHub Actions generates an OIDC token (built-in, automatic)
#   Step 2: Google verifies the token came from GitHub (checks the OIDC issuer)
#   Step 3: Google checks the attribute_condition (is this the right repo?)
#   Step 4: If valid, Google issues a short-lived access token
#   Step 5: CI uses the access token to push images, etc.
#
# COMPONENTS WE CREATE:
#   1. Workload Identity Pool    → A container for external identity providers
#   2. OIDC Provider             → Configures GitHub as a trusted identity source
#   3. Service Account           → The GCP identity that CI will impersonate
#   4. IAM Bindings              → Connects everything together with permissions
#
# INTERVIEW TALKING POINTS:
#   - "We use Workload Identity Federation instead of stored keys"
#   - "Each CI run gets a fresh, short-lived token — no permanent credentials"
#   - "The attribute_condition restricts access to our specific repository"
#   - "This follows the principle of least privilege and zero-trust"
# =============================================================================


# -----------------------------------------------------------------------------
# 1. Workload Identity Pool
# -----------------------------------------------------------------------------
# A pool is a logical grouping of external identity providers.
# Think of it as a "trust boundary" — you can have multiple providers
# (GitHub, GitLab, AWS, etc.) in one pool, or separate pools for isolation.
#
# For this prototype, we create one pool specifically for GitHub Actions.
resource "google_iam_workload_identity_pool" "github" {
  # The ID must be unique within the project and 4-32 characters
  workload_identity_pool_id = "github-actions-pool"

  display_name = "GitHub Actions Pool"
  description  = "Workload Identity Pool for GitHub Actions CI/CD"

  # A pool can be disabled to immediately revoke all external access
  # without deleting the configuration (useful for incident response)
  disabled = false
}


# -----------------------------------------------------------------------------
# 2. OIDC Provider (connects the pool to GitHub)
# -----------------------------------------------------------------------------
# The provider tells Google HOW to verify tokens from GitHub Actions.
#
# WHAT IS OIDC?
#   OpenID Connect is an identity protocol built on OAuth 2.0.
#   GitHub Actions can generate OIDC tokens that contain claims like:
#     - repository: "achimstruve/MCPAuthPrototype"
#     - ref: "refs/heads/main"
#     - workflow: "CI Pipeline"
#     - actor: "achimstruve"
#
#   Google verifies these tokens by:
#     1. Fetching GitHub's public keys from the issuer_uri
#     2. Verifying the token's signature
#     3. Checking the claims match the attribute_condition
#
resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"

  display_name = "GitHub Actions Provider"
  description  = "OIDC provider for GitHub Actions workflows"

  # ---------------------------------------------------------------------------
  # Attribute Mapping
  # ---------------------------------------------------------------------------
  # Maps claims from the GitHub OIDC token to Google attributes.
  # These mapped attributes can be used in IAM conditions and audit logs.
  #
  # GitHub OIDC token claims (assertion.*):
  #   - sub: "repo:owner/repo:ref:refs/heads/main" (subject)
  #   - repository: "owner/repo"
  #   - actor: "username" (who triggered the workflow)
  #   - ref: "refs/heads/main" (branch)
  #   - workflow: "CI Pipeline" (workflow name)
  #
  # Google attributes (google.* and attribute.*):
  #   - google.subject: Required, used for audit logging
  #   - attribute.*: Custom attributes for IAM conditions
  attribute_mapping = {
    # Required: Maps to the unique identifier of the external identity
    "google.subject" = "assertion.sub"

    # Custom attributes we can use in IAM conditions
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  # ---------------------------------------------------------------------------
  # Attribute Condition
  # ---------------------------------------------------------------------------
  # CRITICAL SECURITY CONTROL!
  #
  # This CEL (Common Expression Language) expression restricts which GitHub
  # repos can authenticate. Without this, ANY public GitHub repo could
  # potentially get a token for your GCP project!
  #
  # We restrict to our specific repository. In production, you might also
  # restrict to specific branches:
  #   assertion.repository == 'org/repo' && assertion.ref == 'refs/heads/main'
  attribute_condition = "assertion.repository == '${var.github_repo}'"

  # ---------------------------------------------------------------------------
  # OIDC Configuration
  # ---------------------------------------------------------------------------
  oidc {
    # The OIDC issuer URL for GitHub Actions.
    # Google fetches the discovery document from:
    #   https://token.actions.githubusercontent.com/.well-known/openid-configuration
    # This contains the public keys used to verify GitHub's OIDC tokens.
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}


# -----------------------------------------------------------------------------
# 3. Service Account for GitHub Actions CI
# -----------------------------------------------------------------------------
# This is the GCP identity that GitHub Actions will "become" after the
# OIDC token exchange. It determines what the CI pipeline can do in GCP.
#
# We follow the principle of least privilege: this SA can ONLY push images
# to Artifact Registry. It cannot delete clusters, read secrets, etc.
resource "google_service_account" "github_actions" {
  account_id   = "github-actions-ci"
  display_name = "GitHub Actions CI"
  description  = "Service account for GitHub Actions CI/CD pipeline (push images to Artifact Registry)"
}


# -----------------------------------------------------------------------------
# 4. Grant Artifact Registry Writer Role to CI Service Account
# -----------------------------------------------------------------------------
# This IAM binding gives the CI service account permission to push (write)
# Docker images to Artifact Registry.
#
# roles/artifactregistry.writer includes:
#   - artifactregistry.repositories.uploadArtifacts (push images)
#   - artifactregistry.repositories.downloadArtifacts (pull images)
#   - artifactregistry.tags.* (create/update tags)
#
# It does NOT include:
#   - artifactregistry.repositories.delete (can't delete the repo)
#   - artifactregistry.repositories.create (can't create new repos)
resource "google_project_iam_member" "github_actions_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}


# -----------------------------------------------------------------------------
# 5. Allow GitHub Actions to Impersonate the CI Service Account
# -----------------------------------------------------------------------------
# This is the final piece of the WIF puzzle. It says:
#   "External identities from the github-actions-pool that have
#    attribute.repository == 'achimstruve/MCPAuthPrototype'
#    are allowed to impersonate the github-actions-ci service account."
#
# The member format uses "principalSet://" which matches a SET of identities
# based on attributes, rather than a single specific identity.
#
# Format breakdown:
#   principalSet://iam.googleapis.com/
#     projects/<number>/locations/global/workloadIdentityPools/<pool>
#     /attribute.repository/<repo>
#
# This means: any workflow run from the specified repository can impersonate
# this service account, regardless of branch or actor.
resource "google_service_account_iam_member" "github_actions_wif" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}


# =============================================================================
# Summary of the Security Chain
# =============================================================================
#
#   GitHub Actions                  Google Cloud
#   ─────────────                   ────────────
#   Workflow runs on main     →     OIDC token verified by STS
#   Token says "repo X"       →     attribute_condition checks repo
#   Condition passes           →     Short-lived access token issued
#   Token impersonates SA     →     github-actions-ci SA
#   SA has AR writer role     →     Can push images to Artifact Registry
#   SA has NO other roles     →     Cannot access secrets, clusters, etc.
#
# If someone forks your repo and runs the workflow:
#   - The OIDC token says "repo fork-owner/MCPAuthPrototype"
#   - attribute_condition checks for "achimstruve/MCPAuthPrototype"
#   - MISMATCH → authentication fails → no GCP access
#
# This is why WIF is the recommended approach for all cloud CI/CD pipelines.
# =============================================================================
