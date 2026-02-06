"""
MCP Server implementation using FastMCP v2 with JWT authentication middleware.

This module creates and runs the MCP server with:
- Two tools: get_public_info and get_confidential_info
- JWT authentication: every MCP request must include a valid Bearer token
- Scope-based authorization: token scopes determine which tools are visible/callable
- Health and readiness HTTP endpoints (for Kubernetes probes)
- Structured JSON logging for all auth decisions
- Streamable HTTP transport (the current MCP standard)

Architecture:
    The auth flow for every MCP request:

    1. Client sends HTTP request with "Authorization: Bearer <jwt>" header
    2. FastMCP's RequestContextMiddleware stores the HTTP request in a ContextVar
    3. Our AuthMiddleware intercepts the MCP method (tools/list or tools/call)
    4. Middleware calls get_http_request() to retrieve the Authorization header
    5. auth.validate_token() verifies the JWT signature, expiration, and claims
    6. For tools/list: middleware filters the tool list by comparing token scopes
       against TOOL_SCOPE_MAP
    7. For tools/call: middleware checks that the token has the required scope
       before allowing the call to proceed

    This is "defense in depth": even if a client somehow bypasses the tools/list
    filter and tries to call a tool directly, the tools/call check blocks it.

Running the server:
    uv run python -m src.server

    This starts the server on http://0.0.0.0:8080 with:
    - MCP endpoint at /mcp (Streamable HTTP)
    - Health check at /health
    - Readiness check at /ready
"""

import json
import logging
import sys
import uuid
from typing import Sequence

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import Tool, ToolResult
from mcp.types import CallToolRequestParams, ListToolsRequest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.auth import AuthError, TokenInfo, validate_token
from src.config import settings
from src.tools import TOOL_SCOPE_MAP

# ---------------------------------------------------------------------------
# Structured JSON Logging
# ---------------------------------------------------------------------------
# In production (Kubernetes), logs go to stdout and are collected by the
# cluster's logging agent. JSON format is essential because:
# - Cloud logging systems (Google Cloud Logging, ELK, Datadog) can parse
#   and index JSON fields automatically
# - You can filter logs by subject, tool, decision, etc.
# - It's machine-readable, which enables alerting on auth failures
#
# We use a custom JSON formatter that outputs one JSON object per log line.


class JSONLogFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.

    Each log line contains structured fields that cloud logging systems
    can parse and index. Example output:

        {"timestamp": "2026-02-06T10:30:00", "level": "INFO", "logger": "mcp-server",
         "message": "Tool call authorized", "subject": "alice", "tool": "get_public_info"}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any extra fields passed via logger.info("msg", extra={...})
        # This is how we attach structured auth data to log entries.
        if hasattr(record, "auth_data"):
            log_entry.update(record.auth_data)
        return json.dumps(log_entry)


# Configure the root logger with our JSON formatter
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONLogFormatter())

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    handlers=[handler],
)
logger = logging.getLogger("mcp-server")


# ---------------------------------------------------------------------------
# Authentication & Authorization Middleware
# ---------------------------------------------------------------------------
# This is the core security component. It intercepts every MCP protocol
# request and enforces two rules:
#
# 1. Authentication: Every request must have a valid JWT token
# 2. Authorization: The token's scopes must match the requested tool
#
# The middleware uses FastMCP's hook system:
# - on_list_tools: Called when a client requests the tool list (tools/list)
# - on_call_tool: Called when a client invokes a tool (tools/call)
#
# Both hooks follow the same pattern:
#   1. Extract the Authorization header from the HTTP request
#   2. Validate the JWT token (signature, expiration, claims)
#   3. Check scopes against TOOL_SCOPE_MAP
#   4. Allow or deny the request
#   5. Log the decision with structured data


