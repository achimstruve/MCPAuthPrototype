# =============================================================================
# artifact-registry.tf - Google Artifact Registry Configuration
# =============================================================================
#
# Artifact Registry is GCP's container registry service. It stores Docker
# images that Kubernetes pulls when deploying pods.
#
# WHY ARTIFACT REGISTRY (not Docker Hub)?
# - Same network as GKE: Faster image pulls, no egress costs
# - IAM integration: Use GCP permissions, no separate Docker credentials
# - Vulnerability scanning: Built-in security scanning
# - Regional storage: Keep images close to your cluster
#
# IMPORT NOTE:
# This resource already exists (you created it manually). We'll import it
# into Terraform state so Terraform can manage it going forward:
#
#   terraform import google_artifact_registry_repository.mcp_server \
#     projects/mcpauthprototype/locations/europe-west1/repositories/mcp-server
# =============================================================================

resource "google_artifact_registry_repository" "mcp_server" {
  # Repository identifier (used in image paths)
  repository_id = var.artifact_registry_repository  # "mcp-server"

  # Location must match where you want to store images
  # Using same region as GKE cluster for faster pulls
  location = var.region  # "europe-west1"

  # Repository format - we're storing Docker/OCI images
  # Other options: MAVEN, NPM, PYTHON, APT, YUM, GO, etc.
  format = "DOCKER"

  # Human-readable description
  description = "Docker images for MCP Auth Prototype"

  # Labels for organization and cost tracking
  labels = var.labels

  # Cleanup policies (optional, not set for prototype)
  # In production, you might add policies to delete old images:
  #
  # cleanup_policies {
  #   id     = "delete-old-images"
  #   action = "DELETE"
  #   condition {
  #     older_than = "2592000s"  # 30 days
  #   }
  # }
}

# =============================================================================
# Understanding the Image Path
# =============================================================================
#
# After creation, images are pushed to:
#
#   europe-west1-docker.pkg.dev/mcpauthprototype/mcp-server/IMAGE_NAME:TAG
#   │                          │                 │          │
#   │                          │                 │          └── Your image
#   │                          │                 └── This repository
#   │                          └── Your project
#   └── Regional registry endpoint
#
# Example:
#   docker push europe-west1-docker.pkg.dev/mcpauthprototype/mcp-server/mcp-auth-prototype:v1
# =============================================================================
