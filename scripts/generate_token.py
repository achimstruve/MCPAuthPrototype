"""
CLI utility to generate JWT tokens for testing the MCP server.

In a real production system, tokens would be issued by an identity provider
(e.g., Auth0, Keycloak, Google IAM) or an internal token service. For our
prototype, this script acts as the "auth server" - it mints tokens with
configurable claims that the MCP server will validate.

Usage examples:

    # Token with public access only (default secret)
    uv run python -m scripts.generate_token --sub alice --scope public:read

    # Token with full access
    uv run python -m scripts.generate_token --sub alice --scope public:read confidential:read

    # Token with custom expiration (2 hours)
    uv run python -m scripts.generate_token --sub ci-agent --scope public:read --exp-hours 2

    # Token with custom secret (must match MCP_JWT_SECRET_KEY on the server)
    uv run python -m scripts.generate_token --sub alice --scope public:read --secret my-prod-secret

    # Expired token (for testing rejection)
    uv run python -m scripts.generate_token --sub alice --scope public:read --exp-hours -1

The generated token can be used with curl:

    curl -X POST http://localhost:8080/mcp \\
      -H "Content-Type: application/json" \\
      -H "Authorization: Bearer <token>" \\
      -d '{"jsonrpc":"2.0","id":1,"method":"initialize",...}'

Or with Claude Code:

    claude mcp add --transport http company-mcp http://localhost:8080/mcp \\
      --header "Authorization: Bearer <token>"
"""

import argparse
import datetime

import jwt


def generate_token(
    subject: str,
    scopes: list[str],
    secret: str,
    algorithm: str = "HS256",
    exp_hours: float = 8.0,
) -> str:
    """
    Generate a signed JWT token with the given claims.

    Args:
        subject: The "sub" claim - identifies who/what this token is for
        scopes: List of authorized scopes (e.g., ["public:read"])
        secret: The signing key (must match the server's MCP_JWT_SECRET_KEY)
        algorithm: JWT signing algorithm (default: HS256)
        exp_hours: Hours until expiration (negative = already expired)

    Returns:
        The encoded JWT token string
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    expiration = now + datetime.timedelta(hours=exp_hours)

    payload = {
        "sub": subject,
        "scope": scopes,
        "iat": now,  # Issued at: when the token was created
        "exp": expiration,  # Expiration: when the token becomes invalid
    }

    return jwt.encode(payload, secret, algorithm=algorithm)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate JWT tokens for the MCP server prototype.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Public access only:
    %(prog)s --sub alice --scope public:read

  Full access:
    %(prog)s --sub alice --scope public:read confidential:read

  Expired token (for testing):
    %(prog)s --sub alice --scope public:read --exp-hours -1

  Custom secret:
    %(prog)s --sub alice --scope public:read --secret my-secret
        """,
    )

    parser.add_argument(
        "--sub",
        required=True,
        help="Subject claim: who/what this token identifies (e.g., 'alice', 'ci-agent')",
    )
    parser.add_argument(
        "--scope",
        nargs="+",
        default=[],
        help="Space-separated list of scopes (e.g., public:read confidential:read)",
    )
    parser.add_argument(
        "--secret",
        default="dev-secret-change-me",
        help="JWT signing secret (must match server's MCP_JWT_SECRET_KEY)",
    )
    parser.add_argument(
        "--algorithm",
        default="HS256",
        help="JWT signing algorithm (default: HS256)",
    )
    parser.add_argument(
        "--exp-hours",
        type=float,
        default=8.0,
        help="Hours until token expires (negative = already expired, default: 8)",
    )

    args = parser.parse_args()

    token = generate_token(
        subject=args.sub,
        scopes=args.scope,
        secret=args.secret,
        algorithm=args.algorithm,
        exp_hours=args.exp_hours,
    )

    # Print token info and the token itself
    exp_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=args.exp_hours
    )

    print(f"Subject:    {args.sub}")
    print(f"Scopes:     {args.scope}")
    print(f"Expires:    {exp_time.isoformat()}")
    print(f"Algorithm:  {args.algorithm}")
    print()
    print(f"Token: {token}")

    # Also print a ready-to-use curl command
    print()
    print("Usage with curl (initialize MCP session):")
    print('  curl -X POST http://localhost:8080/mcp \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -H "Accept: application/json, text/event-stream" \\')
    print(f'    -H "Authorization: Bearer {token}" \\')
    print(
        '    -d \'{"jsonrpc":"2.0","id":1,"method":"initialize",'
        '"params":{"protocolVersion":"2025-03-26","capabilities":{},'
        '"clientInfo":{"name":"test","version":"1.0"}}}\''
    )


if __name__ == "__main__":
    main()
