# =============================================================================
# secret-manager.tf - Google Secret Manager Configuration
# =============================================================================
#
# Secret Manager is GCP's service for storing sensitive data like API keys,
# passwords, and cryptographic keys.
#
# WHY SECRET MANAGER (not Kubernetes Secrets directly)?
# - Centralized: One source of truth, accessible by multiple clusters
# - Versioning: Keeps history of all secret versions
# - Audit logging: Every access logged in Cloud Audit Logs
# - IAM: Fine-grained access control
# - Encryption: Encrypted at rest with Google-managed or customer keys
#
# IMPORTANT: We only manage the SECRET STRUCTURE here, not the actual value!
# The secret value was created manually and should NEVER be in Terraform code.
# Terraform manages: "A secret called mcp-jwt-signing-key exists"
# Terraform does NOT manage: "The secret value is abc123..."
#
# IMPORT NOTE:
# This resource already exists (you created it manually). We'll import it:
#
#   terraform import google_secret_manager_secret.jwt_signing_key \
#     projects/mcpauthprototype/secrets/mcp-jwt-signing-key
# =============================================================================

resource "google_secret_manager_secret" "jwt_signing_key" {
  # Secret identifier
  secret_id = var.jwt_secret_name  # "mcp-jwt-signing-key"

  # Replication configuration - where secret data is stored
  replication {
    # User-managed means we choose specific locations
    user_managed {
      replicas {
        location = var.region  # "europe-west1"
      }
      # For higher availability, you could add more replicas:
      # replicas {
      #   location = "europe-west2"
      # }
    }

    # Alternative: automatic replication (Google chooses locations)
    # automatic {}
  }

  # Labels for organization
  labels = var.labels
}

# =============================================================================
# Understanding Secret Manager Structure
# =============================================================================
#
# Secret Manager has a hierarchy:
#
#   Secret (what we define here)
#     └── Version 1 (the actual value, added via CLI or API)
#     └── Version 2 (if you rotate the secret)
#     └── Version 3 ...
#
# When you ran:
#   echo -n "$JWT_SECRET" | gcloud secrets create mcp-jwt-signing-key --data-file=-
#
# It created BOTH the secret AND version 1 with the value.
#
# Terraform only manages the secret metadata (name, replication, labels).
# The version with the actual value was created outside Terraform.
#
# To read the secret (for verification):
#   gcloud secrets versions access latest --secret=mcp-jwt-signing-key
# =============================================================================

# =============================================================================
# Secret Version (NOT RECOMMENDED for sensitive data)
# =============================================================================
#
# You CAN manage secret versions in Terraform, but then the secret value
# would be in your Terraform state file (and possibly .tf files).
#
# DON'T DO THIS in production:
#
# resource "google_secret_manager_secret_version" "jwt_key_version" {
#   secret      = google_secret_manager_secret.jwt_signing_key.id
#   secret_data = "my-secret-value"  # <-- This would be in state!
# }
#
# INSTEAD, manage secret values via:
# - gcloud CLI (what you did)
# - GCP Console
# - CI/CD pipeline with temporary credentials
# - HashiCorp Vault integration
# =============================================================================
