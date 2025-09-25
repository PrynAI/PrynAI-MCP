"""
Azure Entra ID OAuth2 / JWT validation.

- Validates 'Authorization: Bearer <JWT>' on incoming requests.
- Verifies signature via tenant JWKS (RS256).
- Enforces issuer and audience.
- Optionally enforces scopes ('scp') and/or app roles ('roles').
- On failure, raises AuthError carrying a JSONResponse(401).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import jwt  # PyJWT
from jwt import PyJWKClient, InvalidTokenError, InvalidSignatureError, InvalidKeyError
from starlette.responses import JSONResponse

from ..config import settings


class AuthError(Exception):
    """
    Exception that carries an HTTP 401 response.
    Middleware catches this and returns e.response.
    """

    def __init__(self, response: JSONResponse):
        self.response = response
        # Store body for logging/debug if desired
        super().__init__(response.body)


# ---- helpers ---------------------------------------------------------


def _audiences() -> List[str]:
    """Allowed token audiences."""
    if not settings.ENTRA_AUDIENCES:
        return []
    return [a.strip() for a in settings.ENTRA_AUDIENCES.split(",") if a.strip()]


def _required_scopes() -> List[str]:
    """At least one of these scopes ('scp' claim) must be present if configured."""
    if not settings.ENTRA_REQUIRED_SCOPES:
        return []
    return [s.strip() for s in settings.ENTRA_REQUIRED_SCOPES.split(",") if s.strip()]


def _required_roles() -> List[str]:
    """At least one of these app roles ('roles' claim) must be present if configured."""
    if not settings.ENTRA_REQUIRED_APP_ROLES:
        return []
    return [r.strip() for r in settings.ENTRA_REQUIRED_APP_ROLES.split(",") if r.strip()]


_jwk_client: Optional[PyJWKClient] = None  # cached per-process


def _get_jwk_client() -> PyJWKClient:
    """Create or reuse a JWKS client for the tenant."""
    global _jwk_client
    if _jwk_client is None:
        if not settings.jwks_url:
            raise _unauthorized("config_error", "JWKS URL not configured. Set ENTRA_TENANT_ID.")
        # PyJWKClient caches keys and uses standard HTTPS fetch internally
        _jwk_client = PyJWKClient(settings.jwks_url)
    return _jwk_client


def _unauthorized(error: str, desc: str) -> AuthError:
    """Build a 401 AuthError with WWW-Authenticate header."""
    return AuthError(
        JSONResponse(
            {"error": error, "error_description": desc},
            status_code=401,
            headers={"WWW-Authenticate": f'Bearer error="{error}", error_description="{desc}"'},
        )
    )


# ---- main entry ------------------------------------------------------


async def validate_bearer_header(authorization: str | None) -> Dict[str, Any]:
    """
    Parse and validate Authorization header.
    Returns decoded JWT claims on success.
    Raises AuthError(401) on any failure.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized("missing_or_malformed", "Authorization: Bearer <token> required")

    token = authorization[7:].strip()
    if not token:
        raise _unauthorized("missing_token", "Empty bearer token")

    # Resolve signing key from JWKS using token's 'kid'
    try:
        jwk_client = _get_jwk_client()
        signing_key = jwk_client.get_signing_key_from_jwt(token)
    except (InvalidKeyError, InvalidSignatureError, InvalidTokenError) as e:
        raise _unauthorized("invalid_signature", f"Signature validation failed: {e}")
    except AuthError:
        # rethrow config_error
        raise
    except Exception as e:
        raise _unauthorized("jwks_error", f"Unable to resolve signing key: {e}")

    issuer = settings.issuer  # None disables issuer check in PyJWT
    audiences = _audiences()  # [] disables audience check

    # Validate signature, issuer, audience, exp
    try:
        claims = jwt.decode(
            token,
            signing_key.key,            # public key
            algorithms=["RS256"],
            audience=audiences or None, # PyJWT skips aud if None
            issuer=issuer,              # PyJWT skips iss if None
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": bool(audiences),
                "verify_iss": bool(issuer),
            },
        )
    except InvalidTokenError as e:
        raise _unauthorized("invalid_token", f"Token validation failed: {e}")

    # Optional scope/role enforcement
    need_scopes = set(_required_scopes())
    if need_scopes:
        granted_scopes = set((claims.get("scp") or "").split())  # space-separated string
        if not need_scopes.intersection(granted_scopes):
            raise _unauthorized("insufficient_scope", f"Require one of scopes: {sorted(need_scopes)}")

    need_roles = set(_required_roles())
    if need_roles:
        granted_roles = set(claims.get("roles") or [])
        if not need_roles.intersection(granted_roles):
            raise _unauthorized("insufficient_role", f"Require one of app roles: {sorted(need_roles)}")

    return claims