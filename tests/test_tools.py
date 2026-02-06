"""
Integration tests for tool authorization via the MCP server.

These tests exercise the full auth flow through the MCP protocol:
HTTP request -> AuthMiddleware -> tool list filtering / tool call authorization.

Unlike test_auth.py (which tests validate_token() in isolation), these tests
verify that the middleware correctly:
- Filters the tool list based on token scopes
- Blocks unauthorized tool calls
- Allows authorized tool calls and returns document content

Test approach:
    We use httpx.AsyncClient with the FastMCP ASGI app (in-memory, no real
    server process needed). The ASGI app requires its lifespan to be started
    (this initializes the StreamableHTTP session manager's task group), so
    we manually manage the ASGI lifespan in a fixture.

    Each test follows the MCP protocol:
    1. POST to /mcp with "initialize" to start a session
    2. Use the returned Mcp-Session-Id for subsequent requests
    3. POST "tools/list" or "tools/call" with an Authorization header

    This is a true integration test: the request goes through the full
    Starlette -> FastMCP -> Middleware -> Tool handler pipeline.
"""

import asyncio
import json

import httpx
import pytest

from src.server import mcp


@pytest.fixture
async def mcp_client(make_auth_header):
    """
    Fixture that provides a factory for creating authenticated MCP test clients.

    This fixture:
    1. Creates the ASGI app from the FastMCP server
    2. Manually starts the ASGI lifespan (required to initialize the
       StreamableHTTP session manager's task group)
    3. Returns a factory function that creates MCP sessions with given tokens
    4. Cleans up the lifespan on teardown

    The ASGI lifespan is like Docker's ENTRYPOINT: it runs setup code when the
    app starts and cleanup code when it stops. Without it, the MCP transport
    layer isn't initialized and all requests fail.
    """
    app = mcp.http_app(transport="streamable-http")

    # --- Start ASGI lifespan ---
    # The ASGI lifespan protocol works via message passing:
    # we send "lifespan.startup", the app does its init, then sends
    # "lifespan.startup.complete" back.
    startup_complete = asyncio.Event()
    shutdown_triggered = asyncio.Event()

    async def receive():
        if not startup_complete.is_set():
            startup_complete.set()
            return {"type": "lifespan.startup"}
        await shutdown_triggered.wait()
        return {"type": "lifespan.shutdown"}

    async def send(message):
        pass  # We don't need to inspect the lifespan responses

    scope = {"type": "lifespan", "asgi": {"version": "3.0"}}
    lifespan_task = asyncio.create_task(app(scope, receive, send))

    # Wait for the app to finish its startup
    await startup_complete.wait()
    await asyncio.sleep(0.1)  # Give the task group time to initialize

    # --- Provide the factory function ---
    clients = []  # Track clients for cleanup

    async def _create_mcp_client(
        sub: str = "test-user",
        scopes: list[str] | None = None,
    ):
        """
        Create an authenticated MCP client session.

        Returns (client, session_id, auth_header) where:
        - client: httpx.AsyncClient bound to the ASGI app
        - session_id: MCP session ID from the initialize handshake
        - auth_header: The Authorization header used (for subsequent requests)
        """
        auth_header = make_auth_header(sub=sub, scopes=scopes or [])

        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport)
        clients.append(client)

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": auth_header,
        }

        response = await client.post(
            "http://testserver/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0"},
                },
            },
        )

        session_id = response.headers.get("mcp-session-id")
        return client, session_id, auth_header

    yield _create_mcp_client

    # --- Cleanup ---
    for client in clients:
        await client.aclose()

    shutdown_triggered.set()
    await lifespan_task


# ---------------------------------------------------------------------------
# Helper functions for MCP protocol requests
# ---------------------------------------------------------------------------


async def list_tools(client, session_id: str, auth_header: str) -> dict:
    """Send a tools/list request and return the parsed JSON-RPC response."""
    response = await client.post(
        "http://testserver/mcp",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id,
            "Authorization": auth_header,
        },
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    return _parse_sse_response(response.text)


