import json
import logging

from shared.messaging import BookingEvent, EventConsumer

from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class BookingEventConsumer:
    def __init__(self, settings) -> None:
        self._consumer = EventConsumer(settings.rabbitmq_url, "booking_events")
        self._service = NotificationService(settings)

    def start_background(self) -> None:
        self._consumer.start(self._on_message)
        logger.info("Booking event consumer started in background thread")

    def stop(self) -> None:
        self._consumer.stop()

    def _on_message(self, ch, method, properties, body) -> None:
        import asyncio
        try:
            event: BookingEvent = json.loads(body.decode())
            logger.info("Received booking event: %s", event.get("journey_id"))
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._service.send(event))
            finally:
                loop.close()
            logger.info("Notification sent for journey %s", event.get("journey_id"))
        except Exception as exc:
            logger.error("Failed to process booking event: %s", exc)
            raise
