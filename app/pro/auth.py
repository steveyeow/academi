from __future__ import annotations

import os
import logging

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..core.db import get_or_create_user

log = logging.getLogger(__name__)

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
JWT_ALGORITHMS = ["HS256"]

PUBLIC_PATHS = {
    "/", "/api/health",
    "/api/pro/config",
    "/api/pro/webhook",
    "/api/topics",
    "/api/agents",
    "/api/votes",
    "/api/minds",
    "/favicon.ico",
}
PUBLIC_PREFIXES = ("/static/",)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # Allow GET requests to read-only API endpoints without auth
        if request.method == "GET" and path.startswith("/api/"):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"detail": "Authentication required", "code": "auth_required"},
                status_code=401,
            )

        token = auth_header[7:]
        try:
            header = jwt.get_unverified_header(token)
            token_alg = header.get("alg", "unknown")
            if token_alg not in JWT_ALGORITHMS:
                log.warning(
                    "JWT alg mismatch: token uses %s, allowed %s. "
                    "Check SUPABASE_JWT_SECRET matches your Supabase project.",
                    token_alg, JWT_ALGORITHMS,
                )
            payload = jwt.decode(
                token, SUPABASE_JWT_SECRET,
                algorithms=JWT_ALGORITHMS,
                audience="authenticated",
            )
        except jwt.ExpiredSignatureError:
            return JSONResponse({"detail": "Token expired", "code": "token_expired"}, status_code=401)
        except jwt.InvalidTokenError as e:
            log.warning("JWT validation failed: %s", e)
            return JSONResponse({"detail": "Invalid token", "code": "invalid_token"}, status_code=401)

        user_id = payload.get("sub", "")
        email = payload.get("email", "")

        if not user_id:
            return JSONResponse({"detail": "Invalid token claims"}, status_code=401)

        user = get_or_create_user(user_id, email)

        request.state.user_id = user_id
        request.state.email = email
        request.state.tier = user.get("tier", "free") if user else "free"

        return await call_next(request)
