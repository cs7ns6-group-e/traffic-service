#!/usr/bin/env python3
"""
TrafficBook — End to End Test Suite
Run from your laptop: python3 tests/test_e2e.py
VMs must be running before executing this script.
"""

import requests
import json
import time
import sys
from datetime import datetime, timedelta

# ── Config ────────────────────────────────────────────────
EU_LB   = "http://35.240.110.205"
US_LB   = "http://34.10.45.241"
APAC_LB = "http://34.126.131.195"

EU_VM   = "http://104.155.13.81"
US_VM   = "http://136.111.143.185"
APAC_VM = "http://34.143.250.128"

REGIONS = [
    {"name": "EU",   "lb": EU_LB,   "vm": EU_VM},
    {"name": "US",   "lb": US_LB,   "vm": US_VM},
    {"name": "APAC", "lb": APAC_LB, "vm": APAC_VM},
]

FUTURE_TIME = (datetime.now() + timedelta(days=30)).strftime(
    "%Y-%m-%dT%H:%M:%S"
)

# ── Test helpers ──────────────────────────────────────────
passed = 0
failed = 0
errors = []

def ok(name):
    global passed
    passed += 1
    print(f"  ✅ {name}")

def fail(name, reason=""):
    global failed
    failed += 1
    errors.append(f"{name}: {reason}")
    print(f"  ❌ {name} — {reason}")

def section(name):
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")

def post(url, body, token=None, timeout=10):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(url, json=body, headers=headers, timeout=timeout)
        return r
    except Exception as e:
        return None

def get(url, token=None, timeout=10):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        return r
    except Exception as e:
        return None

def login(base_url, email, password):
    r = post(f"{base_url}/auth/login",
             {"email": email, "password": password})
    if r and r.status_code == 200:
        return r.json().get("access_token")
    return None

# ─────────────────────────────────────────────────────────
# TEST 1 — Health checks
# ─────────────────────────────────────────────────────────
section("TEST 1 — Health checks (all 3 regions)")

for region in REGIONS:
    r = get(f"{region['lb']}/health")
    if r and r.status_code == 200:
        ok(f"{region['name']} LB health")
    else:
        fail(f"{region['name']} LB health",
             f"status={r.status_code if r else 'timeout'}")

    for port, svc in [
        (8000,"auth"), (8001,"journey_booking"),
        (8002,"conflict"), (8003,"notification"),
        (8004,"road_routing"), (8005,"authority"),
        (8006,"admin")
    ]:
        r = get(f"{region['vm']}:{port}/health")
        if r and r.status_code == 200:
            ok(f"{region['name']} {svc}:{port}")
        else:
            fail(f"{region['name']} {svc}:{port}",
                 f"status={r.status_code if r else 'timeout'}")

# ─────────────────────────────────────────────────────────
# TEST 2 — Auth: login all 4 users on all 3 regions
# ─────────────────────────────────────────────────────────
section("TEST 2 — Auth login (all users, all regions)")

tokens = {}
users = [
    ("driver@trafficbook.com",    "Driver123!",    "driver"),
    ("emergency@trafficbook.com", "Emergency123!", "emergency"),
    ("authority@trafficbook.com", "Authority123!", "authority"),
    ("admin@trafficbook.com",     "Admin123!",     "admin"),
]

for region in REGIONS:
    tokens[region["name"]] = {}
    for email, password, key in users:
        token = login(region["lb"], email, password)
        if token:
            tokens[region["name"]][key] = token
            ok(f"{region['name']} login {key}")
        else:
            fail(f"{region['name']} login {key}", "no token returned")

# ─────────────────────────────────────────────────────────
# TEST 3 — Famous routes
# ─────────────────────────────────────────────────────────
section("TEST 3 — Famous routes (GET /routes/famous)")

for region in REGIONS:
    r = get(f"{region['lb']}/routes/famous")
    if r and r.status_code == 200:
        routes = r.json()
        if len(routes) >= 11:
            ok(f"{region['name']} famous routes ({len(routes)} routes)")
        else:
            fail(f"{region['name']} famous routes",
                 f"only {len(routes)} routes, expected 11")
    else:
        fail(f"{region['name']} famous routes",
             f"status={r.status_code if r else 'timeout'}")

# ─────────────────────────────────────────────────────────
# TEST 4 — Road routing
# ─────────────────────────────────────────────────────────
section("TEST 4 — Road routing (POST /route)")

