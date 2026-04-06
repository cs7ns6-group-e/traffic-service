import os
import json
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aio_pika
import httpx
from fastapi import FastAPI

app = FastAPI(title="notification")

REGION = os.getenv("REGION", "EU")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_email(subject: str, body: str):
    if not SMTP_USER or not SMTP_PASS:
        print("SMTP not configured — skipping email")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = SMTP_USER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, SMTP_USER, msg.as_string())
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Email error: {e}")


async def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured — skipping")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
            })
        print(f"Telegram sent: {message[:50]}")
    except Exception as e:
        print(f"Telegram error: {e}")


async def handle_booking_event(payload: dict):
    journey_id = payload.get("journey_id", "")[:8]
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    region = payload.get("region", REGION)
    status = payload.get("status", "CONFIRMED")

    if status == "EMERGENCY_CONFIRMED":
        subject = "🚨 EMERGENCY Journey Approved"
        body = (f"EMERGENCY VEHICLE APPROVED\n"
                f"Instant approval — no conflict check\n"
                f"{origin} → {destination}\nRegion: {region}")
        tg_msg = (f"*🚨 EMERGENCY VEHICLE APPROVED*\n"
                  f"Instant approval — no conflict check\n"
                  f"{origin} → {destination}")
    else:
        subject = f"Journey Confirmed — {journey_id}"
        body = (f"Journey CONFIRMED\nID: {journey_id}\n"
                f"{origin} → {destination}\nRegion: {region}")
        tg_msg = (f"*Journey CONFIRMED*\n"
                  f"ID: {journey_id}\n"
                  f"{origin} → {destination}\n"
                  f"Region: {region}")

    send_email(subject, body)
    await send_telegram(tg_msg)


async def handle_emergency_event(payload: dict):
    journey_id = payload.get("journey_id", "")[:8]
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    region = payload.get("region", REGION)

    subject = "🚨 EMERGENCY Journey Approved"
    body = (f"EMERGENCY VEHICLE APPROVED\n"
            f"ID: {journey_id}\n"
            f"{origin} → {destination}\nRegion: {region}")
    tg_msg = (f"*🚨 EMERGENCY VEHICLE APPROVED*\n"
              f"ID: {journey_id}\n"
              f"{origin} → {destination}")
    send_email(subject, body)
    await send_telegram(tg_msg)


async def handle_road_closure_event(payload: dict):
    road_name = payload.get("road_name", "Unknown road")
    reason = payload.get("reason", "No reason given")
    region = payload.get("region", REGION)

    subject = f"Road Closure Alert — {road_name}"
    body = f"Road Closure\n{road_name} is now closed\nReason: {reason}\nRegion: {region}"
    tg_msg = (f"*⚠️ Road Closure*\n"
              f"{road_name} is now closed\n"
              f"Reason: {reason}\n"
              f"Region: {region}")
    send_email(subject, body)
    await send_telegram(tg_msg)


async def consume():
    await asyncio.sleep(10)  # wait for RabbitMQ to be ready
    while True:
        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)

            booking_q = await channel.declare_queue("booking_events", durable=True)
            emergency_q = await channel.declare_queue("emergency_events", durable=True)
            closure_q = await channel.declare_queue("road_closure_events", durable=True)

            async def on_booking(msg: aio_pika.IncomingMessage):
                async with msg.process(requeue=True):
                    try:
                        payload = json.loads(msg.body)
                        await handle_booking_event(payload)
                    except Exception as e:
                        print(f"Booking event error: {e}")
                        raise

            async def on_emergency(msg: aio_pika.IncomingMessage):
                async with msg.process(requeue=True):
                    try:
                        payload = json.loads(msg.body)
                        await handle_emergency_event(payload)
                    except Exception as e:
                        print(f"Emergency event error: {e}")
                        raise

            async def on_closure(msg: aio_pika.IncomingMessage):
                async with msg.process(requeue=True):
                    try:
                        payload = json.loads(msg.body)
                        await handle_road_closure_event(payload)
                    except Exception as e:
                        print(f"Closure event error: {e}")
                        raise

            await booking_q.consume(on_booking)
            await emergency_q.consume(on_emergency)
            await closure_q.consume(on_closure)
            print("Notification consumer running")
            await asyncio.Future()
        except Exception as e:
            print(f"Consumer error, retrying in 5s: {e}")
            await asyncio.sleep(5)


@app.on_event("startup")
async def startup():
    asyncio.create_task(consume())


@app.get("/health")
def health():
    email_ok = bool(SMTP_USER and SMTP_PASS)
    telegram_ok = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    return {
        "status": "ok",
        "service": "notification",
        "region": REGION,
        "channels": {
            "email": "configured" if email_ok else "not_configured",
            "telegram": "configured" if telegram_ok else "not_configured",
        },
    }
