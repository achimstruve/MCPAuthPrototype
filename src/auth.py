"""
JWT token validation and scope extraction.

This module handles the Authentication (AuthN) layer:
- Extracts Bearer tokens from the HTTP Authorization header
- Validates JWT signature (proves the token was issued by us, not forged)
- Checks token expiration (limits blast radius of stolen tokens)
- Extracts scopes from token claims (used by middleware for Authorization)

Security concepts demonstrated:
- **Defense in depth**: Multiple validation layers (presence, format, signature, expiry, claims)
- **Fail closed**: Any validation failure rejects the request (no fallback to anonymous access)
- **Least privilege**: Scopes are extracted here but enforced in the middleware, so each
  token only gets access to what it explicitly claims

Token structure (JWT payload):
    {
        "sub": "user-or-agent-id",     # Who is making the request
        "scope": ["public:read"],       # What they're allowed to access
        "exp": 1738800000               # When this token expires (Unix timestamp)
    }

The token is signed with HS256 (HMAC-SHA256), a symmetric algorithm where the
same secret key is used to sign and verify. In production, you'd typically use
RS256 (asymmetric) where only the auth server has the private key.
"""

from dataclasses import dataclass

import jwt

from src.config import settings


class AuthError(Exception):
    """
    Raised when token validation fails for any reason.

    This is a single exception type for all auth failures (missing token,
    invalid signature, expired, malformed claims). We intentionally don't
    expose detailed error reasons to the client to avoid information leakage.
    The detailed reason is logged server-side for debugging.

    Attributes:
        message: Human-readable error description (logged server-side)
        status_code: HTTP status code to return (401 for auth failures)
    """

    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class TokenInfo:
    """
    Validated token information extracted from a JWT.

    This is a frozen (immutable) dataclass: once created, the fields can't
    be changed. This prevents accidental or malicious modification of the
    validated claims after extraction.

    Attributes:
        subject: The "sub" claim - identifies who/what made the request
                 (e.g., "alice@company.com" or "ci-agent-prod")
        scopes: List of authorized scopes (e.g., ["public:read", "confidential:read"])
    """

    subject: str
    scopes: list[str]


def validate_token(authorization_header: str | None) -> TokenInfo:
    """
    Validate a Bearer token from the Authorization header.

    This function implements the full authentication pipeline:
    1. Check that a header is present
    2. Extract the token from "Bearer <token>" format
    3. Decode and verify the JWT (signature + expiration)
    4. Extract and validate the claims (sub, scope)

    Args:
        authorization_header: The raw Authorization header value,
                              expected format: "Bearer <jwt-token>"

    Returns:
        TokenInfo with the validated subject and scopes

    Raises:
        AuthError: If any validation step fails
    """
    # Step 1: Check header presence
    # A missing Authorization header means the client didn't attempt authentication.
    if not authorization_header:
        raise AuthError("Missing Authorization header")

    # Step 2: Extract the token from "Bearer <token>" format
    # The "Bearer" scheme is defined in RFC 6750 and is the standard way to
    # transmit tokens in HTTP. We do a case-insensitive check on the scheme.
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Invalid Authorization header format, expected 'Bearer <token>'")

    token = parts[1]

    # Step 3: Decode and verify the JWT
    # PyJWT does several things here:
    # - Parses the JWT structure (header.payload.signature)
    # - Verifies the signature using our secret key (proves authenticity)
    # - Checks the "exp" claim against the current time (rejects expired tokens)
    #
    # If any of these fail, PyJWT raises a specific exception that we catch below.
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            # PyJWT verifies "exp" by default when the claim is present.
            # We require it via options to reject tokens without expiration.
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError as e:
        # Catches all other JWT errors: invalid signature, malformed token,
        # missing required claims, etc. We log the specific error server-side
        # but return a generic message to the client.
        raise AuthError(f"Invalid token: {e}")

    # Step 4: Extract and validate claims
    subject = payload.get("sub", "")

    # The "scope" claim should be a list of strings like ["public:read"].
    # We validate the type to prevent injection attacks where someone might
    # set scope to a string or other unexpected type.
    scopes_claim = payload.get("scope", [])

    if not isinstance(scopes_claim, list):
        raise AuthError("Invalid scope claim: must be a list")

    # Validate that all scope entries are strings
    if not all(isinstance(s, str) for s in scopes_claim):
        raise AuthError("Invalid scope claim: all entries must be strings")

    return TokenInfo(subject=subject, scopes=scopes_claim)