for region in REGIONS:
    token = tokens.get(region["name"], {}).get("driver")
    if not token:
        fail(f"{region['name']} road routing", "no token")
        continue
    r = post(f"{region['lb']}/route",
             {"origin": "Dublin, Ireland",
              "destination": "Cork, Ireland"},
             token=token)
    if r and r.status_code == 200:
        data = r.json()
        if "distance_m" in data or "segments" in data:
            ok(f"{region['name']} road routing "
               f"({data.get('distance_km', '?')}km)")
        else:
            fail(f"{region['name']} road routing",
                 f"missing fields: {list(data.keys())}")
    else:
        fail(f"{region['name']} road routing",
             f"status={r.status_code if r else 'timeout'}")

# ─────────────────────────────────────────────────────────
# TEST 5 — Standard journey booking
# ─────────────────────────────────────────────────────────
section("TEST 5 — Standard journey booking")

journey_ids = {}
for region in REGIONS:
    token = tokens.get(region["name"], {}).get("driver")
    if not token:
        fail(f"{region['name']} booking", "no token")
        continue
    r = post(f"{region['lb']}/journeys", {
        "origin":      "Dublin, Ireland",
        "destination": "Cork, Ireland",
        "start_time":  FUTURE_TIME,
    }, token=token)
    if r and r.status_code in (200, 201):
        data = r.json()
        status = data.get("status", "")
        jid = data.get("id", "")
        journey_ids[region["name"]] = jid
        if status in ("CONFIRMED", "PENDING"):
            ok(f"{region['name']} booking — {status} (id:{jid[:8]})")
        else:
            fail(f"{region['name']} booking",
                 f"unexpected status: {status}")
    else:
        body = r.text if r else "timeout"
        fail(f"{region['name']} booking",
             f"status={r.status_code if r else 'timeout'} {body[:100]}")

# ─────────────────────────────────────────────────────────
# TEST 6 — Ghost reservation (conflict detection)
# ─────────────────────────────────────────────────────────
section("TEST 6 — Ghost reservation (conflict detection)")

import threading

results = []
def book(url, body, token):
    r = post(url, body, token=token)
    results.append(r)

token = tokens.get("EU", {}).get("driver")
if token:
    t1 = threading.Thread(target=book, args=(
        f"{EU_LB}/journeys",
        {"origin": "London, UK",
         "destination": "Manchester, UK",
         "start_time": FUTURE_TIME},
        token
    ))
    t2 = threading.Thread(target=book, args=(
        f"{EU_LB}/journeys",
        {"origin": "London, UK",
         "destination": "Manchester, UK",
         "start_time": FUTURE_TIME},
        token
    ))
    t1.start(); t2.start()
    t1.join();  t2.join()

    statuses = [r.status_code for r in results if r]
    if 409 in statuses:
        ok("EU ghost reservation — conflict detected (409)")
    elif all(s in (200, 201) for s in statuses):
        fail("EU ghost reservation",
             "both bookings succeeded — conflict detection not working")
    else:
        fail("EU ghost reservation",
             f"unexpected statuses: {statuses}")
else:
    fail("EU ghost reservation", "no token")

# ─────────────────────────────────────────────────────────
# TEST 7 — Emergency vehicle booking
# ─────────────────────────────────────────────────────────
section("TEST 7 — Emergency vehicle (instant approval)")

token = tokens.get("EU", {}).get("emergency")
if token:
    r = post(f"{EU_LB}/journeys", {
        "origin":      "Dublin, Ireland",
        "destination": "Cork, Ireland",
        "start_time":  FUTURE_TIME,
    }, token=token)
    if r and r.status_code in (200, 201):
        data = r.json()
        status = data.get("status", "")
        vtype  = data.get("vehicle_type", "")
        if status == "EMERGENCY_CONFIRMED":
            ok(f"Emergency booking — {status}")
        elif "CONFIRMED" in status:
            fail("Emergency booking",
                 f"status={status}, expected EMERGENCY_CONFIRMED")
        else:
            fail("Emergency booking", f"status={status}")
    else:
        fail("Emergency booking",
             f"status={r.status_code if r else 'timeout'}")
else:
    fail("Emergency booking", "no emergency token")

# ─────────────────────────────────────────────────────────
# TEST 8 — Cross-region booking (EU → US)
# ─────────────────────────────────────────────────────────
section("TEST 8 — Cross-region booking (EU → US)")

token = tokens.get("EU", {}).get("driver")
us_token = tokens.get("US", {}).get("driver")