class AuthMiddleware(Middleware):
    """
    JWT authentication and scope-based authorization middleware.

    Intercepts all MCP tool requests and enforces access control:
    - tools/list responses are filtered to only include authorized tools
    - tools/call requests are rejected if the token lacks the required scope

    This implements the "Zero Trust" principle: never trust, always verify.
    Every request is authenticated and authorized independently, even within
    the same session.
    """

    def _get_auth_header(self) -> str | None:
        """
        Extract the Authorization header from the current HTTP request.

        FastMCP's RequestContextMiddleware automatically stores each HTTP
        request in a ContextVar. The get_http_request() utility retrieves it,
        giving us access to the full HTTP request including headers.

        Returns None if no HTTP request is available (e.g., stdio transport).
        """
        try:
            request = get_http_request()
            return request.headers.get("authorization")
        except RuntimeError:
            return None

    def _authenticate(self, request_id: str) -> TokenInfo:
        """
        Validate the JWT token and return the decoded claims.

        This is the authentication step: "Who are you?"
        If validation fails, logs the failure and raises AuthError.

        Args:
            request_id: Unique ID for this request (for log correlation)

        Returns:
            TokenInfo with the validated subject and scopes

        Raises:
            AuthError: If authentication fails for any reason
        """
        auth_header = self._get_auth_header()
        try:
            token_info = validate_token(auth_header)
            logger.info(
                "Authentication successful",
                extra={
                    "auth_data": {
                        "request_id": request_id,
                        "subject": token_info.subject,
                        "scopes": token_info.scopes,
                        "decision": "authenticated",
                    }
                },
            )
            return token_info
        except AuthError:
            logger.warning(
                "Authentication failed",
                extra={
                    "auth_data": {
                        "request_id": request_id,
                        "decision": "rejected",
                        "reason": "authentication_failed",
                    }
                },
            )
            raise

    async def on_list_tools(
        self,
        context: MiddlewareContext[ListToolsRequest],
        call_next: CallNext[ListToolsRequest, Sequence[Tool]],
    ) -> Sequence[Tool]:
        """
        Intercept tools/list requests to filter tools by token scope.

        When a client asks "what tools are available?", we:
        1. Authenticate the request (validate JWT)
        2. Get the full tool list from the server
        3. Filter it to only include tools the token's scopes authorize

        This means a client with scope ["public:read"] only sees
        get_public_info, and doesn't even know get_confidential_info exists.

        This is the first line of defense. The on_call_tool hook below
        provides a second check (defense in depth).
        """
        request_id = str(uuid.uuid4())[:8]

        # Step 1: Authenticate
        token_info = self._authenticate(request_id)

        # Step 2: Get full tool list from the server
        all_tools = await call_next(context)

        # Step 3: Filter tools by scope
        # For each tool, look up its required scope in TOOL_SCOPE_MAP.
        # Only include the tool if the token's scopes contain the required scope.
        authorized_tools = []
        for tool in all_tools:
            required_scope = TOOL_SCOPE_MAP.get(tool.name)
            if required_scope and required_scope in token_info.scopes:
                authorized_tools.append(tool)

        logger.info(
            "Tool list filtered by scope",
            extra={
                "auth_data": {
                    "request_id": request_id,
                    "subject": token_info.subject,
                    "scopes": token_info.scopes,
                    "total_tools": len(all_tools),
                    "authorized_tools": [t.name for t in authorized_tools],
                    "decision": "filtered",
                }
            },
        )

        return authorized_tools

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        """
        Intercept tools/call requests to enforce scope-based authorization.

        When a client tries to invoke a tool, we:
        1. Authenticate the request (validate JWT)
        2. Look up the required scope for the requested tool
        3. Check that the token has that scope
        4. Only then allow the tool to execute

        This is the second line of defense (defense in depth):
        even if a client somehow knows about a tool they shouldn't
        (e.g., by guessing the name), this check blocks the call.

        A PermissionError is raised for unauthorized calls, which FastMCP
        converts to an MCP error response.
        """
        request_id = str(uuid.uuid4())[:8]
        tool_name = context.message.name

        # Step 1: Authenticate
        token_info = self._authenticate(request_id)

        # Step 2: Check authorization
        required_scope = TOOL_SCOPE_MAP.get(tool_name)

        if required_scope is None:
            # Tool exists but has no scope mapping - deny by default.
            # This is the "fail closed" principle: if we don't explicitly
            # know what scope a tool needs, deny access rather than allow it.
            logger.warning(
                "Tool call denied: no scope mapping found",
                extra={
                    "auth_data": {
                        "request_id": request_id,
                        "subject": token_info.subject,
                        "tool": tool_name,
                        "decision": "denied",
                        "reason": "no_scope_mapping",
                    }
                },
            )
            raise PermissionError(f"Access denied: tool '{tool_name}' has no scope mapping")

        if required_scope not in token_info.scopes:
            # Token is valid but lacks the required scope for this tool.
            logger.warning(
                "Tool call denied: insufficient scope",
                extra={
                    "auth_data": {
                        "request_id": request_id,
                        "subject": token_info.subject,
                        "tool": tool_name,
                        "required_scope": required_scope,
                        "token_scopes": token_info.scopes,
                        "decision": "denied",
                        "reason": "insufficient_scope",
                    }
                },
            )
            raise PermissionError(
                f"Access denied: tool '{tool_name}' requires scope '{required_scope}'"
            )

        # Step 3: Authorized - allow the tool call to proceed
        logger.info(
            "Tool call authorized",
            extra={
                "auth_data": {
                    "request_id": request_id,
                    "subject": token_info.subject,
                    "tool": tool_name,
                    "required_scope": required_scope,
                    "decision": "allowed",
                }
            },
        )

        return await call_next(context)


