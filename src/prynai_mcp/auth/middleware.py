"""
BearerAuthMiddleware
- Enforces OAuth2 Bearer auth on /mcp only (health endpoints stay open).
- Uses validate_bearer_header() to verify Microsoft Entra ID JWT.
- On success, attaches claims at request.state.user_claims.
- On failure, returns 401 with a proper WWW-Authenticate header.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from ..config import settings
from .azure_oauth import validate_bearer_header, AuthError


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Short-circuit if auth not required (useful for dev/local)
        if not settings.AUTH_REQUIRED:
            return await call_next(request)

        path = request.url.path or "/"

        # Always allow health checks
        if path in ("/healthz", "/livez"):
            return await call_next(request)

        # Protect Streamable HTTP endpoint
        if path.startswith("/mcp"):
            auth_header = request.headers.get("Authorization")
            try:
                claims = await validate_bearer_header(auth_header)
            except AuthError as e:
                # Return the embedded 401 response without crashing the app
                return e.response

            # Make claims available to downstream handlers/tools if needed
            request.state.user_claims = claims

        # Proceed to the next app/middleware (MCP SHTTP app)
        return await call_next(request)
