"""
Unit tests for JWT token validation (src/auth.py).

These tests exercise validate_token() directly, verifying each step of the
authentication pipeline:

1. Header presence check
2. Bearer scheme extraction
3. JWT signature verification
4. Expiration check
5. Claims validation (sub, scope)

This is "shift-left security testing": catching auth bugs early in the
development cycle rather than discovering them in production.

Each test targets a specific failure mode, making it easy to diagnose
which validation step broke if a test fails.
"""

import pytest

from src.auth import AuthError, validate_token


class TestValidateToken:
    """Tests for the validate_token() function."""

    # ----- Happy path -----

    def test_valid_token_decodes_correctly(self, make_auth_header):
        """A properly signed token with valid claims should decode successfully."""
        header = make_auth_header(sub="alice", scopes=["public:read", "confidential:read"])

        result = validate_token(header)

        assert result.subject == "alice"
        assert result.scopes == ["public:read", "confidential:read"]

    def test_valid_token_single_scope(self, make_auth_header):
        """Token with a single scope should work fine."""
        header = make_auth_header(sub="bob", scopes=["public:read"])

        result = validate_token(header)

        assert result.subject == "bob"
        assert result.scopes == ["public:read"]

    # ----- Missing / malformed Authorization header -----

    def test_missing_header_raises_auth_error(self):
        """None header (no Authorization header sent) should be rejected."""
        with pytest.raises(AuthError, match="Missing Authorization header"):
            validate_token(None)

    def test_empty_header_raises_auth_error(self):
        """Empty string header should be rejected."""
        with pytest.raises(AuthError, match="Missing Authorization header"):
            validate_token("")

    def test_non_bearer_scheme_raises_auth_error(self, make_token):
        """Using 'Basic' or other schemes instead of 'Bearer' should be rejected."""
        token = make_token(sub="alice", scopes=["public:read"])

        with pytest.raises(AuthError, match="Invalid Authorization header format"):
            validate_token(f"Basic {token}")

    def test_missing_token_after_bearer_raises_auth_error(self):
        """'Bearer' without a token value should be rejected."""
        with pytest.raises(AuthError, match="Invalid Authorization header format"):
            validate_token("Bearer")

    # ----- JWT signature and structure -----

    def test_malformed_token_raises_auth_error(self):
        """A string that isn't valid JWT structure should be rejected."""
        with pytest.raises(AuthError, match="Invalid token"):
            validate_token("Bearer not-a-jwt-token")

    def test_wrong_signing_key_raises_auth_error(self, make_token):
        """
        A token signed with a different secret should be rejected.

        This is the core security check: even if an attacker crafts a valid
        JWT structure with the right claims, they can't forge the signature
        without knowing the secret key.
        """
        # Sign with a different secret than what the server uses
        token = make_token(sub="attacker", scopes=["confidential:read"], secret="wrong-secret")

        with pytest.raises(AuthError, match="Invalid token"):
            validate_token(f"Bearer {token}")

    # ----- Expiration -----

    def test_expired_token_raises_auth_error(self, make_token):
        """
        An expired token should be rejected even if the signature is valid.

        This limits the blast radius of stolen tokens: even if an attacker
        gets a valid token, it becomes useless after expiration.
        """
        # Create a token that expired 1 hour ago
        token = make_token(sub="alice", scopes=["public:read"], exp_hours=-1)

        with pytest.raises(AuthError, match="Token has expired"):
            validate_token(f"Bearer {token}")

    def test_token_without_exp_claim_raises_auth_error(self, make_token):
        """
        A token without an expiration claim should be rejected.

        We require 'exp' via PyJWT options to prevent indefinitely-valid tokens.
        All tokens must have a finite lifetime.
        """
        token = make_token(sub="alice", scopes=["public:read"], include_exp=False)

        with pytest.raises(AuthError, match="Invalid token"):
            validate_token(f"Bearer {token}")

    # ----- Sub claim -----

    def test_token_without_sub_claim_raises_auth_error(self, make_token):
        """
        A token without a 'sub' (subject) claim should be rejected.

        We require 'sub' to identify who is making the request for audit logging.
        """
        token = make_token(scopes=["public:read"], include_sub=False)

        with pytest.raises(AuthError, match="Invalid token"):
            validate_token(f"Bearer {token}")

    # ----- Scope claim validation -----

    def test_missing_scope_defaults_to_empty_list(self, make_token):
        """
        A token without a 'scope' claim should default to an empty scope list.

        This means the user is authenticated but has no authorization to any tools.
        This is safer than failing: the user exists but can't do anything.
        """
        # Create a token with no scope claim at all (scopes=None omits the claim)
        token = make_token(sub="alice", scopes=None)

        result = validate_token(f"Bearer {token}")

        assert result.subject == "alice"
        assert result.scopes == []

    def test_non_list_scope_raises_auth_error(self, make_token):
        """
        A scope claim that isn't a list should be rejected.

        This prevents type confusion attacks where someone might set scope
        to a string like "public:read confidential:read" hoping it would
        be split incorrectly.
        """
        # Inject a string scope claim via extra_claims
        token = make_token(
            sub="alice",
            scopes=None,  # Don't set scope normally
            extra_claims={"scope": "public:read"},  # Set it as a string instead
        )

        with pytest.raises(AuthError, match="Invalid scope claim: must be a list"):
            validate_token(f"Bearer {token}")

    def test_scope_with_non_string_entries_raises_auth_error(self, make_token):
        """Scope list entries must all be strings."""
        token = make_token(
            sub="alice",
            scopes=None,
            extra_claims={"scope": ["public:read", 123]},  # 123 is not a string
        )

        with pytest.raises(AuthError, match="Invalid scope claim: all entries must be strings"):
            validate_token(f"Bearer {token}")

    def test_empty_scope_list_returns_no_scopes(self, make_token):
        """An explicit empty scope list should result in no authorized scopes."""
        token = make_token(sub="alice", scopes=[])

        result = validate_token(f"Bearer {token}")

        assert result.subject == "alice"
        assert result.scopes == []

    # ----- Case sensitivity -----

    def test_bearer_scheme_case_insensitive(self, make_token):
        """The 'Bearer' scheme should be matched case-insensitively per RFC 6750."""
        token = make_token(sub="alice", scopes=["public:read"])

        # Lowercase 'bearer' should work too
        result = validate_token(f"bearer {token}")

        assert result.subject == "alice"
        assert result.scopes == ["public:read"]
