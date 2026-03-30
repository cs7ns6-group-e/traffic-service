from functools import lru_cache
from shared.config import Settings


class RoadRoutingSettings(Settings):
    app_name: str = "road_routing"
    service_port: int = 8004


@lru_cache()
def get_settings() -> RoadRoutingSettings:
    return RoadRoutingSettings()
