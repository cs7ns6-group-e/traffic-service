from functools import lru_cache
from shared.config import Settings


class NotificationSettings(Settings):
    app_name: str = "notification"
    service_port: int = 8003


@lru_cache()
def get_settings() -> NotificationSettings:
    return NotificationSettings()
