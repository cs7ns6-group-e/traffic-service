import json
import logging
import threading
import time
from collections.abc import Callable
from typing import TypedDict

import pika
import pika.exceptions

logger = logging.getLogger(__name__)


class BookingEvent(TypedDict):
    journey_id: str
    driver_id: str
    status: str
    region: str
    is_cross_region: bool


class EventPublisher:
    """Publishes events to RabbitMQ with retry logic."""

    def __init__(self, rabbitmq_url: str) -> None:
        self._url = rabbitmq_url
        self._connection: pika.BlockingConnection | None = None
        self._channel = None

    def connect(self) -> None:
        params = pika.URLParameters(self._url)
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue="booking_events", durable=True)

    def publish(self, queue: str, event: dict) -> None:
        body = json.dumps(event).encode()
        properties = pika.BasicProperties(delivery_mode=2)
        for attempt in range(3):
            try:
                if self._channel is None or self._connection is None or self._connection.is_closed:
                    self.connect()
                self._channel.basic_publish(
                    exchange="",
                    routing_key=queue,
                    body=body,
                    properties=properties,
                )
                return
            except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError) as exc:
                logger.warning("RabbitMQ publish attempt %d failed: %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(1)
                else:
                    raise

    def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            self._connection.close()


class EventConsumer:
    """Base class for RabbitMQ consumers."""

    def __init__(self, rabbitmq_url: str, queue: str) -> None:
        self._url = rabbitmq_url
        self._queue = queue
        self._connection: pika.BlockingConnection | None = None
        self._channel = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self, callback: Callable) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(callback,),
            daemon=True,
        )
        self._thread.start()

    def _run(self, callback: Callable) -> None:
        while not self._stop_event.is_set():
            try:
                params = pika.URLParameters(self._url)
                self._connection = pika.BlockingConnection(params)
                self._channel = self._connection.channel()
                self._channel.queue_declare(queue=self._queue, durable=True)
                self._channel.basic_qos(prefetch_count=1)

                def on_message(ch, method, properties, body):
                    try:
                        callback(ch, method, properties, body)
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    except Exception as exc:
                        logger.error("Message processing failed: %s", exc)
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

                self._channel.basic_consume(queue=self._queue, on_message_callback=on_message)
                self._channel.start_consuming()
            except pika.exceptions.AMQPConnectionError as exc:
                logger.warning("RabbitMQ consumer connection failed: %s. Retrying in 5s...", exc)
                time.sleep(5)
            except Exception as exc:
                logger.error("Unexpected consumer error: %s. Retrying in 5s...", exc)
                time.sleep(5)

    def stop(self) -> None:
        self._stop_event.set()
        if self._channel:
            try:
                self._channel.stop_consuming()
            except Exception:
                pass
        if self._connection and not self._connection.is_closed:
            self._connection.close()
