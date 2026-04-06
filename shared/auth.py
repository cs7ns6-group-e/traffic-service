"""Shared authentication module — Simple JWT (replaces Keycloak)."""

import os
from typing import Any

import jwt
from fastapi import Depends, Header
from pydantic import BaseModel

from shared.exceptions import ForbiddenException, UnauthorizedException

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "changeme")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")


# ---------------------------------------------------------------------------
# CurrentUser model
# ---------------------------------------------------------------------------
class CurrentUser(BaseModel):
    id: str
    email: str
    name: str
    role: str = "driver"
    roles: list[str] = []
    vehicle_type: str = "STANDARD"
    region: str = "EU"

    def model_post_init(self, __context: Any) -> None:
        # Backward compatibility: if roles is provided but role is default, use first role
        if self.roles and self.role == "driver":
            object.__setattr__(self, "role", self.roles[0])
        # If role is set but roles is empty, populate roles from role
        if not self.roles and self.role:
            object.__setattr__(self, "roles", [self.role])

    def has_role(self, role: str) -> bool:
        return role == self.role or role in self.roles

    def is_driver(self) -> bool:
        return self.has_role("driver")

    def is_authority(self) -> bool:
        return self.has_role("traffic_authority")

    def is_admin(self) -> bool:
        return self.has_role("admin")


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------
async def verify_token(authorization: str = Header(...)) -> dict[str, Any]:
    """Decode and validate a Bearer JWT token. Raises 401 on invalid/expired."""
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException("Invalid authorization header format")
    token = authorization.removeprefix("Bearer ")
    try:
        payload: dict[str, Any] = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Token has expired")
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedException(f"Invalid token: {exc}")


# ---------------------------------------------------------------------------
# Current user extraction
# ---------------------------------------------------------------------------
async def get_current_user(payload: dict[str, Any] = Depends(verify_token)) -> CurrentUser:
    """Extract CurrentUser from the decoded JWT payload."""
    return CurrentUser(
        id=payload.get("sub", ""),
        email=payload.get("email", ""),
        name=payload.get("name", ""),
        role=payload.get("role", "driver"),
        vehicle_type=payload.get("vehicle_type", "STANDARD"),
        region=payload.get("region", "EU"),
    )


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------
def require_role(*roles: str):
    """FastAPI dependency that enforces the user has one of the given roles.
    Raises 403 on insufficient role."""

    async def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise ForbiddenException(
                f"Required role(s): {', '.join(roles)}. User role: {current_user.role}"
            )
        return current_user

    return role_checker


# ---------------------------------------------------------------------------
# Emergency vehicle helper
# ---------------------------------------------------------------------------
def is_emergency(user: CurrentUser) -> bool:
    """Return True if the user's vehicle type is EMERGENCY."""
    return user.vehicle_type == "EMERGENCY"
