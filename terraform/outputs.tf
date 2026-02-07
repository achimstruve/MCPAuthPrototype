# =============================================================================
# outputs.tf - Output Values
# =============================================================================
#
# Outputs are values that Terraform exposes after applying the configuration.
# They're useful for:
# - Displaying important information after terraform apply
# - Passing values to other Terraform configurations (modules)
# - Scripting: terraform output -raw cluster_endpoint
#
# Think of outputs as the "return values" of your Terraform configuration.
# =============================================================================

# -----------------------------------------------------------------------------
# GKE Cluster Outputs
# -----------------------------------------------------------------------------

output "cluster_name" {
  description = "The name of the GKE cluster"
  value       = google_container_cluster.mcp_prototype.name
}

output "cluster_endpoint" {
  description = "The IP address of the GKE cluster master"
  value       = google_container_cluster.mcp_prototype.endpoint
  sensitive   = true  # Don't show in logs (it's an internal IP)
}

output "cluster_location" {
  description = "The zone where the cluster is located"
  value       = google_container_cluster.mcp_prototype.location
}

# Command to get credentials for kubectl
output "get_credentials_command" {
  description = "Command to configure kubectl for this cluster"
  value       = "gcloud container clusters get-credentials ${google_container_cluster.mcp_prototype.name} --zone ${google_container_cluster.mcp_prototype.location} --project ${var.project_id}"
}

# -----------------------------------------------------------------------------
# Artifact Registry Outputs
# -----------------------------------------------------------------------------

output "artifact_registry_repository" {
  description = "The full path to the Artifact Registry repository"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.mcp_server.repository_id}"
}

output "docker_image_base" {
  description = "Base path for Docker images (append :tag to use)"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.mcp_server.repository_id}/mcp-auth-prototype"
}

# -----------------------------------------------------------------------------
# Service Account Outputs
# -----------------------------------------------------------------------------

output "eso_service_account_email" {
  description = "Email of the service account for External Secrets Operator"
  value       = google_service_account.eso_secret_accessor.email
}

output "workload_identity_annotation" {
  description = "Annotation to add to Kubernetes ServiceAccount for Workload Identity"
  value       = "iam.gke.io/gcp-service-account=${google_service_account.eso_secret_accessor.email}"
}

# -----------------------------------------------------------------------------
# Secret Manager Outputs
# -----------------------------------------------------------------------------

output "jwt_secret_id" {
  description = "The ID of the JWT signing key secret in Secret Manager"
  value       = google_secret_manager_secret.jwt_signing_key.secret_id
}

# -----------------------------------------------------------------------------
# Helper Outputs
# -----------------------------------------------------------------------------

output "project_id" {
  description = "The GCP project ID"
  value       = var.project_id
}

output "region" {
  description = "The GCP region"
  value       = var.region
}