if token:
    r = post(f"{EU_LB}/journeys", {
        "origin":      "Dublin, Ireland",
        "destination": "New York, USA",
        "start_time":  FUTURE_TIME,
    }, token=token)
    if r and r.status_code in (200, 201):
        data = r.json()
        if data.get("is_cross_region") and \
           data.get("dest_region") == "US":
            ok(f"EU→US cross-region detected "
               f"(id:{data.get('id','?')[:8]})")

            # Wait for REST call to propagate
            time.sleep(3)

            # Check US DB
            if us_token:
                r2 = get(
                    f"{US_LB}/journeys"
                    f"?driver_id=driver@trafficbook.com",
                    token=us_token
                )
                if r2 and r2.status_code == 200:
                    us_journeys = r2.json()
                    cross = [j for j in us_journeys
                             if j.get("is_cross_region")]
                    if cross:
                        ok(f"Cross-region arrived in US DB "
                           f"({len(cross)} journeys)")
                    else:
                        fail("Cross-region US DB check",
                             "journey not found in US DB")
                else:
                    fail("Cross-region US DB check",
                         "could not query US journeys")
        else:
            fail("EU→US cross-region",
                 f"is_cross_region={data.get('is_cross_region')} "
                 f"dest={data.get('dest_region')}")
    else:
        fail("EU→US cross-region",
             f"status={r.status_code if r else 'timeout'}")
else:
    fail("EU→US cross-region", "no EU token")

# ─────────────────────────────────────────────────────────
# TEST 9 — Traffic authority
# ─────────────────────────────────────────────────────────
section("TEST 9 — Traffic authority")

token = tokens.get("EU", {}).get("authority")
if token:
    # View journeys
    r = get(f"{EU_LB}/authority/journeys", token=token)
    if r and r.status_code == 200:
        journeys = r.json()
        ok(f"Authority can view journeys ({len(journeys)} total)")
    else:
        fail("Authority view journeys",
             f"status={r.status_code if r else 'timeout'}")

    # Create road closure
    r = post(f"{EU_LB}/authority/closure", {
        "road_name": "Test Road E2E",
        "reason":    "E2E test closure",
        "region":    "EU"
    }, token=token)
    if r and r.status_code in (200, 201):
        data = r.json()
        ok(f"Road closure created "
           f"(affected: {data.get('affected_journeys', 0)} journeys)")
    else:
        fail("Road closure",
             f"status={r.status_code if r else 'timeout'} "
             f"{r.text[:100] if r else ''}")
else:
    fail("Traffic authority tests", "no authority token")

# ─────────────────────────────────────────────────────────
# TEST 10 — Admin observability
# ─────────────────────────────────────────────────────────
section("TEST 10 — Admin observability")

token = tokens.get("EU", {}).get("admin")
if token:
    # Health check
    r = get(f"{EU_LB}/admin/health", token=token)
    if r and r.status_code == 200:
        data = r.json()
        services = data.get("services", [])
        healthy = sum(1 for s in services
                      if s.get("status") == "ok")
        ok(f"Admin health — {healthy}/{len(services)} services ok")
    else:
        fail("Admin health",
             f"status={r.status_code if r else 'timeout'}")

    # All regions stats
    r = get(f"{EU_LB}/admin/all-regions", token=token)
    if r and r.status_code == 200:
        data = r.json()
        regions_present = [k for k in ["eu","us","apac"]
                           if k in data or k.upper() in data]
        ok(f"Admin all-regions — {len(regions_present)} regions responded")
    else:
        fail("Admin all-regions",
             f"status={r.status_code if r else 'timeout'}")
else:
    fail("Admin tests", "no admin token")

# ─────────────────────────────────────────────────────────
# TEST 11 — VM failure simulation
# ─────────────────────────────────────────────────────────
section("TEST 11 — Regional independence (no VM stop needed)")
print("  Skipping live VM stop test — run manually with:")
print("  gcloud compute instances stop tb-vm-eu \\")
print("    --zone=europe-west1-b")
print("  curl http://34.10.45.241/health  # US still works")
print("  curl http://34.126.131.195/health # APAC still works")

# ─────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"  RESULTS: {passed} passed  {failed} failed")
print(f"{'='*50}")

if errors:
    print("\nFailed tests:")
    for e in errors:
        print(f"  ❌ {e}")

if failed == 0:
    print("\n🎉 All tests passed! System is fully working.")
elif failed <= 3:
    print("\n⚠️  Minor issues — check failed tests above.")
else:
    print("\n🔴 Significant issues — review backend services.")

sys.exit(0 if failed == 0 else 1)