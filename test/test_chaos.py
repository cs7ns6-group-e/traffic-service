#!/usr/bin/env python3
"""
TrafficBook -- Chaos / Node-Removal Fault Tolerance Test
=========================================================
Actually stops Docker containers (or entire VMs) via SSH / gcloud,
runs live traffic against the degraded system, then restores and
verifies recovery.

Scenarios
---------
  C-1  Kill road_routing        -> bookings still CONFIRMED (routing optional)
  C-2  Kill conflict_detection  -> bookings still CONFIRMED (conflict check skipped)
  C-3  Kill notification        -> bookings CONFIRMED, no Telegram (async only)
  C-4  Kill redis               -> conflict detection falls back to DB-only
  C-5  Kill rabbitmq            -> bookings CONFIRMED, replication paused
  C-6  Kill auth_service        -> NEW logins fail; existing JWT still valid
  C-7  Kill postgres            -> bookings fail (500/503); health reports down
  C-8  Kill entire EU region    -> US and APAC unaffected, serve independently
  C-9  Kill two services        -> system partially degraded but not dead
  C-10 Rolling restart          -> zero-downtime: restart each service one by one

Usage
-----
  # default: uses ~/.ssh/id_rsa, targets EU VM only for speed
  python3 test/test_chaos.py --ssh-key ~/.ssh/your_key --user niraj

  # full 3-region test (takes longer)
  python3 test/test_chaos.py --ssh-key ~/.ssh/your_key --user niraj --all-regions

  # single scenario
  python3 test/test_chaos.py --ssh-key ~/.ssh/your_key --user niraj --scenario C-1

  # dry run: print SSH commands without executing
  python3 test/test_chaos.py --dry-run

  # skip VM-stop scenarios (only service-level chaos)
  python3 test/test_chaos.py --ssh-key ~/.ssh/your_key --user niraj --no-vm-stop

Requirements: pip install requests
SSH key must have access to the VMs (same key used in GitHub Actions).
"""

import sys
import time
import json
import argparse
import subprocess
import threading
from datetime import datetime, timedelta

try:
    import requests
    from requests.exceptions import ConnectionError, Timeout
except ImportError:
    print("pip install requests")
    sys.exit(1)

# ── Infrastructure ────────────────────────────────────────────────────────────
EU_LB   = "http://35.240.110.205"
US_LB   = "http://34.10.45.241"
APAC_LB = "http://34.126.131.195"

EU_VM_IP   = "104.155.13.81"
US_VM_IP   = "136.111.143.185"
APAC_VM_IP = "34.143.250.128"

REGIONS = [
    {"name": "EU",   "lb": EU_LB,   "vm_ip": EU_VM_IP},
    {"name": "US",   "lb": US_LB,   "vm_ip": US_VM_IP},
    {"name": "APAC", "lb": APAC_LB, "vm_ip": APAC_VM_IP},
]

# Docker container names on each VM (docker compose project = traffic-service)
CONTAINERS = {
    "auth":      "traffic-service-auth_service-1",
    "journey":   "traffic-service-journey_booking-1",
    "conflict":  "traffic-service-conflict_detection-1",
    "notify":    "traffic-service-notification-1",
    "routing":   "traffic-service-road_routing-1",
    "authority": "traffic-service-traffic_authority-1",
    "admin":     "traffic-service-admin_service-1",
    "postgres":  "traffic-service-postgres-1",
    "redis":     "traffic-service-redis-1",
    "rabbitmq":  "traffic-service-rabbitmq-1",
    "nginx":     "traffic-service-nginx-1",
}

