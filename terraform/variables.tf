# =============================================================================
# variables.tf - Input Variables
# =============================================================================
#
# Variables allow you to parameterize your Terraform configuration.
# Instead of hardcoding values like "mcpauthprototype", you use var.project_id.
#
# BENEFITS:
# - Reusability: Same code works for dev, staging, prod with different values
# - Security: Sensitive values can be passed at runtime, not stored in code
# - Clarity: All configurable values in one place
#
# HOW TO SET VARIABLE VALUES:
# 1. terraform.tfvars file (automatically loaded)
# 2. Command line: terraform apply -var="project_id=myproject"
# 3. Environment variables: TF_VAR_project_id=myproject
# 4. Interactive prompt (if no default and not set)
# =============================================================================

# -----------------------------------------------------------------------------
# Project Configuration
# -----------------------------------------------------------------------------

variable "project_id" {
  description = "The GCP project ID where resources will be created"
  type        = string

  # No default - must be provided explicitly
  # This is intentional: you don't want to accidentally deploy to wrong project
}

variable "region" {
  description = "The GCP region for regional resources (Artifact Registry, etc.)"
  type        = string
  default     = "europe-west1"

  # Why europe-west1?
  # - Close to your users (assuming Europe)
  # - Good availability of GCP services
  # - Reasonable pricing
}

variable "zone" {
  description = "The GCP zone for zonal resources (GKE cluster)"
  type        = string
  default     = "europe-west1-b"

  # Why a specific zone vs regional?
  # - Zonal clusters are cheaper than regional clusters
  # - For a prototype, we don't need multi-zone high availability
  # - Regional clusters spread nodes across 3 zones (3x node cost)
}

# -----------------------------------------------------------------------------
# GKE Cluster Configuration
# -----------------------------------------------------------------------------

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
  default     = "mcp-prototype"
}

variable "node_count" {
  description = "Number of nodes in the GKE cluster"
  type        = number
  default     = 3

  # Why 3 nodes?
  # - 2 for MCP server replicas
  # - 1 for system components (ArgoCD, ESO, etc.)
  # - Allows us to observe pod scheduling across nodes
}

variable "machine_type" {
  description = "GCE machine type for GKE nodes"
  type        = string
  default     = "e2-medium"

  # e2-small: 2 vCPU, 2 GB RAM
  # Smallest viable size that can run our workloads
  # For production, you'd likely use e2-medium or larger
}

variable "disk_size_gb" {
  description = "Disk size in GB for each GKE node"
  type        = number
  default     = 30

  # 30 GB is enough for:
  # - Container images
  # - System components
  # - Logs and temporary data
}

# -----------------------------------------------------------------------------
# Artifact Registry Configuration
# -----------------------------------------------------------------------------

variable "artifact_registry_repository" {
  description = "Name of the Artifact Registry repository for Docker images"
  type        = string
  default     = "mcp-server"
}

# -----------------------------------------------------------------------------
# Secret Manager Configuration
# -----------------------------------------------------------------------------

variable "jwt_secret_name" {
  description = "Name of the Secret Manager secret for JWT signing key"
  type        = string
  default     = "mcp-jwt-signing-key"
}

# -----------------------------------------------------------------------------
# Naming and Labeling
# -----------------------------------------------------------------------------

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# Common labels applied to all resources for organization and cost tracking
variable "labels" {
  description = "Labels to apply to all resources"
  type        = map(string)
  default = {
    project     = "mcp-auth-prototype"
    managed-by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# GitHub Actions CI Configuration (Phase 7)
# -----------------------------------------------------------------------------

variable "github_repo" {
  description = "GitHub repository in 'owner/repo' format (used for Workload Identity Federation)"
  type        = string
  default     = "achimstruve/MCPAuthPrototype"

  # This is used in the WIF attribute_condition to restrict which repo
  # can authenticate to GCP. Only workflows from THIS repo can get
  # GCP credentials — forks and other repos are blocked.
}
