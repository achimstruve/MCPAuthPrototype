"""
Tool definitions and scope-based access mapping.

This module defines the mapping between MCP tool names and the authorization
scopes required to access them. This is the central registry for access control:

    TOOL_SCOPE_MAP = {
        "tool_name": "required_scope",
    }

The MCP server registers the actual tool functions (in server.py), but the
authorization middleware (added in Phase 2) imports TOOL_SCOPE_MAP from here
to decide whether a caller's token grants access to a given tool.

Why separate this from server.py?
- The auth middleware needs to know the scope requirements, but shouldn't need
  to import the entire server module (avoids circular imports).
- It's a clean separation of concerns: server.py = "what tools do",
  tools.py = "who can use them".
- Makes it easy to add new tools: just add the function in server.py and
  the scope mapping here.

Scope naming convention:
- Format: "<resource>:<action>" (e.g., "public:read", "confidential:read")
- This is a common pattern in OAuth2 and API authorization systems.
- Scopes are additive: a token with ["public:read", "confidential:read"]
  can access both tools.
"""

# Maps each tool name to the scope required to access it.
# A client's JWT token must include the listed scope to see or call the tool.
#
# Example token payloads and their tool access:
#   {"scope": ["public:read"]}                        -> get_public_info only
#   {"scope": ["public:read", "confidential:read"]}   -> both tools
#   {"scope": []}                                       -> no tools
TOOL_SCOPE_MAP: dict[str, str] = {
    "get_public_info": "public:read",
    "get_confidential_info": "confidential:read",
}
