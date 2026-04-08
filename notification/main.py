import os
import json
import asyncio

import aio_pika
import httpx
from fastapi import FastAPI

app = FastAPI(title="notification")

REGION = os.getenv("REGION", "EU")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


async def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN in ("placeholder", ""):
        print(f"[Telegram log] {message[:120]}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(url, json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                })
                if r.status_code == 200:
                    print(f"Telegram sent: {message[:60]}")
                    return
                print(f"Telegram HTTP {r.status_code} on attempt {attempt + 1}")
        except Exception as e:
            print(f"Telegram error (attempt {attempt + 1}): {e}")
    print("Telegram: gave up after 2 attempts")


async def handle_booking_event(payload: dict):
    journey_id = payload.get("journey_id", "")[:8]
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    region = payload.get("region", REGION)
    start_time = payload.get("start_time", "")
    is_cross_region = payload.get("is_cross_region", False)
    dest_region = payload.get("dest_region", "")

    lines = [
        f"*Journey CONFIRMED* ✅",
        f"ID: `{journey_id}`",
        f"{origin} → {destination}",
    ]
    if start_time:
        lines.append(start_time)
    lines.append(f"Region: {region}")
    if is_cross_region and dest_region:
        lines.append(f"Cross-region: {region} → {dest_region}")

    await send_telegram("\n".join(lines))


async def handle_emergency_event(payload: dict):
    journey_id = payload.get("journey_id", "")[:8]
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    region = payload.get("region", REGION)

    msg = (
        f"🚨 *EMERGENCY JOURNEY APPROVED*\n"
        f"Instant approval — no conflict check\n"
        f"{origin} → {destination}\n"
        f"Region: {region}"
    )
    await send_telegram(msg)


async def handle_cancellation_event(payload: dict):
    journey_id = payload.get("journey_id", "")[:8]
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    reason = payload.get("reason", "")

    lines = [
        f"*Journey CANCELLED* ❌",
        f"ID: `{journey_id}`",
        f"{origin} → {destination}",
    ]
    if reason:
        lines.append(f"Reason: {reason}")

    await send_telegram("\n".join(lines))


async def handle_force_cancel_event(payload: dict):
    journey_id = payload.get("journey_id", "")[:8]
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    reason = payload.get("reason", "No reason given")

    msg = (
        f"*Journey FORCE CANCELLED* 🚫\n"
        f"ID: `{journey_id}`\n"
        f"{origin} → {destination}\n"
        f"Cancelled by: Traffic Authority\n"
        f"Reason: {reason}"
    )
    await send_telegram(msg)


async def handle_road_closure_event(payload: dict):
    road_name = payload.get("road_name", "Unknown road")
    reason = payload.get("reason", "No reason given")
    region = payload.get("region", REGION)

    msg = (
        f"*⚠️ Road Closure Alert*\n"
        f"Road: {road_name}\n"
        f"Reason: {reason}\n"
        f"Region: {region}\n"
        f"Your journey has been cancelled."
    )
    await send_telegram(msg)


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
            cancel_q = await channel.declare_queue("journey_cancelled_events", durable=True)
            force_cancel_q = await channel.declare_queue("journey_force_cancelled_events", durable=True)

            async def on_booking(msg: aio_pika.IncomingMessage):
                async with msg.process(requeue=True):
                    try:
                        await handle_booking_event(json.loads(msg.body))
                    except Exception as e:
                        print(f"Booking event error: {e}")
                        raise

            async def on_emergency(msg: aio_pika.IncomingMessage):
                async with msg.process(requeue=True):
                    try:
                        await handle_emergency_event(json.loads(msg.body))
                    except Exception as e:
                        print(f"Emergency event error: {e}")
                        raise

            async def on_closure(msg: aio_pika.IncomingMessage):
                async with msg.process(requeue=True):
                    try:
                        await handle_road_closure_event(json.loads(msg.body))
                    except Exception as e:
                        print(f"Closure event error: {e}")
                        raise

            async def on_cancel(msg: aio_pika.IncomingMessage):
                async with msg.process(requeue=True):
                    try:
                        await handle_cancellation_event(json.loads(msg.body))
                    except Exception as e:
                        print(f"Cancel event error: {e}")
                        raise

            async def on_force_cancel(msg: aio_pika.IncomingMessage):
                async with msg.process(requeue=True):
                    try:
                        await handle_force_cancel_event(json.loads(msg.body))
                    except Exception as e:
                        print(f"Force cancel event error: {e}")
                        raise

            await booking_q.consume(on_booking)
            await emergency_q.consume(on_emergency)
            await closure_q.consume(on_closure)
            await cancel_q.consume(on_cancel)
            await force_cancel_q.consume(on_force_cancel)
            print("Notification consumer running (Telegram only)")
            await asyncio.Future()
        except Exception as e:
            print(f"Consumer error, retrying in 5s: {e}")
            await asyncio.sleep(5)


@app.on_event("startup")
async def startup():
    asyncio.create_task(consume())


@app.get("/health")
def health():
    telegram_ok = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "placeholder")
    return {
        "status": "ok",
        "service": "notification",
        "region": REGION,
        "channels": {
            "telegram": "configured" if telegram_ok else "not_configured",
        },
    }
