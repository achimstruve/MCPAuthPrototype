"""
Application configuration loaded from environment variables.

Uses pydantic-settings to define typed configuration that automatically reads
from environment variables. This follows the 12-factor app methodology:
all config comes from the environment, never hardcoded in source code.

In production (Kubernetes), these are injected via the Deployment manifest:
- MCP_HOST, MCP_PORT, MCP_LOG_LEVEL come from the ConfigMap
- MCP_JWT_SECRET_KEY comes from the External Secret (synced from GCP Secret Manager)

Locally, you can set them via environment variables or a .env file.
"""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Server configuration with environment variable bindings.

    Each field maps to an environment variable with the MCP_ prefix.
    For example, `host` reads from MCP_HOST, `jwt_secret_key` reads
    from MCP_JWT_SECRET_KEY.

    The `model_config` at the bottom controls the prefix and .env file behavior.
    """

    # --- Server settings ---

    # The network interface to bind to.
    # "0.0.0.0" means "listen on all interfaces" which is required inside Docker
    # containers so that traffic from outside the container can reach the server.
    # Locally you might use "127.0.0.1" to only accept local connections.
    host: str = "0.0.0.0"

    # The port the server listens on. 8080 is a common choice for non-root
    # HTTP services (ports below 1024 require root privileges).
    port: int = 8080

    # Logging verbosity. Maps to Python's logging levels.
    # "info" is good for production; "debug" for local development.
    log_level: str = "info"

    # --- Authentication settings (used in Phase 2) ---

    # The secret key used to validate JWT signatures. In production this is
    # injected from GCP Secret Manager via External Secrets Operator.
    # Default is for local development only - NEVER use this in production.
    jwt_secret_key: str = "dev-secret-change-me"

    # The algorithm used for JWT signing. HS256 = HMAC with SHA-256.
    # This is a symmetric algorithm: the same key signs and verifies.
    # Production systems often use RS256 (asymmetric) where only the auth
    # server has the private key, and verifiers use the public key.
    jwt_algorithm: str = "HS256"

    # --- Document settings ---

    # Path to the directory containing the documents served by the MCP tools.
    # In Docker, this is /app/documents/ (copied into the image).
    # Locally, it's relative to the project root.
    documents_dir: Path = Path("documents")

    model_config = {
        # All environment variables are prefixed with MCP_ to avoid collisions.
        # For example: MCP_HOST=0.0.0.0, MCP_PORT=8080, MCP_JWT_SECRET_KEY=my-secret
        "env_prefix": "MCP_",
        # Also read from .env file if it exists (useful for local development).
        # The .env file is in .gitignore so secrets won't be committed.
        "env_file": ".env",
        # Environment variables take precedence over .env file values.
        "env_file_encoding": "utf-8",
    }


# Singleton instance: import this from other modules.
# Created once at module load time, reads environment variables immediately.
settings = Settings()
