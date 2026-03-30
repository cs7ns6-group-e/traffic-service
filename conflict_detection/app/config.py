from functools import lru_cache
from shared.config import Settings


class ConflictDetectionSettings(Settings):
    app_name: str = "conflict_detection"
    service_port: int = 8002


@lru_cache()
def get_settings() -> ConflictDetectionSettings:
    return ConflictDetectionSettings()
