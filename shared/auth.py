import time
from functools import lru_cache
from typing import Any

import httpx
from fastapi import Depends, Header
from jose import JWTError, jwt
from jose.backends import RSAKey
from pydantic import BaseModel

from shared.config import get_settings
from shared.exceptions import ForbiddenException, UnauthorizedException


class CurrentUser(BaseModel):
    id: str
    email: str
    name: str
    roles: list[str]
    region: str = "EU"

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def is_driver(self) -> bool:
        return self.has_role("driver")

    def is_authority(self) -> bool:
        return self.has_role("traffic_authority")

    def is_admin(self) -> bool:
        return self.has_role("admin")


_jwks_cache: dict[str, Any] = {}
_jwks_cache_time: float = 0.0
_JWKS_TTL = 600  # 10 minutes


async def get_public_key(token_header: dict[str, Any]) -> Any:
    global _jwks_cache, _jwks_cache_time
    settings = get_settings()
    now = time.time()
    if _jwks_cache and (now - _jwks_cache_time) < _JWKS_TTL:
        jwks = _jwks_cache
    else:
        jwks_url = (
            f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(jwks_url, timeout=10.0)
            resp.raise_for_status()
        jwks = resp.json()
        _jwks_cache = jwks
        _jwks_cache_time = now

    kid = token_header.get("kid")
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAKey(key, algorithm="RS256")
    raise UnauthorizedException("Public key not found for token kid")


async def verify_token(authorization: str = Header(...)) -> dict[str, Any]:
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException("Invalid authorization header format")
    token = authorization.removeprefix("Bearer ")
    try:
        header = jwt.get_unverified_header(token)
        public_key = await get_public_key(header)
        settings = get_settings()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
        )
        return payload
    except JWTError as exc:
        raise UnauthorizedException(f"Invalid or expired token: {exc}") from exc


async def get_current_user(payload: dict[str, Any] = Depends(verify_token)) -> CurrentUser:
    realm_access = payload.get("realm_access", {})
    roles: list[str] = realm_access.get("roles", [])
    return CurrentUser(
        id=payload.get("sub", ""),
        email=payload.get("email", ""),
        name=payload.get("name", payload.get("preferred_username", "")),
        roles=roles,
        region=payload.get("region", "EU"),
    )


def require_role(*roles: str):
    async def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(current_user.has_role(r) for r in roles):
            raise ForbiddenException(
                f"Required role(s): {', '.join(roles)}. User roles: {', '.join(current_user.roles)}"
            )
        return current_user

    return role_checker
