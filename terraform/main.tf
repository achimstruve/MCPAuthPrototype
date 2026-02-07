# =============================================================================
# main.tf - Terraform Configuration and Provider Setup
# =============================================================================
#
# This file configures:
# 1. Terraform settings (required version, backend for state storage)
# 2. Provider configuration (Google Cloud Platform)
#
# WHAT IS TERRAFORM?
# Terraform is an Infrastructure as Code (IaC) tool. Instead of clicking
# around in the GCP Console or running gcloud commands, you DECLARE what
# infrastructure you want in these .tf files. Terraform then:
# - Compares your desired state (these files) with actual state (what exists)
# - Creates a plan showing what changes are needed
# - Applies those changes to reach the desired state
#
# WHAT IS A PROVIDER?
# A provider is a plugin that lets Terraform interact with a specific
# platform (GCP, AWS, Azure, etc.). The google provider knows how to
# create GCP resources like GKE clusters, Cloud Storage buckets, etc.
# =============================================================================

# -----------------------------------------------------------------------------
# Terraform Settings Block
# -----------------------------------------------------------------------------
# This block configures Terraform itself, not the infrastructure.
terraform {
  # Minimum Terraform version required
  # We use >= to allow newer versions, but you could pin to exact version
  required_version = ">= 1.0.0"

  # Required providers and their versions
  required_providers {
    google = {
      source  = "hashicorp/google"       # Where to download the provider
      version = "~> 5.0"                  # Allow 5.x versions (not 6.0+)
    }
  }

  # STATE STORAGE (Backend)
  # -----------------------
  # Terraform needs to track what resources it has created. This is stored
  # in a "state file". By default, it's stored locally as terraform.tfstate.
  #
  # For production, you'd use a remote backend like GCS:
  #
  # backend "gcs" {
  #   bucket = "my-terraform-state-bucket"
  #   prefix = "mcp-prototype"
  # }
  #
  # Benefits of remote state:
  # - Team collaboration (everyone uses same state)
  # - State locking (prevents concurrent modifications)
  # - Backup and versioning
  #
  # For this prototype, we use local state (the default).
  # The state file will be created as terraform.tfstate in this directory.
}

# -----------------------------------------------------------------------------
# Google Cloud Provider Configuration
# -----------------------------------------------------------------------------
# This configures the google provider with default settings.
# All resources will be created in this project and region unless overridden.
provider "google" {
  project = var.project_id    # GCP project ID (from variables.tf)
  region  = var.region        # Default region for regional resources
}

# Note: We don't specify credentials here because we're using:
# - Application Default Credentials (ADC) when running locally
# - gcloud auth application-default login (already configured)
# This is more secure than putting a service account key in the code.