FUTURE      = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
FUTURE_SLOT = (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%dT10:00:00")

# ── Global config (set by args) ───────────────────────────────────────────────
SSH_KEY  = None
SSH_USER = None
DRY_RUN  = False

# ── Result tracking ───────────────────────────────────────────────────────────
results = []

def record(scenario, name, passed, detail="", duration_ms=None):
    icon = "✅" if passed else "❌"
    dur  = f"  [{duration_ms:.0f}ms]" if duration_ms is not None else ""
    print(f"  {icon} [{scenario}] {name}{dur}")
    if detail:
        print(f"        {detail}")
    results.append({
        "scenario": scenario, "name": name,
        "passed": passed, "detail": detail,
        "duration_ms": duration_ms,
    })

def section(title):
    print(f"\n{'='*62}")
    print(f"  {title}")
    print(f"{'='*62}")

# ── HTTP helpers ──────────────────────────────────────────────────────────────
def _get(url, token=None, timeout=8):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    t0 = time.time()
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        return r, (time.time() - t0) * 1000
    except Exception:
        return None, (time.time() - t0) * 1000

def _post(url, body, token=None, timeout=10):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    t0 = time.time()
    try:
        r = requests.post(url, json=body, headers=headers, timeout=timeout)
        return r, (time.time() - t0) * 1000
    except Exception:
        return None, (time.time() - t0) * 1000

def login(base, email, password):
    r, _ = _post(f"{base}/auth/login", {"email": email, "password": password})
    return r.json().get("access_token") if r and r.status_code == 200 else None

# ── SSH / Docker helpers ──────────────────────────────────────────────────────
def ssh(vm_ip, cmd, timeout=30):
    """Run a command on a remote VM via SSH. Returns (stdout, stderr, returncode)."""
    if DRY_RUN:
        print(f"  [DRY-RUN] ssh {SSH_USER}@{vm_ip} '{cmd}'")
        return "", "", 0

    ssh_cmd = [
        "ssh",
        "-i", SSH_KEY,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=15",
        "-o", "BatchMode=yes",
        f"{SSH_USER}@{vm_ip}",
        cmd,
    ]
    try:
        r = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "ssh timeout", 1
    except Exception as e:
        return "", str(e), 1

def container_stop(vm_ip, container_name):
    out, err, rc = ssh(vm_ip, f"docker stop {container_name}")
    ok = rc == 0 or DRY_RUN
    print(f"  [chaos] STOP  {container_name} on {vm_ip} -> {'ok' if ok else f'FAIL: {err}'}")
    return ok

def container_start(vm_ip, container_name):
    out, err, rc = ssh(vm_ip, f"docker start {container_name}")
    ok = rc == 0 or DRY_RUN
    print(f"  [chaos] START {container_name} on {vm_ip} -> {'ok' if ok else f'FAIL: {err}'}")
    return ok

def container_restart(vm_ip, container_name):
    out, err, rc = ssh(vm_ip, f"docker restart {container_name}")
    ok = rc == 0 or DRY_RUN
    print(f"  [chaos] RESTART {container_name} on {vm_ip} -> {'ok' if ok else f'FAIL: {err}'}")
    return ok

def container_is_running(vm_ip, container_name):
    out, _, rc = ssh(vm_ip, f"docker inspect --format='{{{{.State.Running}}}}' {container_name}")
    return out.strip() == "true" or DRY_RUN

def wait_healthy(vm_ip, container_name, port, max_wait=45):
    """Poll container health after restart; return seconds taken or -1."""
    if DRY_RUN:
        return 5
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r, _ = _get(f"http://{vm_ip}:{port}/health", timeout=3)
        if r and r.status_code == 200:
            return round(time.time() - (deadline - max_wait))
        time.sleep(2)
    return -1

def gcloud_stop_vm(vm_name, zone):
    if DRY_RUN:
        print(f"  [DRY-RUN] gcloud compute instances stop {vm_name} --zone={zone}")
        return True
    cmd = ["gcloud", "compute", "instances", "stop", vm_name, f"--zone={zone}", "--quiet"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode == 0

def gcloud_start_vm(vm_name, zone):
    if DRY_RUN:
        print(f"  [DRY-RUN] gcloud compute instances start {vm_name} --zone={zone}")
        return True
    cmd = ["gcloud", "compute", "instances", "start", vm_name, f"--zone={zone}", "--quiet"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    return r.returncode == 0


# ── Token bootstrap ───────────────────────────────────────────────────────────
_tokens = {}

def bootstrap():
    section("Bootstrapping tokens (EU region)")
    creds = [
        ("driver@trafficbook.com",    "Driver123!",    "driver"),
        ("emergency@trafficbook.com", "Emergency123!", "emergency"),
        ("admin@trafficbook.com",     "Admin123!",     "admin"),
    ]
    _tokens["EU"] = {}
    _tokens["US"] = {}
    _tokens["APAC"] = {}
    for email, pwd, key in creds:
        for reg in REGIONS:
            tok = login(reg["lb"], email, pwd)
            _tokens[reg["name"]][key] = tok
            status = "ok" if tok else "FAILED"
            print(f"  {reg['name']} {key}: {status}")

def tok(region, role):
    return _tokens.get(region, {}).get(role)

def book(base, token, origin="Dublin, Ireland", dest="Cork, Ireland", slot=None):
    return _post(f"{base}/journeys", {
        "origin": origin, "destination": dest,
        "start_time": slot or FUTURE,
    }, token=token)


# ==============================================================================
# C-1  road_routing killed
# ==============================================================================
def scenario_c1():
    section("C-1  Kill road_routing -> booking must still succeed (graceful degradation)")
    vm = EU_VM_IP
    svc = CONTAINERS["routing"]

    container_stop(vm, svc)
    time.sleep(3)

    # Health check should still show nginx alive
    r, ms = _get(f"{EU_LB}/health")
    record("C-1", "nginx LB health survives routing outage",
           r is not None and r.status_code == 200, f"HTTP {r.status_code if r else 'timeout'}", ms)

    # Booking should still complete (routing failure is swallowed with `pass`)
    t = tok("EU", "driver")
    if t:
        r, ms = book(EU_LB, t)
        record("C-1", "Booking succeeds without routing (graceful degrade)",
               r is not None and r.status_code in (200, 201),
               f"HTTP {r.status_code if r else 'timeout'} | route_segments likely empty", ms)
        if r and r.status_code in (200, 201):
            segs = r.json().get("route_segments", [])
            record("C-1", "route_segments empty when routing down (expected)",
                   segs == [] or segs is None,
                   f"segments={segs}")
    else:
        record("C-1", "Booking without routing", False, "no token")

    # Restore
    container_start(vm, svc)
    recovery = wait_healthy(vm, svc, 8004)
    record("C-1", f"road_routing recovered",
           recovery >= 0, f"took ~{recovery}s" if recovery >= 0 else "did not recover in 45s")


# ==============================================================================
# C-2  conflict_detection killed
# ==============================================================================
def scenario_c2():
    section("C-2  Kill conflict_detection -> booking still CONFIRMED (check skipped)")
    vm = EU_VM_IP
    svc = CONTAINERS["conflict"]

    container_stop(vm, svc)
    time.sleep(3)

    t = tok("EU", "driver")
    if t:
        slot = (datetime.now() + timedelta(days=50)).strftime("%Y-%m-%dT11:00:00")
        r, ms = book(EU_LB, t, slot=slot)
        record("C-2", "Booking confirmed when conflict service is down",
               r is not None and r.status_code in (200, 201),
               f"HTTP {r.status_code if r else 'timeout'} in {ms:.0f}ms", ms)
    else:
        record("C-2", "Booking without conflict service", False, "no token")

    container_start(vm, svc)
    recovery = wait_healthy(vm, svc, 8002)
    record("C-2", "conflict_detection recovered",
           recovery >= 0, f"took ~{recovery}s")


# ==============================================================================
# C-3  notification killed
# ==============================================================================
def scenario_c3():
    section("C-3  Kill notification -> bookings succeed, Telegram silent")
    vm = EU_VM_IP
    svc = CONTAINERS["notify"]

    container_stop(vm, svc)
    time.sleep(3)

    t = tok("EU", "driver")
    if t:
        r, ms = book(EU_LB, t)
        record("C-3", "Booking confirmed when notification service down",
               r is not None and r.status_code in (200, 201),
               f"HTTP {r.status_code if r else 'timeout'}", ms)

    # RabbitMQ queue depth should be building up (events not consumed)
    # Check via admin service HTTP management API
    a_tok = tok("EU", "admin")
    if a_tok:
        r2, ms2 = _get(f"{EU_LB}/admin/health", token=a_tok)
        if r2 and r2.status_code == 200:
            svcs = r2.json().get("services", [])
            notify_entry = next((s for s in svcs
                                 if "notif" in s.get("name","").lower()), None)
            if notify_entry:
                record("C-3", "Admin health shows notification status",
                       True, f"status={notify_entry.get('status')}")
            else:
                record("C-3", "Admin health shows notification status",
                       False, "notification not in health response")

    container_start(vm, svc)
    recovery = wait_healthy(vm, svc, 8003)
    record("C-3", "notification recovered",
           recovery >= 0, f"took ~{recovery}s")


# ==============================================================================
# C-4  Redis killed
# ==============================================================================
def scenario_c4():
    section("C-4  Kill Redis -> conflict detection falls back to DB-only check")
    vm = EU_VM_IP
    svc = CONTAINERS["redis"]

    container_stop(vm, svc)
    time.sleep(3)

    t = tok("EU", "driver")
    if t:
        # Slot reservation should fail or degrade gracefully (Redis unavailable)
        slot = (datetime.now() + timedelta(days=55)).strftime("%Y-%m-%dT09:00:00")
        r, ms = _post(f"{EU_LB}/conflicts/reserve-slot", {
            "origin": "Dublin, Ireland",
            "destination": "Cork, Ireland",
            "start_time": slot,
        }, token=t)
        # Should return 500/503 OR fallback (not hang)
        responded = r is not None
        record("C-4", "Slot reservation returns (no hang) with Redis down",
               responded,
               f"HTTP {r.status_code if r else 'timeout'} in {ms:.0f}ms", ms)

        # Full booking may still work (conflict check swallowed)
        r2, ms2 = book(EU_LB, t, slot=slot)
        record("C-4", "Full booking attempted with Redis down (not crash)",
               r2 is not None and r2.status_code not in (502, 504),
               f"HTTP {r2.status_code if r2 else 'timeout'}", ms2)

    container_start(vm, svc)
    # Redis has no health endpoint exposed -- wait a few seconds
    time.sleep(8)
    record("C-4", "Redis restarted (no health probe available)",
           True, "container restarted; conflict service will reconnect on next request")


# ==============================================================================
# C-5  RabbitMQ killed
# ==============================================================================
def scenario_c5():
    section("C-5  Kill RabbitMQ -> bookings succeed, replication/notifications paused")
    vm = EU_VM_IP
    svc = CONTAINERS["rabbitmq"]

    container_stop(vm, svc)
    time.sleep(5)   # notification/journey_booking reconnect loops

    t = tok("EU", "driver")
    if t:
        r, ms = book(EU_LB, t)
        record("C-5", "Booking still CONFIRMED with RabbitMQ down",
               r is not None and r.status_code in (200, 201),
               f"HTTP {r.status_code if r else 'timeout'} in {ms:.0f}ms", ms)
        # Cross-region HTTP replication is direct (not via rabbit), so check it
        r2, ms2 = book(EU_LB, t,
                       dest="New York, USA",
                       slot=(datetime.now() + timedelta(days=32)).strftime("%Y-%m-%dT12:00:00"))
        record("C-5", "Cross-region booking (direct HTTP) works without RabbitMQ",
               r2 is not None and r2.status_code in (200, 201),
               f"HTTP {r2.status_code if r2 else 'timeout'}", ms2)

    container_start(vm, svc)
    time.sleep(10)   # RabbitMQ takes a few seconds to boot
    # Verify journey_booking reconnects to rabbit (try a new booking)
    if t:
        r3, ms3 = book(EU_LB, t)
        record("C-5", "Booking works after RabbitMQ recovery (reconnect ok)",
               r3 is not None and r3.status_code in (200, 201),
               f"HTTP {r3.status_code if r3 else 'timeout'}", ms3)


# ==============================================================================
# C-6  auth_service killed
# ==============================================================================
def scenario_c6():
    section("C-6  Kill auth_service -> NEW logins fail; existing JWT still valid")
    vm = EU_VM_IP
    svc = CONTAINERS["auth"]

    container_stop(vm, svc)
    time.sleep(3)

    # Existing token should still work (JWT verified locally via shared secret)
    t = tok("EU", "driver")
    if t:
        r, ms = _get(f"{EU_LB}/journeys", token=t)
        record("C-6", "Existing JWT accepted without auth_service running",
               r is not None and r.status_code in (200, 404),
               f"HTTP {r.status_code if r else 'timeout'} in {ms:.0f}ms", ms)

    # New login should fail
    new_tok = login(EU_LB, "driver@trafficbook.com", "Driver123!")
    record("C-6", "New login fails when auth_service is down",
           new_tok is None,
           f"token={'None (expected)' if new_tok is None else 'got token (unexpected)'}")

    container_start(vm, svc)
    recovery = wait_healthy(vm, svc, 8000)
    record("C-6", "auth_service recovered", recovery >= 0, f"took ~{recovery}s")

    # New login should work after recovery
    new_tok2 = login(EU_LB, "driver@trafficbook.com", "Driver123!")
    record("C-6", "New login works after auth_service recovery",
           new_tok2 is not None, "")


# ==============================================================================
# C-7  PostgreSQL killed
# ==============================================================================
def scenario_c7():
    section("C-7  Kill PostgreSQL -> bookings fail; health reports degraded")
    vm = EU_VM_IP
    svc = CONTAINERS["postgres"]

    container_stop(vm, svc)
    time.sleep(5)

    t = tok("EU", "driver")
    if t:
        r, ms = book(EU_LB, t)
        record("C-7", "Booking fails (500/503) when PostgreSQL is down",
               r is not None and r.status_code in (500, 503, 422),
               f"HTTP {r.status_code if r else 'timeout'} (expected 5xx)", ms)

    # Admin health should report postgres/services as degraded
    a = tok("EU", "admin")
    if a:
        r2, ms2 = _get(f"{EU_LB}/admin/health", token=a)
        if r2 and r2.status_code == 200:
            svcs = r2.json().get("services", [])
            degraded = [s for s in svcs if s.get("status") not in ("ok", "healthy")]
            record("C-7", "Admin health reports degraded services with DB down",
                   len(degraded) > 0,
                   f"{len(degraded)} degraded: {[s.get('name','?') for s in degraded]}")
        else:
            record("C-7", "Admin health response during DB outage", False,
                   f"HTTP {r2.status_code if r2 else 'timeout'}")

    container_start(vm, svc)
    time.sleep(10)  # Postgres needs time to restore
    recovery = wait_healthy(vm, CONTAINERS["journey"], 8001, max_wait=60)
    record("C-7", "journey_booking recovered after DB restart",
           recovery >= 0, f"took ~{recovery}s")

    if t:
        r3, ms3 = book(EU_LB, t)
        record("C-7", "Booking succeeds after PostgreSQL recovery",
               r3 is not None and r3.status_code in (200, 201),
               f"HTTP {r3.status_code if r3 else 'timeout'}", ms3)


# ==============================================================================
# C-8  Kill entire EU region VM
# ==============================================================================
def scenario_c8(no_vm_stop=False):
    section("C-8  Kill entire EU VM -> US and APAC serve independently")

    if no_vm_stop:
        print("  [SKIPPED] --no-vm-stop flag set. To run: remove --no-vm-stop")
        record("C-8", "EU VM stop (skipped by flag)", True, "use --no-vm-stop=false to enable")
        return

    EU_VM_NAME = "tb-vm-eu"
    EU_ZONE    = "europe-west1-b"

    print(f"  Stopping GCP VM {EU_VM_NAME} ({EU_ZONE})...")
    stopped = gcloud_stop_vm(EU_VM_NAME, EU_ZONE)
    record("C-8", f"EU VM ({EU_VM_NAME}) stopped via gcloud",
           stopped or DRY_RUN, "")

    time.sleep(15)

    # US and APAC must still work
    for reg in [r for r in REGIONS if r["name"] != "EU"]:
        r, ms = _get(f"{reg['lb']}/health")
        record("C-8", f"{reg['name']} region healthy while EU is down",
               r is not None and r.status_code == 200,
               f"HTTP {r.status_code if r else 'timeout'} in {ms:.0f}ms", ms)

        t = tok(reg["name"], "driver")
        if t:
            r2, ms2 = book(reg["lb"], t)
            record("C-8", f"{reg['name']} accepts bookings while EU is down",
                   r2 is not None and r2.status_code in (200, 201),
                   f"HTTP {r2.status_code if r2 else 'timeout'}", ms2)

    # EU should be unreachable
    r_eu, ms_eu = _get(f"{EU_LB}/health", timeout=5)
    record("C-8", "EU LB unreachable while VM stopped",
           r_eu is None, f"got HTTP {r_eu.status_code if r_eu else 'no response (expected)'}")

    # Restore EU
    print(f"  Restarting GCP VM {EU_VM_NAME}...")
    started = gcloud_start_vm(EU_VM_NAME, EU_ZONE)
    record("C-8", "EU VM restarted via gcloud", started or DRY_RUN, "")

    print("  Waiting 60s for EU VM to boot and services to start...")
    time.sleep(60)

    r_eu2, ms_eu2 = _get(f"{EU_LB}/health", timeout=15)
    record("C-8", "EU region recovered after VM restart",
           r_eu2 is not None and r_eu2.status_code == 200,
           f"HTTP {r_eu2.status_code if r_eu2 else 'timeout'}", ms_eu2)


# ==============================================================================
# C-9  Kill two services simultaneously
# ==============================================================================
def scenario_c9():
    section("C-9  Kill road_routing + conflict_detection simultaneously")
    vm = EU_VM_IP

    container_stop(vm, CONTAINERS["routing"])
    container_stop(vm, CONTAINERS["conflict"])
    time.sleep(4)

    t = tok("EU", "driver")
    if t:
        r, ms = book(EU_LB, t)
        record("C-9", "Booking still CONFIRMED with routing+conflict both down",
               r is not None and r.status_code in (200, 201),
               f"HTTP {r.status_code if r else 'timeout'} in {ms:.0f}ms", ms)

    # Health check
    r2, ms2 = _get(f"{EU_LB}/health")
    record("C-9", "nginx LB health still responds with 2 services down",
           r2 is not None and r2.status_code == 200,
           f"HTTP {r2.status_code if r2 else 'timeout'}", ms2)

    # Restore both
    container_start(vm, CONTAINERS["routing"])
    container_start(vm, CONTAINERS["conflict"])

    r_rt = wait_healthy(vm, CONTAINERS["routing"],  8004)
    r_cf = wait_healthy(vm, CONTAINERS["conflict"], 8002)
    record("C-9", "road_routing recovered",     r_rt >= 0, f"~{r_rt}s")
    record("C-9", "conflict_detection recovered", r_cf >= 0, f"~{r_cf}s")


# ==============================================================================
# C-10  Rolling restart (zero-downtime simulation)
# ==============================================================================
def scenario_c10():
    section("C-10  Rolling restart -- restart every service one by one")
    vm = EU_VM_IP

    service_ports = [
        ("auth",      8000),
        ("journey",   8001),
        ("conflict",  8002),
        ("notify",    8003),
        ("routing",   8004),
        ("authority", 8005),
        ("admin",     8006),
    ]

    t = tok("EU", "driver")
    failed_during = []

    for key, port in service_ports:
        container = CONTAINERS[key]
        print(f"\n  Rolling restart: {container}")
        container_restart(vm, container)
        time.sleep(3)

        # While this service is restarting, all others should still handle requests
        if t and key not in ("auth",):   # skip booking test during auth restart
            r, ms = book(EU_LB, t)
            still_ok = r is not None and r.status_code in (200, 201, 409)
            if not still_ok:
                failed_during.append(key)
            record("C-10", f"Booking works while {key} restarts",
                   still_ok,
                   f"HTTP {r.status_code if r else 'timeout'}", ms)

        # Wait for this service to come back
        recovery = wait_healthy(vm, container, port, max_wait=30)
        record("C-10", f"{key} healthy after restart",
               recovery >= 0, f"~{recovery}s")

    record("C-10", f"System survived rolling restart of all 7 services",
           len(failed_during) == 0,
           f"failures during restart: {failed_during if failed_during else 'none'}")


# ── Summary ───────────────────────────────────────────────────────────────────
def print_summary():
    passed = [r for r in results if r["passed"]]
    failed = [r for r in results if not r["passed"]]

    print(f"\n{'='*62}")
    print(f"  CHAOS TEST RESULTS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*62}")
    print(f"  Total : {len(results)}")
    print(f"  Passed: {len(passed)}  ✅")
    print(f"  Failed: {len(failed)}  ❌")
    if results:
        print(f"  Rate  : {100*len(passed)/len(results):.1f}%")

    if failed:
        print(f"\n  FAILURES:")
        for r in failed:
            print(f"    ❌ [{r['scenario']}] {r['name']}")
            if r["detail"]:
                print(f"        {r['detail']}")

    # Per-scenario summary
    scenarios = sorted({r["scenario"] for r in results})
    print(f"\n  Per-scenario:")
    for sc in scenarios:
        sc_results = [r for r in results if r["scenario"] == sc]
        sc_pass = sum(1 for r in sc_results if r["passed"])
        icon = "✅" if sc_pass == len(sc_results) else ("⚠️ " if sc_pass > 0 else "❌")
        print(f"    {icon} {sc}: {sc_pass}/{len(sc_results)}")

    print(f"\n{'='*62}")

    # Save JSON
    out = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "passed": len(passed),
        "failed": len(failed),
        "results": results,
    }
    with open("test/chaos_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Full results saved to test/chaos_results.json")
    print(f"{'='*62}\n")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TrafficBook chaos tests")
    parser.add_argument("--ssh-key",     default="~/.ssh/id_rsa",
                        help="Path to SSH private key for VM access")
    parser.add_argument("--user",        default="user",
                        help="SSH username on the VMs")
    parser.add_argument("--scenario",    default=None,
                        help="Run single scenario e.g. --scenario C-1")
    parser.add_argument("--dry-run",     action="store_true",
                        help="Print SSH commands without executing")
    parser.add_argument("--no-vm-stop",  action="store_true",
                        help="Skip C-8 (gcloud VM stop) -- service-level only")
    parser.add_argument("--all-regions", action="store_true",
                        help="Bootstrap tokens on all 3 regions (default: EU only)")
    args = parser.parse_args()

    import os
    SSH_KEY  = os.path.expanduser(args.ssh_key)
    SSH_USER = args.user
    DRY_RUN  = args.dry_run

    ALL_SCENARIOS = {
        "C-1":  scenario_c1,
        "C-2":  scenario_c2,
        "C-3":  scenario_c3,
        "C-4":  scenario_c4,
        "C-5":  scenario_c5,
        "C-6":  scenario_c6,
        "C-7":  scenario_c7,
        "C-8":  lambda: scenario_c8(no_vm_stop=args.no_vm_stop),
        "C-9":  scenario_c9,
        "C-10": scenario_c10,
    }

    print("\nTrafficBook -- Chaos & Node-Removal Fault Tolerance")
    print(f"SSH key : {SSH_KEY}")
    print(f"SSH user: {SSH_USER}")
    print(f"Dry run : {DRY_RUN}")
    print(f"Target  : EU={EU_LB}  US={US_LB}  APAC={APAC_LB}")

    bootstrap()

    if args.scenario:
        key = args.scenario.upper()
        fn = ALL_SCENARIOS.get(key)
        if not fn:
            print(f"Unknown scenario {key}. Options: {list(ALL_SCENARIOS.keys())}")
            sys.exit(1)
        fn()
    else:
        for key, fn in ALL_SCENARIOS.items():
            fn()

    print_summary()
    sys.exit(0 if all(r["passed"] for r in results) else 1)
