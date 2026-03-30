from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class TrafficBookException(Exception):
    """Base exception for all TrafficBook errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class JourneyNotFoundException(TrafficBookException):
    """Raised when a journey ID does not exist."""

    def __init__(self, message: str = "Journey not found") -> None:
        super().__init__(message, "JOURNEY_NOT_FOUND")


class JourneyConflictException(TrafficBookException):
    """Raised when a journey slot is already taken."""

    def __init__(self, message: str = "Journey slot conflict") -> None:
        super().__init__(message, "JOURNEY_CONFLICT")


class UnauthorizedException(TrafficBookException):
    """Raised when JWT token is invalid or expired."""

    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message, "UNAUTHORIZED")


class ForbiddenException(TrafficBookException):
    """Raised when user role is insufficient."""

    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, "FORBIDDEN")


class RouteNotFoundException(TrafficBookException):
    """Raised when OSRM cannot find a route."""

    def __init__(self, message: str = "Route not found") -> None:
        super().__init__(message, "ROUTE_NOT_FOUND")


class NotificationFailedException(TrafficBookException):
    """Raised when email and Telegram both fail."""

    def __init__(self, message: str = "Notification failed") -> None:
        super().__init__(message, "NOTIFICATION_FAILED")


class RegionUnavailableException(TrafficBookException):
    """Raised when cross-region communication fails."""

    def __init__(self, message: str = "Region unavailable") -> None:
        super().__init__(message, "REGION_UNAVAILABLE")


async def journey_not_found_handler(request: Request, exc: JourneyNotFoundException) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": exc.code, "message": exc.message},
    )


async def conflict_handler(request: Request, exc: JourneyConflictException) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"error": exc.code, "message": exc.message},
    )


async def auth_handler(request: Request, exc: UnauthorizedException) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": exc.code, "message": exc.message},
    )


async def forbidden_handler(request: Request, exc: ForbiddenException) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": exc.code, "message": exc.message},
    )


async def route_not_found_handler(request: Request, exc: RouteNotFoundException) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": exc.code, "message": exc.message},
    )


async def notification_failed_handler(request: Request, exc: NotificationFailedException) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"error": exc.code, "message": exc.message},
    )


async def region_unavailable_handler(request: Request, exc: RegionUnavailableException) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": exc.code, "message": exc.message},
    )


async def generic_trafficbook_handler(request: Request, exc: TrafficBookException) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": exc.code, "message": exc.message},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(JourneyNotFoundException, journey_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(JourneyConflictException, conflict_handler)  # type: ignore[arg-type]
    app.add_exception_handler(UnauthorizedException, auth_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ForbiddenException, forbidden_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RouteNotFoundException, route_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(NotificationFailedException, notification_failed_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RegionUnavailableException, region_unavailable_handler)  # type: ignore[arg-type]
    app.add_exception_handler(TrafficBookException, generic_trafficbook_handler)  # type: ignore[arg-type]
