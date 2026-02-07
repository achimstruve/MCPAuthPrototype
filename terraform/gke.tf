# =============================================================================
# gke.tf - Google Kubernetes Engine Cluster Configuration
# =============================================================================
#
# This file defines the GKE cluster that will run our MCP server.
#
# GKE STANDARD vs AUTOPILOT:
# - Standard (what we use): You manage node pools, scaling, machine types
# - Autopilot: Google manages nodes, you just deploy pods
#
# We use Standard because:
# 1. Learning: Understanding nodes, scheduling, resource management
# 2. Control: Can observe pod placement with kubectl get pods -o wide
# 3. Cost visibility: See exactly what nodes cost
#
# For production, Autopilot is often simpler and can be more cost-effective.
# =============================================================================

resource "google_container_cluster" "mcp_prototype" {
  name     = var.cluster_name  # "mcp-prototype"
  location = var.zone          # "europe-west1-b" (zonal cluster)

  # ---------------------------------------------------------------------------
  # Node Pool Configuration
  # ---------------------------------------------------------------------------
  # We use the default node pool with our configuration.
  # For more complex setups, you'd use separate google_container_node_pool resources.

  initial_node_count = var.node_count  # 3 nodes

  node_config {
    machine_type = var.machine_type  # "e2-small" (2 vCPU, 2 GB RAM)
    disk_size_gb = var.disk_size_gb  # 30 GB

    # OAuth scopes define what GCP APIs the nodes can access
    # cloud-platform gives full access (scoped down by IAM at service account level)
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Labels applied to nodes (useful for node selectors)
    labels = var.labels

    # Metadata for the node VMs
    metadata = {
      # Disable legacy metadata API (security best practice)
      disable-legacy-endpoints = "true"
    }

    # Shielded Nodes (secure boot, integrity monitoring)
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }

  # ---------------------------------------------------------------------------
  # Workload Identity
  # ---------------------------------------------------------------------------
  # Workload Identity lets Kubernetes ServiceAccounts act as GCP ServiceAccounts.
  # This is THE recommended way to give pods access to GCP services.
  #
  # Without Workload Identity:
  # - Export a JSON key file for a GCP service account
  # - Mount it as a Kubernetes secret
  # - Set GOOGLE_APPLICATION_CREDENTIALS in the pod
  # - Hope nobody leaks the key file
  #
  # With Workload Identity:
  # - Annotate the K8s ServiceAccount with the GCP SA email
  # - Bind them together with IAM
  # - Pods automatically get temporary credentials
  # - No key files, no secrets to rotate

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # ---------------------------------------------------------------------------
  # Release Channel
  # ---------------------------------------------------------------------------
  # Determines how Kubernetes version upgrades are handled.
  #
  # Options:
  # - RAPID: Newest features, less stable
  # - REGULAR: Balance of features and stability (what we use)
  # - STABLE: Most tested, fewer features
  # - UNSPECIFIED: Manual version management

  release_channel {
    channel = "REGULAR"
  }

  # ---------------------------------------------------------------------------
  # Network Configuration
  # ---------------------------------------------------------------------------
  # Using default VPC network for simplicity.
  # Production would typically use a custom VPC with specific subnet configurations.

  network    = "default"
  subnetwork = "default"

  # ---------------------------------------------------------------------------
  # Cluster Add-ons
  # ---------------------------------------------------------------------------
  # Configure built-in cluster add-ons

  addons_config {
    # Horizontal Pod Autoscaler (HPA) - scales pods based on metrics
    horizontal_pod_autoscaling {
      disabled = false
    }

    # HTTP Load Balancing - enables GCP Ingress controller
    http_load_balancing {
      disabled = false
    }

    # GCE Persistent Disk CSI Driver - for persistent volumes
    gce_persistent_disk_csi_driver_config {
      enabled = true
    }
  }

  # Timeouts for long-running operations
  timeouts {
    create = "30m"
    update = "30m"
    delete = "30m"
  }

  # Prevent accidental deletion
  # Set to true in production!
  deletion_protection = false

  # ---------------------------------------------------------------------------
  # Lifecycle Configuration
  # ---------------------------------------------------------------------------
  # Ignore changes to node count since it might be modified by autoscaling
  # or manual kubectl operations

  lifecycle {
    ignore_changes = [
      initial_node_count,
    ]
  }
}

# =============================================================================
# Understanding GKE Cluster Creation
# =============================================================================
#
# When terraform apply creates this cluster:
#
# 1. Control Plane (managed by Google):
#    - API server, etcd, scheduler, controller-manager
#    - You never see or manage these VMs
#    - Google handles upgrades, patches, scaling
#
# 2. Worker Nodes (your VMs):
#    - 3 x e2-medium instances in europe-west1-b
#    - Run kubelet, container runtime
#    - Where your pods actually execute
#
# 3. Networking:
#    - Each pod gets an IP from the cluster CIDR
#    - Services get ClusterIP addresses
#    - Default network policies allow all traffic (we'll lock down later)
#
# After creation, run:
#   gcloud container clusters get-credentials mcp-prototype --zone europe-west1-b
#
# This configures kubectl to talk to your cluster.
# =============================================================================