# ---------------------------------------------------------------------------
# Create the MCP server with auth middleware
# ---------------------------------------------------------------------------
# The middleware list is processed in order. Our AuthMiddleware runs on every
# MCP request before the tool handlers execute.
mcp = FastMCP(
    name="mcp-auth-prototype",
    instructions=(
        "Secure MCP server prototype demonstrating token-based authentication "
        "and scope-based tool access. Provides access to company documents "
        "based on the caller's authorization level."
    ),
    middleware=[AuthMiddleware()],
)


# ---------------------------------------------------------------------------
# Tool: get_public_info
# ---------------------------------------------------------------------------
# Required scope: "public:read" (defined in TOOL_SCOPE_MAP, enforced by AuthMiddleware)
@mcp.tool(description="Retrieve public company information document.")
def get_public_info() -> str:
    """
    Returns the contents of the public company information document.

    Accessible to users with the 'public:read' scope.
    Contains general information: company overview, products, contact details.
    """
    doc_path = settings.documents_dir / "public.md"
    logger.info("Tool executed: get_public_info")

    if not doc_path.exists():
        logger.error("Public document not found at %s", doc_path)
        return "Error: public document not found."

    return doc_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tool: get_confidential_info
# ---------------------------------------------------------------------------
# Required scope: "confidential:read" (defined in TOOL_SCOPE_MAP, enforced by AuthMiddleware)
@mcp.tool(description="Retrieve confidential company strategy document.")
def get_confidential_info() -> str:
    """
    Returns the contents of the confidential strategy document.

    Requires the 'confidential:read' scope. Contains sensitive information:
    financial projections, acquisition targets, competitive intelligence.
    """
    doc_path = settings.documents_dir / "confidential.md"
    logger.info("Tool executed: get_confidential_info")

    if not doc_path.exists():
        logger.error("Confidential document not found at %s", doc_path)
        return "Error: confidential document not found."

    return doc_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Health and Readiness Endpoints
# ---------------------------------------------------------------------------
# These are plain HTTP endpoints (not MCP protocol) for Kubernetes probes.
# They do NOT require authentication because:
# - The kubelet (Kubernetes agent) that calls these doesn't have a JWT token
# - Health checks must work even when the auth system has issues
# - They don't expose sensitive data or operations
# - In production, they're only accessible within the cluster (ClusterIP Service)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> Response:
    """Liveness probe: is the server process alive and responsive?"""
    return JSONResponse({"status": "healthy"})


@mcp.custom_route("/ready", methods=["GET"])
async def readiness_check(request: Request) -> Response:
    """Readiness probe: can this pod accept MCP requests?"""
    public_doc = settings.documents_dir / "public.md"
    confidential_doc = settings.documents_dir / "confidential.md"

    if not public_doc.exists() or not confidential_doc.exists():
        return JSONResponse(
            {"status": "not_ready", "reason": "document files missing"},
            status_code=503,
        )

    return JSONResponse({"status": "ready"})


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info(
        "Starting MCP server on %s:%d (transport=streamable-http, auth=enabled)",
        settings.host,
        settings.port,
    )
    mcp.run(
        transport="streamable-http",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
