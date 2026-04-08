import os
import json
import asyncio
from datetime import datetime

import aio_pika
import httpx
import psycopg2
from fastapi import FastAPI

app = FastAPI(title="notification")

REGION = os.getenv("REGION", "EU")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS replicated_journeys (
            id UUID PRIMARY KEY,
            origin_region TEXT NOT NULL,
            driver_id UUID,
            driver_email TEXT,
            origin TEXT,
            destination TEXT,
            start_time TIMESTAMP,
            status TEXT,
            vehicle_type TEXT,
            route_segments JSONB DEFAULT '[]',
            distance_km FLOAT,
            duration_mins INTEGER,
            is_cross_region BOOLEAN DEFAULT FALSE,
            dest_region TEXT,
            replicated_at TIMESTAMP DEFAULT NOW(),
            original_created_at TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_rep_origin_region
            ON replicated_journeys(origin_region);
        CREATE INDEX IF NOT EXISTS idx_rep_driver
            ON replicated_journeys(driver_id);
    """)
    conn.commit()
    cur.close()
    conn.close()


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


def _fmt_datetime(start_time: str):
    try:
        dt = datetime.fromisoformat(str(start_time).replace(" ", "T").split(".")[0])
        return dt.strftime("%A %d %B %Y"), dt.strftime("%H:%M")
    except Exception:
        return str(start_time), ""


async def handle_booking_event(payload: dict):
    journey_id = payload.get("journey_id", "")
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    origin_region = payload.get("origin_region", payload.get("region", REGION))
    start_time = payload.get("start_time", "")
    is_cross_region = payload.get("is_cross_region", False)
    dest_region = payload.get("dest_region", "")
    driver_name = payload.get("driver_name", payload.get("telegram_name", "Driver"))
    driver_email = payload.get("driver_email", "")
    distance_km = payload.get("distance_km")
    duration_mins = payload.get("duration_mins")
    segments = payload.get("route_segments", [])

    formatted_date, formatted_time = _fmt_datetime(start_time)
    cross_region_line = (
        f"\n*Cross-region:* {origin_region} → {dest_region}"
        if is_cross_region and dest_region else ""
    )
    segments_str = ", ".join(segments[:3]) if segments else "N/A"
    dist_str = f"{distance_km:.1f}" if distance_km else "N/A"
    dur_str = str(duration_mins) if duration_mins else "N/A"

    message = (
        f"*Journey CONFIRMED* ✅\n\n"
        f"*Passenger:* {driver_name} ({driver_email})\n"
        f"*Route:* {origin} → {destination}\n"
        f"*Date:* {formatted_date}\n"
        f"*Time:* {formatted_time}\n"
        f"*Duration:* {dur_str} mins\n"
        f"*Distance:* {dist_str} km\n"
        f"*Segments:* {segments_str}\n"
        f"*Region:* {origin_region}"
        f"{cross_region_line}\n"
        f"*Journey ID:* `{str(journey_id)[:8]}`\n"
        f"*Status:* CONFIRMED — have a safe journey!"
    )
    await send_telegram(message)


async def handle_emergency_event(payload: dict):
    journey_id = payload.get("journey_id", "")
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    origin_region = payload.get("origin_region", payload.get("region", REGION))
    start_time = payload.get("start_time", "")
    driver_name = payload.get("driver_name", payload.get("telegram_name", "Driver"))
    driver_email = payload.get("driver_email", "")
    distance_km = payload.get("distance_km")

    formatted_date, formatted_time = _fmt_datetime(start_time)
    dist_str = f"{distance_km:.1f}" if distance_km else "N/A"

    message = (
        f"*EMERGENCY JOURNEY APPROVED* 🚨\n\n"
        f"*Driver:* {driver_name} ({driver_email})\n"
        f"*Route:* {origin} → {destination}\n"
        f"*Date:* {formatted_date} at {formatted_time}\n"
        f"*Distance:* {dist_str} km\n"
        f"*Region:* {origin_region}\n"
        f"*Journey ID:* `{str(journey_id)[:8]}`\n\n"
        f"Emergency vehicle — instant approval, all roads clear."
    )
    await send_telegram(message)


async def handle_cancellation_event(payload: dict):
    journey_id = payload.get("journey_id", "")
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    start_time = payload.get("start_time", "")
    driver_name = payload.get("driver_name", payload.get("telegram_name", "Driver"))
    driver_email = payload.get("driver_email", "")

    formatted_date, formatted_time = _fmt_datetime(start_time)

    message = (
        f"*Journey CANCELLED* ❌\n\n"
        f"*Passenger:* {driver_name} ({driver_email})\n"
        f"*Route:* {origin} → {destination}\n"
        f"*Was scheduled:* {formatted_date} at {formatted_time}\n"
        f"*Journey ID:* `{str(journey_id)[:8]}`\n"
        f"*Cancelled by:* Driver (self-cancellation)"
    )
    await send_telegram(message)


async def handle_force_cancel_event(payload: dict):
    journey_id = payload.get("journey_id", "")
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    start_time = payload.get("start_time", "")
    reason = payload.get("reason", "No reason given")
    driver_name = payload.get("driver_name", payload.get("telegram_name", "Driver"))
    driver_email = payload.get("driver_email", "")
    cancelled_by = payload.get("cancelled_by", "Traffic Authority")

    formatted_date, formatted_time = _fmt_datetime(start_time)

    message = (
        f"*Journey FORCE CANCELLED* 🚫\n\n"
        f"*Passenger:* {driver_name} ({driver_email})\n"
        f"*Route:* {origin} → {destination}\n"
        f"*Was scheduled:* {formatted_date} at {formatted_time}\n"
        f"*Journey ID:* `{str(journey_id)[:8]}`\n"
        f"*Cancelled by:* Traffic Authority ({cancelled_by})\n"
        f"*Reason:* {reason}\n\n"
        f"Please rebook at a different time."
    )
    await send_telegram(message)


async def handle_road_closure_event(payload: dict):
    journey_id = payload.get("journey_id", "")
    origin = payload.get("origin", "")
    destination = payload.get("destination", "")
    start_time = payload.get("start_time", "")
    road_name = payload.get("road_name", "Unknown road")
    closure_reason = payload.get("reason", "No reason given")
    region = payload.get("region", REGION)
    driver_name = payload.get("driver_name", payload.get("telegram_name", "Driver"))
    driver_email = payload.get("driver_email", "")

    formatted_date, formatted_time = _fmt_datetime(start_time)

    message = (
        f"*Road Closure — Journey Cancelled* ⚠️\n\n"
        f"*Passenger:* {driver_name} ({driver_email})\n"
        f"*Your route:* {origin} → {destination}\n"
        f"*Was scheduled:* {formatted_date} at {formatted_time}\n"
        f"*Journey ID:* `{str(journey_id)[:8]}`\n\n"
        f"*Road closed:* {road_name}\n"
        f"*Closure reason:* {closure_reason}\n"
        f"*Region:* {region}\n\n"
        f"Your journey has been cancelled due to this closure.\n"
        f"Please rebook via an alternative route."
    )
    await send_telegram(message)


async def replicate_journey(event_data: dict):
    """Write incoming journey event to local replicated_journeys table.
    Skips if origin_region matches this region (already in primary journeys table).
    """
    if event_data.get("origin_region") == REGION:
        return

    if not DATABASE_URL:
        return

    try:
        conn = get_conn()
        cur = conn.cursor()
        try:
            driver_id_raw = event_data.get("driver_id")
            # driver_id must be a valid UUID or None
            try:
                import uuid as _uuid
                driver_id_val = str(_uuid.UUID(str(driver_id_raw))) if driver_id_raw else None
            except Exception:
                driver_id_val = None

            cur.execute("""
                INSERT INTO replicated_journeys (
                    id, origin_region, driver_id, driver_email,
                    origin, destination, start_time, status,
                    vehicle_type, route_segments, distance_km,
                    duration_mins, is_cross_region, dest_region,
                    original_created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    replicated_at = NOW()
            """, (
                event_data.get("journey_id"),
                event_data.get("origin_region"),
                driver_id_val,
                event_data.get("driver_email"),
                event_data.get("origin"),
                event_data.get("destination"),
                event_data.get("start_time"),
                event_data.get("status", "CONFIRMED"),
                event_data.get("vehicle_type", "STANDARD"),
                json.dumps(event_data.get("route_segments", [])),
                event_data.get("distance_km"),
                event_data.get("duration_mins"),
                event_data.get("is_cross_region", False),
                event_data.get("dest_region"),
                event_data.get("created_at"),
            ))
            conn.commit()
            jid = str(event_data.get("journey_id", ""))[:8]
            print(
                f"Replicated journey {jid} "
                f"from {event_data.get('origin_region')} to {REGION}"
            )
        except Exception as e:
            print(f"Replication error: {e}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        print(f"Replication DB connect error: {e}")


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
            force_cancel_q = await channel.declare_queue(
                "journey_force_cancelled_events", durable=True
            )
            replication_q = await channel.declare_queue(
                "journey_replication_events", durable=True
            )

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

            async def on_replication(msg: aio_pika.IncomingMessage):
                async with msg.process(requeue=False):
                    try:
                        await replicate_journey(json.loads(msg.body))
                    except Exception as e:
                        print(f"Replication event error: {e}")

            await booking_q.consume(on_booking)
            await emergency_q.consume(on_emergency)
            await closure_q.consume(on_closure)
            await cancel_q.consume(on_cancel)
            await force_cancel_q.consume(on_force_cancel)
            await replication_q.consume(on_replication)
            print("Notification consumer running (Telegram + replication)")
            await asyncio.Future()
        except Exception as e:
            print(f"Consumer error, retrying in 5s: {e}")
            await asyncio.sleep(5)


@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try:
            init_db()
            print("replicated_journeys table ready")
        except Exception as e:
            print(f"DB init warning: {e}")
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
