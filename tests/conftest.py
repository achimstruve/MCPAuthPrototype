"""
Shared test fixtures for the MCP server test suite.

Pytest fixtures are reusable setup functions that tests can request by name.
They run before each test (or once per session, depending on scope) and provide
the test with preconfigured objects.

Key fixtures:
- make_token: A factory function to generate JWT tokens with any claims
- mcp_app: The FastMCP ASGI app for integration testing (no real server needed)
- async_client: An httpx.AsyncClient wired to the ASGI app

Testing approach:
- test_auth.py: Unit tests for validate_token() - tests the auth logic in isolation.
  Uses make_token() to create tokens with specific claims and passes the resulting
  "Bearer <token>" string directly to validate_token().

- test_tools.py: Integration tests for the full MCP server - tests that the middleware
  correctly filters tools and blocks unauthorized calls. Uses async_client to send
  real HTTP requests to the ASGI app (in-memory, no network needed).
"""

import datetime

import jwt
import pytest

from src.config import settings

# ---------------------------------------------------------------------------
# Known test secret
# ---------------------------------------------------------------------------
# This must match settings.jwt_secret_key so that tokens generated in tests
# are accepted by validate_token(). The default is "dev-secret-change-me".
TEST_SECRET = settings.jwt_secret_key
TEST_ALGORITHM = settings.jwt_algorithm


# ---------------------------------------------------------------------------
# Token factory fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def make_token():
    """
    Factory fixture to generate JWT tokens for testing.

    Returns a callable that creates tokens with configurable claims.
    This is a "factory fixture" pattern: instead of returning a fixed value,
    it returns a function that tests can call with different parameters.

    Usage in tests:
        def test_something(make_token):
            token = make_token(sub="alice", scopes=["public:read"])
            # token is a raw JWT string (not "Bearer ..." prefixed)
    """

    def _make_token(
        sub: str = "test-user",
        scopes: list[str] | None = None,
        secret: str = TEST_SECRET,
        algorithm: str = TEST_ALGORITHM,
        exp_hours: float = 1.0,
        extra_claims: dict | None = None,
        include_exp: bool = True,
        include_sub: bool = True,
    ) -> str:
        """
        Generate a signed JWT token with the given claims.

        Args:
            sub: Subject claim (who the token identifies)
            scopes: List of scopes (None means omit the claim entirely)
            secret: Signing key
            algorithm: JWT algorithm
            exp_hours: Hours until expiration (negative = already expired)
            extra_claims: Additional claims to include in the payload
            include_exp: Whether to include the exp claim
            include_sub: Whether to include the sub claim
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        payload: dict = {}

        if include_sub:
            payload["sub"] = sub

        if scopes is not None:
            payload["scope"] = scopes

        if include_exp:
            payload["exp"] = now + datetime.timedelta(hours=exp_hours)

        payload["iat"] = now

        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(payload, secret, algorithm=algorithm)

    return _make_token


# ---------------------------------------------------------------------------
# Authorization header helper fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def make_auth_header(make_token):
    """
    Convenience fixture that returns a full "Bearer <token>" string.

    Usage in tests:
        def test_something(make_auth_header):
            header = make_auth_header(sub="alice", scopes=["public:read"])
            # header is "Bearer eyJhbGci..."
    """

    def _make_auth_header(**kwargs) -> str:
        return f"Bearer {make_token(**kwargs)}"

    return _make_auth_header
