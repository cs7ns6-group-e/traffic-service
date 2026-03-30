from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.exceptions import NotificationFailedException
from shared.messaging import BookingEvent
from app.services.notification_service import NotificationService
from app.tests.conftest import *  # noqa: F401, F403


def make_event(**kwargs) -> BookingEvent:
    base: BookingEvent = {
        "journey_id": "j-1",
        "driver_id": "d-1",
        "status": "CONFIRMED",
        "region": "EU",
        "is_cross_region": False,
    }
    base.update(kwargs)
    return base


@pytest.mark.asyncio
async def test_notification_email_fails_telegram_succeeds(mock_settings):
    service = NotificationService(mock_settings)

    async def fail_email(*args, **kwargs):
        raise RuntimeError("SMTP down")

    async def ok_telegram(*args, **kwargs):
        pass

    service.send_email = fail_email
    service.send_telegram = ok_telegram

    await service.send(make_event())  # should NOT raise


@pytest.mark.asyncio
async def test_notification_both_fail_raises(mock_settings):
    service = NotificationService(mock_settings)

    async def fail(*args, **kwargs):
        raise RuntimeError("all down")

    service.send_email = fail
    service.send_telegram = fail

    with pytest.raises(NotificationFailedException):
        await service.send(make_event())


@pytest.mark.asyncio
async def test_notification_both_succeed(mock_settings):
    service = NotificationService(mock_settings)

    service.send_email = AsyncMock()
    service.send_telegram = AsyncMock()

    await service.send(make_event())

    service.send_email.assert_called_once()
    service.send_telegram.assert_called_once()
