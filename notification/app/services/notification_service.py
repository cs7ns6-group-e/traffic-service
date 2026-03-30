import asyncio
import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from shared.exceptions import NotificationFailedException
from shared.messaging import BookingEvent

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)


class NotificationService:
    def __init__(self, settings) -> None:
        self._settings = settings

    async def send(self, event: BookingEvent) -> None:
        subject = f"TrafficBook: Journey {event['status']} - {event['journey_id']}"
        body = (
            f"Journey {event['journey_id']} has been {event['status']}.\n"
            f"Driver: {event['driver_id']}\n"
            f"Region: {event['region']}\n"
            f"Cross-region: {event['is_cross_region']}"
        )
        telegram_msg = (
            f"*TrafficBook Alert*\n"
            f"Journey `{event['journey_id']}` is now *{event['status']}*\n"
            f"Driver: {event['driver_id']} | Region: {event['region']}"
        )

        email_ok = False
        telegram_ok = False

        results = await asyncio.gather(
            self.send_email(self._settings.smtp_user, subject, body),
            self.send_telegram(telegram_msg),
            return_exceptions=True,
        )

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                channel = "email" if i == 0 else "telegram"
                logger.error("Notification channel %s failed: %s", channel, result)
            else:
                if i == 0:
                    email_ok = True
                else:
                    telegram_ok = True

        if not email_ok and not telegram_ok:
            raise NotificationFailedException(
                f"All notification channels failed for journey {event['journey_id']}"
            )

    async def send_email(self, to: str, subject: str, body: str) -> None:
        if not self._settings.smtp_user or not self._settings.smtp_pass:
            logger.warning("SMTP credentials not configured, skipping email")
            return

        def _send() -> None:
            msg = MIMEMultipart()
            msg["From"] = self._settings.smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as server:
                server.starttls()
                server.login(self._settings.smtp_user, self._settings.smtp_pass)
                server.send_message(msg)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, _send)

    async def send_telegram(self, message: str) -> None:
        if not self._settings.telegram_bot_token or not self._settings.telegram_chat_id:
            logger.warning("Telegram credentials not configured, skipping")
            return
        try:
            from telegram import Bot
            bot = Bot(token=self._settings.telegram_bot_token)
            await bot.send_message(
                chat_id=self._settings.telegram_chat_id,
                text=message,
                parse_mode="Markdown",
            )
        except Exception as exc:
            raise RuntimeError(f"Telegram send failed: {exc}") from exc
