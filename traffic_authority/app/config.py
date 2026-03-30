from functools import lru_cache
from shared.config import Settings


class TrafficAuthoritySettings(Settings):
    app_name: str = "traffic_authority"
    service_port: int = 8005


@lru_cache()
def get_settings() -> TrafficAuthoritySettings:
    return TrafficAuthoritySettings()
