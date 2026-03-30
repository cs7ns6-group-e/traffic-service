from shared.config import Settings, get_settings as _base_get_settings
from functools import lru_cache


class JourneyBookingSettings(Settings):
    app_name: str = "journey_booking"
    service_port: int = 8001
    conflict_service_url: str = "http://conflict_detection:8002"
    routing_service_url: str = "http://road_routing:8004"


@lru_cache()
def get_settings() -> JourneyBookingSettings:
    return JourneyBookingSettings()