async def call_tool(
    client, session_id: str, auth_header: str, tool_name: str
) -> dict:
    """Send a tools/call request and return the parsed JSON-RPC response."""
    response = await client.post(
        "http://testserver/mcp",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id,
            "Authorization": auth_header,
        },
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": {}},
        },
    )
    return _parse_sse_response(response.text)


def _parse_sse_response(text: str) -> dict:
    """
    Parse an SSE (Server-Sent Events) response body into a JSON dict.

    MCP Streamable HTTP transport returns responses as SSE events:
        event: message
        data: {"jsonrpc":"2.0","id":1,"result":{...}}

    We extract the JSON from the 'data:' line.
    """
    for line in text.strip().split("\n"):
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}


# ---------------------------------------------------------------------------
# Test: Tool list filtering by scope
# ---------------------------------------------------------------------------


class TestToolListFiltering:
    """Tests for scope-based tool list filtering (on_list_tools middleware)."""

    async def test_public_scope_sees_only_public_tool(self, mcp_client):
        """
        A token with only 'public:read' scope should only see get_public_info.

        The get_confidential_info tool should be completely hidden - the client
        doesn't even know it exists.
        """
        client, session_id, auth_header = await mcp_client(
            sub="alice", scopes=["public:read"]
        )
        data = await list_tools(client, session_id, auth_header)
        tools = data["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        assert tool_names == ["get_public_info"]

    async def test_both_scopes_sees_both_tools(self, mcp_client):
        """A token with both scopes should see both tools."""
        client, session_id, auth_header = await mcp_client(
            sub="bob", scopes=["public:read", "confidential:read"]
        )
        data = await list_tools(client, session_id, auth_header)
        tools = data["result"]["tools"]
        tool_names = sorted([t["name"] for t in tools])

        assert tool_names == ["get_confidential_info", "get_public_info"]

    async def test_no_scopes_sees_no_tools(self, mcp_client):
        """
        A token with an empty scope list should see no tools at all.

        The user is authenticated (valid token) but has no authorization.
        """
        client, session_id, auth_header = await mcp_client(
            sub="dave", scopes=[]
        )
        data = await list_tools(client, session_id, auth_header)
        tools = data["result"]["tools"]

        assert tools == []


# ---------------------------------------------------------------------------
# Test: Tool call authorization
# ---------------------------------------------------------------------------


class TestToolCallAuthorization:
    """Tests for scope-based tool call authorization (on_call_tool middleware)."""

    async def test_unauthorized_tool_call_returns_permission_denied(self, mcp_client):
        """
        Calling a tool without the required scope should return a permission error.

        This tests the "defense in depth" layer: even if a client somehow knows
        about get_confidential_info (e.g., by guessing the name), the on_call_tool
        middleware blocks the call.
        """
        client, session_id, auth_header = await mcp_client(
            sub="alice", scopes=["public:read"]
        )
        data = await call_tool(client, session_id, auth_header, "get_confidential_info")

        # FastMCP wraps PermissionError into an MCP result with isError=true
        result = data.get("result", {})
        assert result.get("isError") is True

        # The error content should mention the scope requirement
        error_text = result["content"][0]["text"]
        assert "confidential:read" in error_text

    async def test_authorized_tool_call_returns_document_content(self, mcp_client):
        """Calling a tool with the correct scope should return the document content."""
        client, session_id, auth_header = await mcp_client(
            sub="alice", scopes=["public:read"]
        )
        data = await call_tool(client, session_id, auth_header, "get_public_info")

        result = data.get("result", {})
        assert result.get("isError") is not True

        # The content should contain the public document text
        content_text = result["content"][0]["text"]
        assert "Acme Corp" in content_text
        assert "Public Company Information" in content_text

    async def test_confidential_tool_call_with_correct_scope(self, mcp_client):
        """Calling get_confidential_info with 'confidential:read' scope should succeed."""
        client, session_id, auth_header = await mcp_client(
            sub="bob", scopes=["public:read", "confidential:read"]
        )
        data = await call_tool(client, session_id, auth_header, "get_confidential_info")

        result = data.get("result", {})
        assert result.get("isError") is not True

        content_text = result["content"][0]["text"]
        assert "Confidential Strategy Document" in content_text
